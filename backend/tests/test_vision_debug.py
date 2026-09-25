"""Dev-only photo capture behind VISION_DEBUG_DIR: on when set (never in production), atomic, remembers the board's IP."""

import json

from app.core.config import get_settings
from app.services import vision_debug

JPEG = b"\xff\xd8\xff\xe0fakejpegbytes"


def _enable(monkeypatch, tmp_path, env="development"):
    monkeypatch.setenv("VISION_DEBUG_DIR", str(tmp_path / "dbg"))
    monkeypatch.setenv("APP_ENV", env)
    get_settings.cache_clear()


def test_disabled_without_setting(monkeypatch, tmp_path):
    monkeypatch.delenv("VISION_DEBUG_DIR", raising=False)
    get_settings.cache_clear()
    assert vision_debug.enabled() is False
    vision_debug.write_latest(JPEG, {"tray_id": 1})
    assert not (tmp_path / "dbg").exists()


def test_debug_disabled_in_production(monkeypatch, tmp_path):
    _enable(monkeypatch, tmp_path, env="production")
    assert vision_debug.enabled() is False
    vision_debug.write_latest(JPEG, {"tray_id": 1})
    assert not (tmp_path / "dbg").exists()


def test_write_and_read_latest(monkeypatch, tmp_path):
    _enable(monkeypatch, tmp_path)
    assert vision_debug.read_latest() is None
    vision_debug.write_latest(JPEG, {"tray_id": 7, "slots": [{"slot": 1, "item": "milk"}]})
    assert (tmp_path / "dbg" / "latest.jpg").read_bytes() == JPEG
    data = json.loads((tmp_path / "dbg" / "latest.json").read_text())
    assert data["tray_id"] == 7 and data["slots"][0]["item"] == "milk" and data["at"].endswith("+00:00")
    assert vision_debug.read_latest() == data


def test_write_latest_is_atomic_no_temp_left(monkeypatch, tmp_path):
    _enable(monkeypatch, tmp_path)
    vision_debug.write_latest(JPEG, {"tray_id": 1})
    vision_debug.write_latest(JPEG + b"2", {"tray_id": 2})
    names = sorted(p.name for p in (tmp_path / "dbg").iterdir())
    assert names == ["latest.jpg", "latest.json"]
    assert vision_debug.read_latest()["tray_id"] == 2


def test_remember_device_ip():
    vision_debug.remember_device_ip(5, "192.168.1.9")
    vision_debug.remember_device_ip(5, None)  # a missing client address must not erase a known one
    assert vision_debug.device_ip(5) == "192.168.1.9"
    assert vision_debug.device_ip(6) is None
