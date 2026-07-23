from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import SessionLocal
from ..agent import run_agent_chat
from ..agent.memory import clear_history, get_pending_confirmation

router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"

def get_db():
    db = SessionLocal()
    try:
         yield db
    finally:
         db.close()

@router.post("/chat")
def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    """Conversational endpoint representing the AutoBasket Smart Pantry Agent."""
    answer = run_agent_chat(req.message, req.session_id, db)
    pending = get_pending_confirmation(req.session_id)
    return {
        "response": answer,
        "needs_confirmation": pending is not None,
        "pending_confirmation": pending,
    }

@router.post("/clear")
def clear_endpoint(session_id: str = "default_session"):
    """Resets conversational memory history for a session."""
    clear_history(session_id)
    return {"message": f"Successfully cleared chat history for session '{session_id}'."}
