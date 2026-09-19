from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..agent import run_agent_chat
from ..agent.memory import clear_history, get_pending_confirmation
from ..api.deps import current_household, get_db

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"


def _scoped(household: models.Household, session_id: str) -> str:
    """Chat memory is keyed per household so two homes never share a conversation."""
    return f"{household.id}:{session_id}"


@router.post("/chat")
def chat_endpoint(
    req: ChatRequest,
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    """Conversational endpoint representing the AutoBasket Smart Pantry Agent."""
    session = _scoped(household, req.session_id)
    answer = run_agent_chat(req.message, session, db, household)
    pending = get_pending_confirmation(session)
    return {
        "response": answer,
        "needs_confirmation": pending is not None,
        "pending_confirmation": pending,
    }


@router.post("/clear")
def clear_endpoint(session_id: str = "default_session", household: models.Household = Depends(current_household)):
    """Resets conversational memory history for a session."""
    clear_history(_scoped(household, session_id))
    return {"message": f"Successfully cleared chat history for session '{session_id}'."}
