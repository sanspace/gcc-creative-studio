import asyncio
import logging
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.config.logger_config import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

async def main():
    """
    End-to-End Test for Hybrid Search & Agentic Flow
    1. Ingest Brand Guideline (Mock Upload + Process)
    2. Verify Sparse Indexing
    3. Run Agent Generation
    """
    from src.database import WorkerDatabase
    from src.brand_guidelines.repository.brand_guideline_repository import BrandGuidelineRepository
    from src.brand_guidelines.brand_guideline_service import BrandGuidelineService
    from src.common.storage_service import GcsService
    from src.multimodal.gemini_service import GeminiService
    from src.common.vector_search_service import VectorSearchService
    from src.common.sparse_embedding_service import SparseEmbeddingService
    from src.agents.agent_service import AgentService
    from src.agents.dto.agent_dto import AgentGenerationRequest
    from src.users.user_model import UserModel, UserRoleEnum
    from src.workspaces.repository.workspace_repository import WorkspaceRepository
    from src.auth.iam_signer_credentials_service import IamSignerCredentials

    # Initialize Services
    # Note: We need a DB connection context
    async with WorkerDatabase() as db_factory:
        async with db_factory() as db:
            logger.info("Initializing Services...")
            
            # Repos & Services
            bg_repo = BrandGuidelineRepository(db)
            ws_repo = WorkspaceRepository(db)
            gcs_service = GcsService()
            gemini_service = GeminiService(brand_guideline_repo=bg_repo)
            vector_service = VectorSearchService()
            sparse_service = SparseEmbeddingService()
            iam_signer = IamSignerCredentials()
            
            # Application Services
            bg_service = BrandGuidelineService(
                repo=bg_repo,
                gcs_service=gcs_service,
                gemini_service=gemini_service,
                workspace_repo=ws_repo,
                iam_signer_credentials=iam_signer,
                vector_search_service=vector_service
            )
            
            # Instantiate Agents
            from src.agents.enforcer_agent import BrandingEnforcerAgent
            from src.agents.validator_agent import ValidatorAgent
            
            enforcer = BrandingEnforcerAgent(
                vector_search_service=vector_service,
                gemini_service=gemini_service,
                brand_guideline_repo=bg_repo
            )
            validator = ValidatorAgent(
                gemini_service=gemini_service
            )

            agent_service = AgentService(
                enforcer_agent=enforcer,
                validator_agent=validator,
                imagen_service=None,
                veo_service=None,
                audio_service=None
            )

            # ---------------------------------------------------------
            # 1. Ingestion
            # ---------------------------------------------------------
            pdf_path = "/usr/local/google/home/vasanthakumara/gcc-creative-studio/brand_guidelines.pdf"
            if not os.path.exists(pdf_path):
                logger.error(f"PDF not found at {pdf_path}")
                return

            logger.info(f"Reading PDF from {pdf_path}...")
            with open(pdf_path, "rb") as f:
                pdf_content = f.read()

            # Upload to GCS (Simulate Client Upload)
            # functionality is in bg_service._split_and_upload_pdf or similar?
            # actually we can just upload it manually to a test path
            filename = "test_guidelines.pdf"
            gcs_uri = f"gs://{gcs_service.bucket_name}/tests/{filename}"
            gcs_service.upload_bytes_to_gcs(pdf_content, f"tests/{filename}", "application/pdf")
            logger.info(f"Uploaded to {gcs_uri}")

            # Trigger Processing (using internal method to bypass API/Auth)
            # We need to simulate the background job call
            from src.brand_guidelines.brand_guideline_service import _process_brand_guideline_in_background
            
            # Create a mock placeholder entry
            from src.brand_guidelines.schema.brand_guideline_model import BrandGuidelineModel
            from src.common.schema.media_item_model import JobStatusEnum
            
            placeholder = BrandGuidelineModel(
                name="Test Guidelines (Auto)",
                status=JobStatusEnum.PROCESSING,
                source_pdf_gcs_uris=[gcs_uri]
            )
            placeholder = await bg_repo.create(placeholder)
            logger.info(f"Created Placeholder Guideline ID: {placeholder.id}")

            # Run the worker function directly (it runs its own loop, but we are async?)
            # The worker function creates a NEW loop. calling it from here might be tricky if we are already in a loop.
            # _process_brand_guideline_in_background is synchronous wrapper that starts a loop.
            # We should probably run the logic inside it? 
            # Or simpler: run it in a thread/executor.
            
            logger.info("Starting Ingestion Worker...")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, 
                _process_brand_guideline_in_background,
                placeholder.id,
                "Test Guidelines (Auto)",
                filename,
                gcs_uri,
                None # workspace_id
            )
            
            # Poll for completion
            while True:
                g = await bg_repo.get_by_id(placeholder.id)
                logger.info(f"Guideline Status: {g.status}")
                if g.status == JobStatusEnum.COMPLETED:
                    break
                if g.status == JobStatusEnum.FAILED:
                    logger.error(f"Ingestion Failed: {g.error_message}")
                    return
                await asyncio.sleep(2)

            logger.info("Ingestion Complete!")

            # ---------------------------------------------------------
            # 2. Verify Sparse Indexing
            # ---------------------------------------------------------
            # Verify that we can generate a sparse embedding for a keyword from the doc
            # This requires knowing a keyword. Let's guess or check the text.
            guideline_text = g.guideline_text or ""
            # Fallback to summaries if text is empty, just for testing
            if not guideline_text:
                guideline_text = (g.tone_of_voice_summary or "") + "\n" + (g.visual_style_summary or "")
            
            snippet = guideline_text[:50] if guideline_text else "No Text"
            logger.info(f"Extracted Text Snippet: {snippet}")
            
            if guideline_text:
                sparse_vec = sparse_service.get_sparse_embedding(guideline_text[:1000]) # Use reasonable chunk
                if sparse_vec:
                    logger.info(f"Sparse Vector Generated! Dimensions: {len(sparse_vec['dimensions'])}")
                else:
                    logger.error("Sparse Vector Generation Failed (Locally).")
            else:
                logger.warning("No text available for sparse vector generation test.")

            # ---------------------------------------------------------
            # 3. Agent Generation (Enforcer Only Test)
            # ---------------------------------------------------------
            # We will test the Enforcer's ability to retrieve this guideline using Hybrid Search.
            # We won't trigger full generation (Imagen/Veo) unless we have mocks or keys, 
            # but getting the "Enhanced Prompt" proves Hybrid Search worked.
            
            logger.info("Testing Enforcer Agent (Hybrid Search)...")
            prompt = "Create a social media post." 
            # Add a keyword from the PDF if possible to test sparse search? 
            # For now, generic prompt.
            
            # Manually invoke Enforcer
            enforcer = agent_service.enforcer_agent
            enhanced_prompt = await enforcer.enforce_guidelines(
                prompt, 
                workspace_id=None, # Global
            )
            
            logger.info("------------------------------------------------")
            logger.info(f"Original Prompt: {prompt}")
            logger.info(f"Enhanced Prompt: {enhanced_prompt}")
            logger.info("------------------------------------------------")
            
            if len(enhanced_prompt) > len(prompt):
                logger.info("SUCCESS: Prompt was enhanced, likely retrieved guidelines.")
            else:
                logger.warning("Prompt might not have been enhanced (check logs).")

if __name__ == "__main__":
    asyncio.run(main())
