"""Names what sits in each slot of a tray from one photo, using an image-capable chat model.

The model only identifies items. Quantity always comes from the load cells. Not configured → None, never a guess.
"""

import base64
import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from .. import models
from ..core.config import get_settings

log = logging.getLogger("autobasket.vision")

MISMATCH_MIN_CONFIDENCE = 0.6
EMPTY_WORDS = {"", "empty", "nothing", "none", "unknown"}

PROMPT = (
    "This is a photo of one shelf of a household fridge. The shelf has {n} slots, numbered 1 to {n} from left to right. "
    "For each slot say which grocery item sits there. Use ONLY names from this list when one fits: {catalog}. "
    'If a slot is empty answer "empty". If you cannot tell, answer "unknown". '
    'Reply with JSON only, exactly like {{"slots":[{{"slot":1,"item":"milk","confidence":0.9}}]}} with one entry per slot '
    "and confidence between 0 and 1."
)


@dataclass
class SlotGuess:
    slot: int
    item: str
    confidence: float
    product_id: int | None = None


# A caller takes (prompt, image_bytes, mime) and returns the model's text. Swappable in tests.
Caller = Callable[[str, bytes, str], str]


def configured() -> bool:
    return get_settings().llm_enabled


def _openai_caller(prompt: str, image: bytes, mime: str) -> str:
    s = get_settings()
    base = s.openai_base_url.rstrip("/")
    model = s.vision_model or s.openai_model
    data_uri = f"data:{mime};base64,{base64.b64encode(image).decode()}"
    body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
    }
    r = httpx.post(
        f"{base}/chat/completions",
        json=body,
        headers={"Authorization": f"Bearer {s.openai_api_key}"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _parse(text: str, slot_count: int) -> list[SlotGuess]:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.strip("`")
        if clean.startswith("json"):
            clean = clean[4:]
    start, end = clean.find("{"), clean.rfind("}")
    data = json.loads(clean[start : end + 1])
    guesses: list[SlotGuess] = []
    for row in data.get("slots", []):
        try:
            slot = int(row.get("slot"))
            if not 1 <= slot <= slot_count:
                continue
            conf = float(row.get("confidence", 0))
            guesses.append(SlotGuess(slot=slot, item=str(row.get("item", "")).strip().lower(), confidence=max(0.0, min(1.0, conf))))
        except (TypeError, ValueError):
            continue
    return guesses


def identify(image: bytes, mime: str, slot_count: int, catalog: list[str], caller: Caller | None = None) -> list[SlotGuess] | None:
    """Ask the model. Returns None when vision is not configured or the call fails (the caller decides what to show)."""
    caller = caller or (_openai_caller if configured() else None)
    if caller is None:
        return None
    prompt = PROMPT.format(n=slot_count, catalog=", ".join(sorted(set(catalog))))
    try:
        return _parse(caller(prompt, image, mime), slot_count)
    except Exception as exc:  # fail soft: a vision outage must not break the door-close flow
        log.warning("vision call failed: %s", exc)
        return None


def match_catalog(item: str, products: list[models.Product]) -> models.Product | None:
    """Exact name first, then a product name contained in the guess ('amul taaza milk 1l' → milk)."""
    needle = item.strip().lower()
    if needle in EMPTY_WORDS:
        return None
    for p in products:
        if p.name.lower() == needle:
            return p
    hits = [p for p in products if p.name.lower() in needle]
    return max(hits, key=lambda p: len(p.name)) if hits else None


def analyze_tray(db: Session, tray: models.Tray, image: bytes, mime: str, caller: Caller | None = None) -> list[dict] | None:
    """Identify every slot, store one VisionResult per answered slot, return the vision blocks. Commits."""
    products = db.query(models.Product).all()
    guesses = identify(image, mime, len(tray.slots), [p.name for p in products], caller=caller)
    if guesses is None:
        return None
    sha = hashlib.sha256(image).hexdigest()
    for g in guesses:
        product = match_catalog(g.item, products)
        g.product_id = product.id if product else None
        db.add(
            models.VisionResult(
                tray_id=tray.id,
                slot_position=g.slot,
                product_guess=g.item[:80],
                matched_product_id=g.product_id,
                confidence=g.confidence,
                image_sha=sha,
            )
        )
    db.commit()
    return [vision_block(db, slot) for slot in tray.slots]


def vision_block(db: Session, slot: models.Slot) -> dict | None:
    """Latest camera answer for one slot, classified against what the household assigned."""
    result = (
        db.query(models.VisionResult)
        .filter_by(tray_id=slot.tray_id, slot_position=slot.position)
        .order_by(models.VisionResult.id.desc())
        .first()
    )
    if result is None:
        return None
    matched = db.get(models.Product, result.matched_product_id) if result.matched_product_id else None
    if matched is None:
        kind = "unknown"
    elif slot.product_id is None:
        kind = "suggestion"
    elif slot.product_id == matched.id:
        kind = "match"
    elif result.confidence >= MISMATCH_MIN_CONFIDENCE:
        kind = "mismatch"
    else:
        kind = "unsure"
    return {
        "item": result.product_guess,
        "confidence": round(result.confidence, 2),
        "matched_product_id": matched.id if matched else None,
        "matched_name": matched.name if matched else None,
        "kind": kind,
        "at": result.created_at.isoformat() if result.created_at else None,
    }
