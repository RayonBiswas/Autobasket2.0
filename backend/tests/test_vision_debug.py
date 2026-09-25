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


# ---- capture from the photo routes ----

import io  # noqa: E402

from app.services import vision  # noqa: E402
from app.services.vision import SlotGuess  # noqa: E402


def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def _device_photo(client, token):
    return client.post(
        "/vision/device/trays/1/photo",
        files={"image": ("s.jpg", io.BytesIO(JPEG), "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_device_photo_writes_debug_files(app_client, login, monkeypatch, tmp_path):
    client, _ = app_client
    h = _auth(client, login, "dbg@x.y")
    seeded = client.post("/seed/dev", headers=h).json()
    _enable(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    get_settings.cache_clear()
    monkeypatch.setattr(vision, "identify", lambda *a, **k: [SlotGuess(1, "curd", 0.9, box=(0.1, 0.1, 0.2, 0.5))])

    assert _device_photo(client, seeded["device_token"]).status_code == 200
    data = vision_debug.read_latest()
    assert data["tray_position"] == 1 and data["device_name"] and data["device_id"]
    assert data["device_ip"] == "testclient"
    assert data["model"] and data["provider"]
    first = data["slots"][0]
    assert first["slot"] == 1 and first["item"] == "curd" and first["box"] == [0.1, 0.1, 0.2, 0.5] and first["kind"]
    assert (tmp_path / "dbg" / "latest.jpg").read_bytes() == JPEG
    assert vision_debug.device_ip(data["device_id"]) == "testclient"


def test_debug_files_untouched_when_analysis_fails(app_client, login, monkeypatch, tmp_path):
    client, _ = app_client
    h = _auth(client, login, "dbg2@x.y")
    seeded = client.post("/seed/dev", headers=h).json()
    _enable(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    get_settings.cache_clear()
    monkeypatch.setattr(vision, "identify", lambda *a, **k: None)

    assert _device_photo(client, seeded["device_token"]).status_code == 502
    assert vision_debug.read_latest() is None
