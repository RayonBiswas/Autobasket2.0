"""Names what sits in each slot of a tray from one photo, using an image-capable chat model.

The model only identifies items. Quantity always comes from the load cells. Not configured → None, never a guess.
"""

import base64
import hashlib
import time
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
    "If an item from the list is visible anywhere in the photo, name it even if the scene does not look like a fridge. "
    'If a slot is empty answer "empty". If you cannot tell, answer "unknown". '
    'When you name an item also give "box" as [x, y, w, h], fractions of the image from 0 to 1 around that item; '
    'omit "box" for empty or unknown. '
    'Reply with JSON only, exactly like {{"slots":[{{"slot":1,"item":"milk","confidence":0.9,"box":[0.05,0.1,0.2,0.6]}}]}} '
    "with one entry per slot and confidence between 0 and 1."
)


Box = tuple[float, float, float, float]


@dataclass
class SlotGuess:
    slot: int
    item: str
    confidence: float
    product_id: int | None = None
    box: Box | None = None  # x, y, w, h as fractions of the image; viewer-only, never stored


@dataclass
class Analysis:
    blocks: list[dict]
    guesses: list[SlotGuess]
    elapsed_ms: int


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
        "max_tokens": 400,  # the answer is short JSON; without a cap some gateways reserve the model's whole budget
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


def _parse_box(raw) -> Box | None:
    """[x, y, w, h] as fractions of the image. Anything malformed becomes None; boxes are clamped to the image."""
    try:
        x, y, w, h = (float(v) for v in raw)
    except (TypeError, ValueError):
        return None
    if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
        return None
    return (round(x, 4), round(y, 4), round(min(w, 1 - x), 4), round(min(h, 1 - y), 4))


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
            guesses.append(
                SlotGuess(
                    slot=slot,
                    item=str(row.get("item", "")).strip().lower(),
                    confidence=max(0.0, min(1.0, conf)),
                    box=_parse_box(row.get("box")),
                )
            )
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
    except Exception as exc:  # fail soft: a vision outage must not break the photo flow
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


def analyze_tray_detail(db: Session, tray: models.Tray, image: bytes, mime: str, caller: Caller | None = None) -> Analysis | None:
    """Identify every slot, store one VisionResult per answered slot, return blocks + raw guesses + timing. Commits."""
    products = db.query(models.Product).all()
    started = time.monotonic()
    guesses = identify(image, mime, len(tray.slots), [p.name for p in products], caller=caller)
    elapsed_ms = int((time.monotonic() - started) * 1000)
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
    return Analysis(blocks=[vision_block(db, slot) for slot in tray.slots], guesses=guesses, elapsed_ms=elapsed_ms)


def analyze_tray(db: Session, tray: models.Tray, image: bytes, mime: str, caller: Caller | None = None) -> list[dict] | None:
    """Blocks only; what the routes and older callers use."""
    result = analyze_tray_detail(db, tray, image, mime, caller=caller)
    return None if result is None else result.blocks


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
