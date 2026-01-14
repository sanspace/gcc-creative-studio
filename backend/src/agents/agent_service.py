import logging
from enum import Enum
from typing import Dict, Any, List
from fastapi import Depends

from src.agents.enforcer_agent import BrandingEnforcerAgent
from src.agents.validator_agent import ValidatorAgent
from src.agents.dto.agent_dto import AgentGenerationRequest, AgentGenerationResponse, MediaTypeEnum
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
        logger.info(f"Enforcement Result: {enforcement_result}")
        # logger.info(f"Enhanced Prompt: {enhanced_prompt}")

        # 2. Determine Model
        # The DTO now parses string inputs to Enums automatically where possible,
        # or we accept the Enum directly if the frontend sends it.
        generation_model = request.generation_model
        
        # 3. Dispatch to appropriate Service
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1) # TODO: Use shared app executor

        media_response = None
        
        if request.media_type == MediaTypeEnum.IMAGE:
            # Default to Gemini 2.0 Flash if not specified
            if not generation_model:
                generation_model = GenerationModelEnum.GEMINI_2_5_FLASH_IMAGE_PREVIEW
                
            ar_enum = request.aspect_ratio or AspectRatioEnum.RATIO_1_1
            
            # Gather reference images from both the user request and the enforcer agent
            all_reference_uris = []
            if request.reference_image_uri:
                all_reference_uris.append(request.reference_image_uri)
            
            # Add reference images retrieved by the Enforcer (e.g. brand assets)
            enforcer_ref_uris = enforcement_result.get("reference_image_uris", [])
            if enforcer_ref_uris:
                all_reference_uris.extend(enforcer_ref_uris)
            
            imagen_dto = CreateImagenDto(
                prompt=enhanced_prompt,
                workspace_id=request.workspace_id,
                generation_model=generation_model,
                aspect_ratio=ar_enum,
                number_of_media=request.number_of_media,
                style=request.style,
                reference_image_gcs_uris=all_reference_uris if all_reference_uris else None
            )
            media_response = await self.imagen_service.start_image_generation_job(
                request_dto=imagen_dto,
                user=current_user,
                executor=executor
            )
            
        elif request.media_type == MediaTypeEnum.VIDEO:
            # Default to Veo 2.0
            if not generation_model:
                generation_model = GenerationModelEnum.VEO_2_0_001
            
            # Map aspect ratio
            ar_enum = request.aspect_ratio or AspectRatioEnum.RATIO_16_9

            veo_dto = CreateVeoDto(
                prompt=enhanced_prompt,
                workspace_id=request.workspace_id,
                generation_model=generation_model,
                aspect_ratio=ar_enum,
                duration_seconds=request.duration_seconds,
                generate_audio=request.generate_audio,
                style=request.style,
            )
            media_response = await self.veo_service.start_video_generation_job(
                request_dto=veo_dto,
                user=current_user,
                executor=executor
            )

        elif request.media_type == MediaTypeEnum.AUDIO:
            # Default to Gemini 2.5 Flash TTS
            if not generation_model:
                generation_model = GenerationModelEnum.GEMINI_2_5_FLASH_TTS
            
            audio_dto = CreateAudioDto(
                prompt=enhanced_prompt,
                workspace_id=request.workspace_id,
                model=generation_model,
                voice_name=request.voice_name or VoiceEnum.PUCK,
                language_code=LanguageEnum.EN_US,
                sample_count=request.number_of_media or 1
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
                                 validation_results = await self.validator_agent.validate_batch(
                                     media_item_ids=[mid],
                                     guidelines_text=guidelines,
                                     original_prompt=orig_prompt,
                                     media_repo=service_instance.media_repo
                                 )
                                 
                                 # Ensure results are sorted by URI to match the index order in gcs_uris
                                 # This assumes item.gcs_uris order is consistent (it is a List)
                                 # create a map for O(1) lookup
                                 res_map = {r['uri']: r for r in validation_results}
                                 in_order_results = []
                                 for uri in item.gcs_uris:
                                     if uri in res_map:
                                         in_order_results.append(res_map[uri])
                                     else:
                                         # Should not happen if validate_batch covers all
                                         in_order_results.append({"validation": {"is_compliant": False, "reasoning": "Validation missing", "score": 0}})
                                 
                                 # Persist validation results
                                 # Persist validation results
                                 all_validations = []
                                 combined_critique = []
                                 
                                 for res in in_order_results:
                                     validation_data = res.get("validation", {})
                                     all_validations.append(validation_data)
                                     # Optional: Combine critiques or just use the first/generic one
                                     # For now, let's append them for observability or pick the first failed one?
                                     # Combining is safer for visibility.
                                     score = validation_data.get('score', 0)
                                     status = "COMPLIANT" if validation_data.get('is_compliant') else "NON-COMPLIANT"
                                     combined_critique.append(f"[Image {len(all_validations)}] {status} (Score: {score}): {validation_data.get('reasoning', '')}")

                                 update_payload = {
                                     "raw_data": {"validations": all_validations},
                                     "critique": "\n\n".join(combined_critique)
                                 }
                                 await service_instance.media_repo.update(mid, update_payload)
                                 logger.info(f"Validation saved for {mid}. Validated {len(all_validations)} images.")
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
