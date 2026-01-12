from fastapi import APIRouter, Depends, status
from src.agents.dto.agent_dto import AgentGenerationRequest, AgentGenerationResponse
from src.agents.agent_service import AgentService
from src.auth.auth_service import verify_token
from src.users.user_model import UserModel

router = APIRouter(prefix="/api/agents", tags=["Agents"])

@router.post("/generate", response_model=AgentGenerationResponse, status_code=status.HTTP_200_OK)
async def generate_compliant_media(
    request: AgentGenerationRequest,
    agent_service: AgentService = Depends(),
    current_user: UserModel = Depends(verify_token)
):
    """
    Triggers the Agentic RAG workflow: Enforce -> Generate -> Validate (Async).
    """
    return await agent_service.generate_compliant_media(request, current_user)
