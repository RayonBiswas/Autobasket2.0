"""Dev-only viewer for the fridge camera: latest photo + model verdicts + grams, and a "snap now" relay to the board.

Every route answers 404 unless VISION_DEBUG_DIR is set and APP_ENV is not production. No login by design:
this exists on a developer's laptop, never on the VPS.
"""

from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import get_db
from ..services import vision_debug
from ..services.readings import latest_reading

PAGE = Path(__file__).resolve().parent.parent / "static" / "vision_debug.html"
BOARD_TIMEOUT_S = 3.0


def _require_debug() -> None:
    if not vision_debug.enabled():
        raise HTTPException(404, "Not found")


router = APIRouter(dependencies=[Depends(_require_debug)])


def _latest_or_404() -> dict:
    data = vision_debug.read_latest()
    if data is None:
        raise HTTPException(404, "No photo yet. Press Snap now, or wait for the board's next photo")
    return data


def _board_ip(data: dict) -> str:
    ip = vision_debug.device_ip(data.get("device_id") or -1) or data.get("device_ip")
    if not ip:
        raise HTTPException(502, "board not reachable: its address is unknown until it posts a photo")
    return ip


def _board_get(ip: str, path: str) -> dict:
    try:
        r = httpx.get(f"http://{ip}{path}", timeout=BOARD_TIMEOUT_S)
        r.raise_for_status()
        return r.json()
    except Exception as exc:  # noqa: BLE001 - any failure means the same thing to the page
        raise HTTPException(502, f"board not reachable at {ip}: {exc}") from exc


@router.get("", response_class=HTMLResponse)
def page() -> str:
    return PAGE.read_text(encoding="utf-8")


@router.get("/latest.json")
def latest() -> dict:
    return _latest_or_404()


@router.get("/latest.jpg")
def latest_jpg():
    path = vision_debug.debug_dir() / "latest.jpg"
    if not path.exists():
        raise HTTPException(404, "No photo yet")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/weights")
def weights(db: Session = Depends(get_db)) -> dict:
    data = _latest_or_404()
    tray = db.get(models.Tray, data.get("tray_id"))
    if tray is None:
        raise HTTPException(404, "Tray not found")
    out = []
    for slot in tray.slots:
        r = latest_reading(db, slot)
        out.append({"slot": slot.position, "grams": r.weight_grams if r else None, "at": r.recorded_at.isoformat() if r else None})
    return {"tray_id": tray.id, "slots": out}


@router.post("/snap")
def snap() -> dict:
    data = _latest_or_404()
    ip = _board_ip(data)
    return {"ok": True, "board": _board_get(ip, "/snap")}


@router.get("/board")
def board() -> dict:
    data = _latest_or_404()
    return _board_get(_board_ip(data), "/")
