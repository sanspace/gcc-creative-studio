import logging
import json
from typing import List, Dict, Any, Optional
from src.multimodal.gemini_service import GeminiService
from google.genai import types
from fastapi import Depends

logger = logging.getLogger(__name__)

class ValidatorAgent:
    """
    Agent responsible for visually auditing generated assets against branding guidelines.
    """
    def __init__(self, gemini_service: GeminiService = Depends()):
        self.gemini_service = gemini_service

    async def validate_asset(
        self, 
        asset_uri: str, 
        guidelines_text: str, 
        original_prompt: str
    ) -> Dict[str, Any]:
        """
        Validates a single asset against the guidelines.
        
        Args:
            asset_uri: GCS URI of the image/video to validate.
            guidelines_text: The guidelines text used for generation.
            original_prompt: The prompt used.
            
        Returns:
            Validation report (JSON).
        """
        logger.info(f"Validating asset: {asset_uri}")
        
        # Construct Multimodal Prompt
        prompt = (
            "You are the Brand Validator Agent. Your task is to audit the provided image against the following brand guidelines.\n"
            "Determine if the image complies with the visual style, color palette, and other rules.\n"
            "Also check if it faithfully represents the original user prompt.\n\n"
            f"--- BRAND GUIDELINES ---\n{guidelines_text}\n----------------------\n\n"
            f"--- ORIGINAL PROMPT ---\n{original_prompt}\n----------------------\n\n"
            "Provide your assessment in the following JSON format:\n"
            "{\n"
            "  \"is_compliant\": boolean,\n"
            "  \"score\": integer (0-100),\n"
            "  \"reasoning\": \"string explanation\",\n"
            "  \"issues\": [\"list\", \"of\", \"issues\"]\n"
            "}"
        )
        
        # Prepare content parts
        # GeminiService might need a helper for 'from_uri' if not exposed, 
        # but internal generate_content usage in gemini_service handles types.Part.
        
        # We need to construct the call. 
        # Since GeminiService abstracts the client, we might need a method there or use the client directly if exposed.
        # GeminiService exposes `client`.
        
        try:
            image_part = types.Part.from_uri(file_uri=asset_uri, mime_type="image/png") # Assuming PNG/JPEG, API usually handles detection or defaulting
            if asset_uri.endswith(".jpg") or asset_uri.endswith(".jpeg"):
                 image_part = types.Part.from_uri(file_uri=asset_uri, mime_type="image/jpeg")
            
            response = self.gemini_service.client.models.generate_content(
                model=self.gemini_service.rewriter_model, # Reuse default model or config specific validator model
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            if response.text:
                return json.loads(response.text)
            return {"is_compliant": False, "reasoning": "No response from model", "score": 0}
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {"is_compliant": False, "reasoning": f"Validation error: {e}", "score": 0}

    async def validate_batch(
        self,
        media_item_ids: List[int],
        guidelines_text: str,
        original_prompt: str,
        media_repo: Any
    ) -> List[Dict[str, Any]]:
        """
        Validates a batch of media items identified by their IDs.
        """
        results = []
        for mid in media_item_ids:
            item = await media_repo.get_by_id(mid)
            if not item or not item.gcs_uris:
                continue
                
            for uri in item.gcs_uris:
                res = await self.validate_asset(uri, guidelines_text, original_prompt)
                results.append({
                    "media_item_id": mid,
                    "uri": uri,
                    "validation": res
                })
        return results
