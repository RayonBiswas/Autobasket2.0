from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..services import proposals
from ..services.notify import notification_row
from ..services.orders import order_row

router = APIRouter()


class Respond(BaseModel):
    choice: str


@router.get("")
def list_notifications(
    unanswered: bool = Query(default=False),
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    q = db.query(models.Notification).filter(models.Notification.household_id == household.id)
    if unanswered:
        q = q.filter(models.Notification.responded_at.is_(None))
    rows = q.order_by(models.Notification.id.desc()).limit(50).all()
    return {"notifications": [notification_row(n) for n in rows]}


@router.post("/{note_id}/respond")
def respond(
    note_id: int,
    body: Respond,
    household: models.Household = Depends(current_household),
    db: Session = Depends(get_db),
):
    """Answer a 'shall we order?' ask: choice 1, 2, 3 places that order; skip closes the ask."""
    note = db.get(models.Notification, note_id)
    if note is None or note.household_id != household.id:
        raise HTTPException(404, "Notification not found")
    try:
        order = proposals.respond(db, household, note, body.choice.strip().lower())
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"notification": notification_row(note), "order": order_row(order) if order else None}


@router.post("/propose")
def propose_now(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    """Run the worker's 'anything to reorder?' check for this household right now."""
    created = proposals.propose_reorders(db, household)
    return {"created": [notification_row(n) for n in created]}
