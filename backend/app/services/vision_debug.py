"""Dev-only capture of the latest analysed photo for the /vision/debug page.

The product never stores photos (only a hash). This module is the one exception, and it is off unless
VISION_DEBUG_DIR is set, and always off in production. Writes are atomic so the page never reads a half file.
"""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ..core.config import get_settings

_device_ips: dict[int, str] = {}


def enabled() -> bool:
    return get_settings().vision_debug_enabled


def debug_dir() -> Path:
    path = Path(get_settings().vision_debug_dir or "")
    path.mkdir(parents=True, exist_ok=True)
    return path


def remember_device_ip(device_id: int, ip: str | None) -> None:
    """The board's address, learned from its own posts; the snap relay needs it."""
    if ip:
        _device_ips[device_id] = ip


def device_ip(device_id: int) -> str | None:
    return _device_ips.get(device_id)


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_latest(image: bytes, meta: dict) -> None:
    """Save latest.jpg and latest.json (meta plus an ISO 'at' timestamp). No-op when disabled."""
    if not enabled():
        return
    folder = debug_dir()
    _atomic_write(folder / "latest.jpg", image)
    payload = {"at": datetime.now(UTC).isoformat(), **meta}
    _atomic_write(folder / "latest.json", json.dumps(payload).encode("utf-8"))


def read_latest() -> dict | None:
    if not enabled():
        return None
    path = debug_dir() / "latest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
