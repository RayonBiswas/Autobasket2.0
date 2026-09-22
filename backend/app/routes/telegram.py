"""Telegram: link a household to a chat, and receive button taps through the bot webhook."""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_household, get_db
from ..core.config import get_settings
from ..services import proposals
from ..services.notify import bot
from ..services.notify.telegram import parse_update

router = APIRouter()


@router.get("/link")
def link_status(household: models.Household = Depends(current_household)):
    s = get_settings()
    return {
        "enabled": s.telegram_enabled,
        "connected": bool(household.telegram_chat_id),
        "bot_username": s.telegram_bot_username,
    }


@router.post("/link")
def start_link(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    """Hand out a one-time code; the user sends /start <code> to the bot and the webhook completes the link."""
    s = get_settings()
    if not s.telegram_enabled:
        raise HTTPException(409, "Telegram alerts are not set up on this server yet")
    code = secrets.token_hex(4)
    household.telegram_link_code = code
    db.commit()
    url = f"https://t.me/{s.telegram_bot_username}?start={code}" if s.telegram_bot_username else None
    return {"code": code, "url": url}


@router.delete("/link", status_code=204)
def unlink(household: models.Household = Depends(current_household), db: Session = Depends(get_db)):
    household.telegram_chat_id = None
    household.telegram_link_code = None
    db.commit()


@router.post("/webhook")
async def webhook(
    request: Request,
    db: Session = Depends(get_db),
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
):
    s = get_settings()
    if s.telegram_webhook_secret and secret != s.telegram_webhook_secret:
        raise HTTPException(403, "Bad webhook secret")
    update = await request.json()
    kind, chat_id, data, callback_id = parse_update(update)
    tg = bot()

    if kind == "start":
        household = db.query(models.Household).filter(models.Household.telegram_link_code == data).first() if data else None
        if household is None:
            if tg:
                tg.send_message(chat_id, "Open AutoBasket → Settings → Alerts on Telegram to get a link code.")
            return {"ok": True, "linked": False}
        household.telegram_chat_id = chat_id
        household.telegram_link_code = None
        db.commit()
        if tg:
            tg.send_message(chat_id, f"Linked to {household.name}. You'll hear from me when something runs low.")
        return {"ok": True, "linked": True}

    if kind == "callback" and data.startswith("n:"):
        _, note_id, choice = data.split(":", 2)
        note = db.get(models.Notification, int(note_id))
        household = db.get(models.Household, note.household_id) if note else None
        if note is None or household is None or household.telegram_chat_id != chat_id:
            if tg and callback_id:
                tg.answer_callback(callback_id, "That one isn't yours.")
            return {"ok": True}
        try:
            order = proposals.respond(db, household, note, choice)
        except ValueError as exc:
            if tg and callback_id:
                tg.answer_callback(callback_id, str(exc))
            return {"ok": True}
        if tg:
            if order is None:
                tg.answer_callback(callback_id, "Skipped.")
            elif order.payment_url:
                tg.answer_callback(callback_id, "Ordered!")
                tg.send_message(chat_id, f"Ordered from {order.vendor.name} for ₹{order.total_amount}. Pay here: {order.payment_url}")
            else:
                tg.answer_callback(callback_id, "Opening the app link.")
                tg.send_message(chat_id, f"Finish in the app: {order.handoff_url}")
        return {"ok": True, "order_id": order.id if order else None}

    return {"ok": True}
