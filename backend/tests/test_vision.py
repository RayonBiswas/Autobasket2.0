"""Vision: the model names slot contents; the app turns that into suggestions and mismatch alerts."""

import io
import json

from app import models
from app.core.config import get_settings
from app.services import vision
from app.services.vision import SlotGuess, analyze_tray, identify, match_catalog

FAKE_ANSWER = json.dumps({"slots": [
    {"slot": 1, "item": "Amul curd", "confidence": 0.9},
    {"slot": 2, "item": "milk", "confidence": 0.8},
    {"slot": 3, "item": "empty", "confidence": 0.7},
]})
JPEG = b"\xff\xd8\xff\xe0fakejpegbytes"


def _auth(client, login, email):
    return {"Authorization": f"Bearer {login(client, email)}"}


def _seeded_tray(client, h):
    trays = client.get("/households/me/slots", headers=h).json()["trays"]
    return trays[0]


def test_identify_parses_and_fails_soft():
    ok = identify(JPEG, "image/jpeg", 4, ["milk"], caller=lambda p, i, m: "```json\n" + FAKE_ANSWER + "\n```")
    assert [g.slot for g in ok] == [1, 2, 3]
    assert ok[0].item == "amul curd" and ok[0].confidence == 0.9

    def boom(p, i, m):
        raise TimeoutError

    assert identify(JPEG, "image/jpeg", 4, ["milk"], caller=boom) is None


def test_identify_none_when_unconfigured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    assert not vision.configured()
    assert identify(JPEG, "image/jpeg", 4, ["milk"]) is None
    get_settings.cache_clear()


def test_match_catalog():
    products = [models.Product(id=1, name="milk"), models.Product(id=2, name="curd"), models.Product(id=3, name="paneer")]
    assert match_catalog("Amul Taaza milk 1L", products).name == "milk"
    assert match_catalog("CURD", products).name == "curd"
    assert match_catalog("empty", products) is None
    assert match_catalog("tomato", products) is None


def test_analyze_tray_classifies_slots(app_client, login):
    client, factory = app_client
    h = _auth(client, login, "cam@x.y")
    client.post("/seed/dev", headers=h)
    tray_id = _seeded_tray(client, h)["tray_id"]

    with factory() as db:
        tray = db.get(models.Tray, tray_id)
        blocks = analyze_tray(db, tray, JPEG, "image/jpeg", caller=lambda p, i, m: FAKE_ANSWER)
    kinds = [b["kind"] if b else None for b in blocks]
    # Tray 1: milk, rice, water assigned; slot 4 empty.
    assert kinds == ["mismatch", "mismatch", "unknown", None]
    assert blocks[0]["matched_name"] == "curd" and blocks[1]["matched_name"] == "milk"

    # Unassigned slot + a matched guess → suggestion.
    with factory() as db:
        tray = db.get(models.Tray, tray_id)
        tray.slots[3].product_id = None
        db.commit()
        blocks = analyze_tray(db, tray, JPEG, "image/jpeg", caller=lambda p, i, m: json.dumps({"slots": [{"slot": 4, "item": "paneer", "confidence": 0.75}]}))
    assert blocks[3]["kind"] == "suggestion" and blocks[3]["matched_name"] == "paneer"

    # The slot view now carries the block.
    slots = _seeded_tray(client, h)["slots"]
    assert slots[3]["vision"]["kind"] == "suggestion"
    assert slots[0]["vision"]["kind"] == "mismatch"


def test_photo_endpoints(app_client, login, monkeypatch):
    client, _ = app_client
    h = _auth(client, login, "photo@x.y")
    seeded = client.post("/seed/dev", headers=h).json()
    tray = _seeded_tray(client, h)
    files = {"image": ("shelf.jpg", io.BytesIO(JPEG), "image/jpeg")}

    assert client.post(f"/vision/trays/{tray['tray_id']}/photo", files=files, headers=h).status_code == 503

    monkeypatch.setenv("OPENAI_API_KEY", "test")
    get_settings.cache_clear()
    monkeypatch.setattr(vision, "identify", lambda *a, **k: [SlotGuess(1, "curd", 0.9)])
    r = client.post(f"/vision/trays/{tray['tray_id']}/photo", files={"image": ("shelf.jpg", io.BytesIO(JPEG), "image/jpeg")}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["slots"][0]["vision"]["kind"] == "mismatch"

    other = _auth(client, login, "other@x.y")
    assert client.post(f"/vision/trays/{tray['tray_id']}/photo", files={"image": ("s.jpg", io.BytesIO(JPEG), "image/jpeg")}, headers=other).status_code == 404
    assert client.post(f"/vision/trays/{tray['tray_id']}/photo", files={"image": ("s.gif", io.BytesIO(JPEG), "image/gif")}, headers=h).status_code == 415

    dev = {"Authorization": f"Bearer {seeded['device_token']}"}
    r = client.post("/vision/device/trays/1/photo", files={"image": ("s.jpg", io.BytesIO(JPEG), "image/jpeg")}, headers=dev)
    assert r.status_code == 200 and r.json()["position"] == 1
    assert client.post("/vision/device/trays/9/photo", files={"image": ("s.jpg", io.BytesIO(JPEG), "image/jpeg")}, headers=dev).status_code == 404


def test_openai_caller_caps_output(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    get_settings.cache_clear()
    sent: dict = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    def fake_post(url, json, headers, timeout):
        sent.update(json)
        return FakeResponse()

    monkeypatch.setattr(vision.httpx, "post", fake_post)
    assert vision._openai_caller("prompt", JPEG, "image/jpeg") == "{}"
    assert sent["max_tokens"] == 400
    assert sent["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_parse_box_accepts_fractions_and_clamps():
    assert vision._parse_box([0.1, 0.2, 0.3, 0.4]) == (0.1, 0.2, 0.3, 0.4)
    assert vision._parse_box([0.9, 0.9, 0.5, 0.5]) == (0.9, 0.9, 0.1, 0.1)  # clamped to the image edge


def test_parse_box_rejects_bad_shapes():
    for bad in (None, "x", [1, 2], ["a", "b", "c", "d"], [0.1, 0.2, 0, 0.4], [1.5, 0.2, 0.3, 0.4], [0.1, 0.2, 0.3, -0.1]):
        assert vision._parse_box(bad) is None, bad


def test_identify_keeps_optional_box():
    answer = json.dumps({"slots": [
        {"slot": 1, "item": "milk", "confidence": 0.9, "box": [0.05, 0.1, 0.2, 0.6]},
        {"slot": 2, "item": "unknown", "confidence": 0.1},
        {"slot": 3, "item": "eggs", "confidence": 0.8, "box": "nonsense"},
    ]})
    got = identify(JPEG, "image/jpeg", 4, ["milk"], caller=lambda p, i, m: answer)
    assert got[0].box == (0.05, 0.1, 0.2, 0.6)
    assert got[1].box is None
    assert got[2].item == "eggs" and got[2].box is None


def test_prompt_asks_for_boxes_and_stays_strict_in_production(monkeypatch):
    monkeypatch.setenv("VISION_DEBUG_DIR", "")
    get_settings.cache_clear()
    p = vision.build_prompt(4, ["milk"])
    assert '"box"' in p and "0 to 1" in p
    assert "even if the scene does not look like a fridge" not in p


def test_prompt_tolerates_test_scenes_only_with_debug_viewer(monkeypatch, tmp_path):
    monkeypatch.setenv("VISION_DEBUG_DIR", str(tmp_path))
    get_settings.cache_clear()
    assert "even if the scene does not look like a fridge" in vision.build_prompt(4, ["milk"])


def test_analyze_tray_detail_reports_guesses_and_timing(app_client, login):
    client, session_factory = app_client
    h = _auth(client, login, "detail@x.y")
    client.post("/seed/dev", headers=h)
    with session_factory() as db:
        tray = db.query(models.Tray).first()
        result = vision.analyze_tray_detail(db, tray, JPEG, "image/jpeg", caller=lambda p, i, m: FAKE_ANSWER)
        assert result is not None
        assert [g.slot for g in result.guesses] == [1, 2, 3]
        assert result.elapsed_ms >= 0
        assert len(result.blocks) == len(tray.slots)
        assert vision.analyze_tray_detail(db, tray, JPEG, "image/jpeg", caller=lambda p, i, m: "not json") is None
