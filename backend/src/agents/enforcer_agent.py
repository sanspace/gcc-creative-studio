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
        guidelines_text = await self.search_tool(user_prompt, str(workspace_id) if workspace_id else "Global")
        
        # 2. Synthesize Enhanced Prompt using Gemini
        # We construct a specific system instruction for the Enforcer.
        system_instruction = (
            "You are the Branding Enforcer Agent for a Creative Studio. "
            "Your goal is to rewrite user prompts to strictly adhere to the provided brand guidelines. "
            "You must ensure the generated media will match the brand's visual style and tone. "
            "Do NOT remove the core intent of the user's request, but wrap it in the brand's aesthetics. "
            "If the user's request explicitly violates a negative constraint in the guidelines (e.g. 'Do not use red'), "
            "you must modify the request to be compliant or politely explain why if modification makes it impossible (but prefer modification). "
            "\n\n"
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
            "guidelines_used": guidelines_text
        }