import logging
from typing import Dict, Any, List
from fastapi import Depends

from src.agents.enforcer_agent import BrandingEnforcerAgent
from src.agents.validator_agent import ValidatorAgent
from src.agents.dto.agent_dto import AgentGenerationRequest, AgentGenerationResponse
from src.images.dto.create_imagen_dto import CreateImagenDto, AspectRatioEnum
from src.videos.dto.create_veo_dto import CreateVeoDto
from src.audios.dto.create_audio_dto import CreateAudioDto
from src.common.base_dto import GenerationModelEnum
from src.videos.veo_service import VeoService
from src.audios.audio_service import AudioService
from src.images.imagen_service import ImagenService
from src.users.user_model import UserModel
from src.audios.audio_constants import VoiceEnum, LanguageEnum

logger = logging.getLogger(__name__)

class AgentService:
    """
    Orchestrates the Agentic RAG flow for Images, Video, and Audio.
    1. Enforcer: Enhances prompt using retrieved guidelines.
    2. Generator: Generates assets using enhanced prompt.
    3. Validator: Audits generated assets (Async/Post-process).
    """

    def __init__(
        self,
        enforcer_agent: BrandingEnforcerAgent = Depends(),
        validator_agent: ValidatorAgent = Depends(),
        imagen_service: ImagenService = Depends(),
        veo_service: VeoService = Depends(),
        audio_service: AudioService = Depends()
    ):
        self.enforcer_agent = enforcer_agent
        self.validator_agent = validator_agent
        self.imagen_service = imagen_service
        self.veo_service = veo_service
        self.audio_service = audio_service

    async def generate_compliant_media(
        self, 
        request: AgentGenerationRequest, 
        current_user: UserModel
    ) -> AgentGenerationResponse:
        """
        Executes the full agentic flow.
        """
        logger.info(f"Starting agentic generation for user {current_user.email} - Type: {request.media_type}")
        
        # 1. Enforce Guidelines
        enforcement_result = await self.enforcer_agent.enforce_guidelines(
            user_prompt=request.prompt,
            workspace_id=request.workspace_id
        )
        enhanced_prompt = enforcement_result["enhanced_prompt"]
        logger.info(f"Enhanced Prompt: {enhanced_prompt}")

        # 2. Determine Model
        model_str = request.generation_model
        generation_model = None
        if model_str:
            try:
                # Try to match string to Enum
                for m in GenerationModelEnum:
                    if m.value == model_str:
                        generation_model = m
                        break
            except Exception:
                logger.warning(f"Could not map model string '{model_str}' to GenerationModelEnum.")

        # 3. Dispatch to appropriate Service
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1) # TODO: Use shared app executor

        media_response = None
        
        if request.media_type == "IMAGE":
            # Default to Gemini 2.0 Flash if not specified
            if not generation_model:
                generation_model = GenerationModelEnum.GEMINI_2_0_FLASH_EXP
                
            ar_enum = AspectRatioEnum.RATIO_1_1
            if request.aspect_ratio:
                 for ar in AspectRatioEnum:
                    if ar.value == request.aspect_ratio:
                        ar_enum = ar
                        break
            
            imagen_dto = CreateImagenDto(
                prompt=enhanced_prompt,
                workspace_id=request.workspace_id,
                generation_model=generation_model,
                aspect_ratio=ar_enum,
                number_of_media=request.number_of_images,
                reference_image_gcs_uris=[request.reference_image_uri] if request.reference_image_uri else None
            )
            media_response = await self.imagen_service.start_image_generation_job(
                request_dto=imagen_dto,
                user=current_user,
                executor=executor
            )
            
        elif request.media_type == "VIDEO":
            # Default to Veo 2.0
            if not generation_model:
                generation_model = GenerationModelEnum.VEO_2_0_001
            
            # Map aspect ratio
            ar_enum = AspectRatioEnum.RATIO_16_9 # Default for video usually
            if request.aspect_ratio:
                 for ar in AspectRatioEnum:
                    if ar.value == request.aspect_ratio:
                        ar_enum = ar
                        break

            veo_dto = CreateVeoDto(
                prompt=enhanced_prompt,
                workspace_id=request.workspace_id,
                generation_model=generation_model,
                aspect_ratio=ar_enum,
                duration_seconds=request.duration_seconds,
                generate_audio=request.generate_audio,
            )
            media_response = await self.veo_service.start_video_generation_job(
                request_dto=veo_dto,
                user=current_user,
                executor=executor
            )

        elif request.media_type == "AUDIO":
            # AUDIO is usually synchronous or simpler in this app structure, 
            # but AudioService.generate_audio returns MediaItemResponse.
            # It might be async/blocking. 
            
            # Default to Gemini 2.5 Flash TTS
            if not generation_model:
                generation_model = GenerationModelEnum.GEMINI_2_5_FLASH_TTS
            
            audio_dto = CreateAudioDto(
                prompt=enhanced_prompt,
                workspace_id=request.workspace_id,
                model=generation_model,
                voice_name=VoiceEnum.PUCK, # Default
                language_code=LanguageEnum.EN_US,
                sample_count=1 # Default
            )
            # Audio service execution
            media_response = await self.audio_service.generate_audio(
                request_dto=audio_dto,
                user=current_user
            )

        else:
             raise ValueError(f"Unsupported media type: {request.media_type}")

        # 4. Trigger Validation (Fire & Forget Task)
        if media_response and media_response.id:
             import asyncio
             from src.common.schema.media_item_model import JobStatusEnum
             
             # Determine which service to use for polling
             repo_service = None
             if request.media_type == "IMAGE":
                 repo_service = self.imagen_service
             elif request.media_type == "VIDEO":
                 repo_service = self.veo_service
             elif request.media_type == "AUDIO":
                 repo_service = self.audio_service

             if repo_service:
                 async def poll_and_validate(mid: int, service_instance, guidelines: str, orig_prompt: str):
                     try:
                         # Polling configuration: 10 minutes max
                         max_attempts = 120 
                         delay = 5
                         
                         for _ in range(max_attempts):
                             await asyncio.sleep(delay)
                             if not hasattr(service_instance, 'media_repo'):
                                 return

                             item = await service_instance.media_repo.get_by_id(mid)
                             if not item:
                                 return
                                 
                             if item.status == JobStatusEnum.COMPLETED:
                                 logger.info(f"Generation completed for {mid}. Triggering validation.")
                                 await self.validator_agent.validate_batch(
                                     media_item_ids=[mid],
                                     guidelines_text=guidelines,
                                     original_prompt=orig_prompt,
                                     media_repo=service_instance.media_repo
                                 )
                                 return
                                 
                             if item.status == JobStatusEnum.FAILED:
                                 return
                         
                         logger.warning(f"Polling timed out for {mid}.")
                         
                     except Exception as e:
                         logger.error(f"Async validation task failed for {mid}: {e}")

                 # Launch the background task
                 guidelines_used = enforcement_result.get("guidelines_used", "")
                 asyncio.create_task(poll_and_validate(media_response.id, repo_service, guidelines_used, request.prompt))

        # 5. Return Response
        return AgentGenerationResponse(
            original_prompt=request.prompt,
            enhanced_prompt=enhanced_prompt,
            generated_assets=[{
                "id": media_response.id,
                "status": media_response.status,
                "note": "Generation started. Validation is queued."
            }] if media_response else []
        )
