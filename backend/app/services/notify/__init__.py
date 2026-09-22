"""Notifications: one row per thing we told the household, delivered through whichever channels are set up.

The in-app channel is always on (the web app polls unanswered rows). Telegram is added when a bot token is
configured and the household has linked its chat. Both point at the same row, so answering on one side
answers everywhere.
"""

import json
import logging

from sqlalchemy.orm import Session

from ... import models
from ...core.config import get_settings
from ...models.base import utcnow
from .telegram import TelegramBot

log = logging.getLogger("autobasket.notify")

KIND_REORDER = "reorder_offer"
KIND_ORDER = "order_update"


def bot() -> TelegramBot | None:
    s = get_settings()
    return TelegramBot(s.telegram_bot_token) if s.telegram_enabled else None


def send(
    db: Session,
    household: models.Household,
    kind: str,
    title: str,
    body: str,
    payload: dict | None = None,
    buttons: list[tuple[str, str]] | None = None,
    product_id: int | None = None,
) -> models.Notification:
    """Store the notification and push it to Telegram when linked. Commits. Button callback data gets the row id."""
    note = models.Notification(
        household_id=household.id,
        product_id=product_id,
        channel="inapp",
        kind=kind,
        title=title,
        body=body,
        payload=json.dumps(payload or {}),
        sent_at=utcnow(),
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    tg = bot()
    if tg and household.telegram_chat_id:
        keyboard = [(label, f"n:{note.id}:{choice}") for label, choice in (buttons or [])]
        delivered = tg.send_message(household.telegram_chat_id, f"<b>{title}</b>\n{body}", keyboard)
        if delivered:
            note.channel = "inapp+telegram"
            db.commit()
        else:
            log.info("telegram delivery failed for notification %s; in-app copy remains", note.id)
    return note


def payload_of(note: models.Notification) -> dict:
    try:
        return json.loads(note.payload or "{}")
    except json.JSONDecodeError:
        return {}


def notification_row(note: models.Notification) -> dict:
    return {
        "id": note.id,
        "kind": note.kind,
        "channel": note.channel,
        "title": note.title,
        "body": note.body,
        "product_id": note.product_id,
        "payload": payload_of(note),
        "sent_at": note.sent_at.isoformat() if note.sent_at else None,
        "response": note.response,
        "responded_at": note.responded_at.isoformat() if note.responded_at else None,
    }
