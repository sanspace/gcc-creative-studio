import logging
from typing import Optional, List, Dict, Any
# Use the refactored tool creator or class
# The existing vector_search_tool.py exports `create_search_branding_guidelines_tool`.
# We might need to wrap it or call it. It returns a function. 
# ADK Agents typically expect a Tool object or a function.
# Let's import the creation function and dependencies.
from src.tools.vector_search_tool import create_search_branding_guidelines_tool
from src.common.vector_search_service import VectorSearchService
from src.multimodal.gemini_service import GeminiService
from src.brand_guidelines.repository.brand_guideline_repository import BrandGuidelineRepository
from fastapi import Depends

logger = logging.getLogger(__name__)

class BrandingEnforcerAgent:
    """
    Agent responsible for ensuring that generation prompts adhere to branding guidelines.
    It retrieves relevant guidelines and synthesizes a compliant prompt.
    """
    def __init__(
        self, 
        vector_search_service: VectorSearchService = Depends(),
        gemini_service: GeminiService = Depends(),
        brand_guideline_repo: BrandGuidelineRepository = Depends()
    ):
        # Create the tool instance (callable)
        self.search_tool = create_search_branding_guidelines_tool(
            vector_search_service, 
            gemini_service,
            brand_guideline_repo
        )
        self.gemini_service = gemini_service

    async def enforce_guidelines(self, user_prompt: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyzes the user prompt, retrieves guidelines, and returns an enhanced prompt.
        
        Args:
            user_prompt: The raw prompt from the user.
            workspace_id: The workspace to scope the guideline search.
            
        Returns:
            Dict containing 'enhanced_prompt' and 'guidelines_used'.
        """
        logger.info(f"Enforcing guidelines for prompt: '{user_prompt}' in workspace: {workspace_id}")
        
        # 1. Retrieve Guidelines using the tool
        # The tool function is async now
        # 1. Retrieve Guidelines using the tool
        # The tool function is async now and returns a Dict
        # Augment query to ensure we fetch general style references even if the prompt is specific
        search_query = f"{user_prompt} Visual Style Tone Brand Guidelines Color Palette Logo Typography Shapes Brand Name"
        search_result = await self.search_tool(search_query, str(workspace_id) if workspace_id else "Global")

        logger.info(f"Search Result: {search_result}")
        
        # Handle the result whether it's the new Dict format or legacy string (safeguard)
        if isinstance(search_result, dict):
            guidelines_text = search_result.get("rules_text", "")
            reference_image_uris = search_result.get("reference_image_uris", [])
        else:
            guidelines_text = str(search_result)
            reference_image_uris = []
            
        
        # 2. Synthesize Enhanced Prompt using Gemini
        # We construct a specific system instruction for the Enforcer.
        system_instruction = (
            "You are the Branding Enforcer Agent for a Creative Studio. "
            "Your goal is to rewrite user prompts to strictly adhere to the provided brand guidelines. "
            "You must ensure the generated media will match the brand's Visual Style and Tone of Voice. "
            "\n\n"
            "INSTRUCTIONS:\n"
            "1. Analyze the retrieved 'Relevant Brand Guidelines' carefully. Extract key elements of the Visual Style (colors, composition, lighting, texture) and Tone.\n"
            "2. Rewrite the 'User Prompt' to be highly detailed and descriptive. EXPAND on the user's intent using the brand's vocabulary.\n"
            "3. If the user's request is vague (e.g. 'a logo'), use the guidelines to fill in specific details (e.g. 'a minimalist geometric logo in deep teal and charcoal...').\n"
            "4. Do NOT remove the core subject of the request, but transform its presentation to match the brand.\n"
            "5. If negative constraints exist (e.g. 'No gradients'), strictly obey them.\n"
            "\n"
            "Output ONLY the rewritten prompt. Do not add conversational filler."
        )
        
        full_prompt = (
            f"{system_instruction}\n\n"
            f"--- RELEVANT BRAND GUIDELINES ---\n"
            f"{guidelines_text}\n"
            f"---------------------------------\n\n"
            f"USER PROMPT: {user_prompt}\n"
            f"ENHANCED PROMPT:"
        )
        
        # Call Gemini (using generate_text for now as a simple interface)
        enhanced_prompt = self.gemini_service.generate_text(full_prompt)
        
        return {
            "original_prompt": user_prompt,
            "enhanced_prompt": enhanced_prompt,
            "guidelines_used": guidelines_text,
            "reference_image_uris": reference_image_uris
        }