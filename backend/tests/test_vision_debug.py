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
    monkeypatch.setenv("VISION_DEBUG_DIR", "")  # blank = not configured; delenv would let the developer's .env through
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


# ---- debug routes ----

import httpx  # noqa: E402


def test_debug_routes_404_when_disabled(app_client, monkeypatch):
    client, _ = app_client
    monkeypatch.setenv("VISION_DEBUG_DIR", "")  # blank = not configured; delenv would let the developer's .env through
    get_settings.cache_clear()
    for path in ("/vision/debug", "/vision/debug/latest.json", "/vision/debug/latest.jpg", "/vision/debug/weights"):
        assert client.get(path).status_code == 404, path
    assert client.post("/vision/debug/snap").status_code == 404


def test_debug_page_and_latest(app_client, login, monkeypatch, tmp_path):
    client, _ = app_client
    h = _auth(client, login, "page@x.y")
    seeded = client.post("/seed/dev", headers=h).json()
    _enable(monkeypatch, tmp_path)
    page = client.get("/vision/debug")
    assert page.status_code == 200 and "Snap now" in page.text
    assert client.get("/vision/debug/latest.json").status_code == 404

    monkeypatch.setenv("OPENAI_API_KEY", "test")
    get_settings.cache_clear()
    monkeypatch.setattr(vision, "identify", lambda *a, **k: [SlotGuess(1, "curd", 0.9)])
    assert _device_photo(client, seeded["device_token"]).status_code == 200
    assert client.get("/vision/debug/latest.json").json()["slots"][0]["item"] == "curd"
    jpg = client.get("/vision/debug/latest.jpg")
    assert jpg.status_code == 200 and jpg.content == JPEG and jpg.headers["cache-control"] == "no-store"

    client.post(
        "/devices/me/readings",
        json={"readings": [{"tray": 1, "slot": 1, "weight_grams": 123.0}]},
        headers={"Authorization": f"Bearer {seeded['device_token']}"},
    )
    w = client.get("/vision/debug/weights").json()
    assert w["slots"][0]["slot"] == 1 and w["slots"][0]["grams"] == 123.0


def test_snap_without_board_ip_is_502(app_client, monkeypatch, tmp_path):
    client, _ = app_client
    _enable(monkeypatch, tmp_path)
    vision_debug.write_latest(JPEG, {"device_id": 999, "tray_id": 1, "slots": []})
    r = client.post("/vision/debug/snap")
    assert r.status_code == 502 and "board not reachable" in r.json()["detail"]


def test_snap_relays_to_board(app_client, monkeypatch, tmp_path):
    client, _ = app_client
    _enable(monkeypatch, tmp_path)
    vision_debug.write_latest(JPEG, {"device_id": 42, "device_ip": "10.0.0.5", "tray_id": 1, "slots": []})
    vision_debug.remember_device_ip(42, "10.0.0.5")
    calls = []

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return FakeResp()

    monkeypatch.setattr(httpx, "get", fake_get)
    r = client.post("/vision/debug/snap")
    assert r.status_code == 200 and r.json() == {"ok": True, "board": {"ok": True}}
    assert calls == [("http://10.0.0.5/snap", 3.0)]

    def timeout_get(url, timeout):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx, "get", timeout_get)
    r = client.post("/vision/debug/snap")
    assert r.status_code == 502 and "10.0.0.5" in r.json()["detail"]
