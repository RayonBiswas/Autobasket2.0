from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import SessionLocal

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/")
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):

    existing = db.query(models.Item).filter(models.Item.name == item.name).first()

    if existing:
        existing.total_qty = item.total_qty
        existing.remaining_qty = item.remaining_qty
        existing.min_threshold = item.min_threshold
        existing.last_updated = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return {"message": "Item updated", "id": existing.id}

    new_item = models.Item(
        name=item.name,
        total_qty=item.total_qty,
        remaining_qty=item.remaining_qty,
        min_threshold=item.min_threshold,
        last_updated=datetime.utcnow()
    )

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    return {"message": "Item created", "id": new_item.id}
