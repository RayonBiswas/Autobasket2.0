# Live Vision Viewer + Provider Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A dev-only page that shows the fridge camera's latest photo with browser-side detector boxes, the model's per-slot verdicts and live grams, with a "snap now" trigger on the board; plus a one-line provider switch (NIM / Gemini / Groq / OpenRouter).

**Architecture:** The board gains a tiny HTTP listener (`GET /snap`) that fires the normal readings+photo post. The backend keeps its vision path but, when `VISION_DEBUG_DIR` is set (never in production), also writes `latest.jpg` + `latest.json` after each analysis and serves them, the page, latest grams and a snap relay under `/vision/debug`. The page is one static HTML file that draws COCO-SSD boxes in the browser and overlays the model's slot verdicts.

**Tech Stack:** FastAPI + SQLAlchemy (backend, Python 3.12, pytest), plain HTML/JS with TensorFlow.js + coco-ssd from jsDelivr, ESP32 Arduino core (`WebServer`), PlatformIO, httpx.

**Spec:** `docs/superpowers/specs/2026-09-25-live-vision-viewer-design.md`

## Global Constraints

- Tests never call a real model: the autouse fixture blanks `OPENAI_API_KEY`; stub `vision.identify` or pass `caller=`.
- The product never stores photos; `latest.jpg` exists only under `VISION_DEBUG_DIR`, and only when `APP_ENV` is not `production`.
- Boxes are never written to the database; no Alembic migration in this plan.
- Firmware must compile with both the PlatformIO ESP32 core (2.0.x) and CI's arduino-cli core (3.x); use only `WebServer.h` from the core.
- Debug routes are unauthenticated by design and must answer 404 whenever debug is disabled.
- Run backend tests from `backend/` with `../.venv/Scripts/python.exe -m pytest`.
- Commit after every task; commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. Model returns `box` with strings, wrong length or values outside 0–1 → the guess keeps its item and the box becomes `None`; no exception. (Task 2 test `test_parse_box_rejects_bad_shapes`)
2. The model call fails while debug is on → the route returns 502 and `latest.json` is left untouched, so the page never shows a verdict for a photo that was not analysed. (Task 4 test `test_debug_files_untouched_when_analysis_fails`)
3. Snap pressed after the API restarted and before the board has posted → 502 with "board not reachable", not a 500. (Task 5 test `test_snap_without_board_ip_is_502`)
4. `VISION_DEBUG_DIR` set with `APP_ENV=production` → routes 404 and no files written. (Task 3 test `test_debug_disabled_in_production`, Task 5 test `test_debug_routes_404_when_disabled`)
5. Page reads `latest.json` while it is being rewritten → atomic replace means it sees either the old or the new complete file. (Task 3 test `test_write_latest_is_atomic_no_temp_left`)

---

### Task 1: Output cap, provider blocks, smoke script

**Files:**
- Modify: `backend/app/services/vision.py:49-75` (`_openai_caller`)
- Create: `backend/scripts/vision_smoke.py`
- Modify: `.env.example:16-22`
- Modify: `README.md` (vision section near line 131)
- Test: `backend/tests/test_vision.py`

**Interfaces:**
- Consumes: `vision._openai_caller(prompt, image, mime) -> str`, `get_settings()`.
- Produces: `_openai_caller` sends `max_tokens: 400`; `scripts/vision_smoke.py <photo> [slots] [catalog]` CLI.

- [ ] **Step 1: Write the failing test** (append to `backend/tests/test_vision.py`)

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_vision.py::test_openai_caller_caps_output -v`
Expected: FAIL with `KeyError: 'max_tokens'`

- [ ] **Step 3: Add the cap** in `_openai_caller`'s `body` dict, after `"temperature": 0,`:

```python
        "max_tokens": 400,  # the answer is short JSON; without a cap some gateways reserve the model's whole budget
```

- [ ] **Step 4: Run the vision tests**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_vision.py -v`
Expected: all PASS

- [ ] **Step 5: Create `backend/scripts/vision_smoke.py`**

```python
"""Send one photo through the configured vision provider and print the raw answer.

Usage, from backend/:
    ../.venv/Scripts/python.exe scripts/vision_smoke.py path/to/photo.jpg [slots] [catalog,comma,separated]
Reads the same .env the API uses, so it tests exactly the active provider block.
"""

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.services import vision  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    image = pathlib.Path(sys.argv[1]).read_bytes()
    slots = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    catalog = sys.argv[3].replace(",", ", ") if len(sys.argv) > 3 else ""
    s = get_settings()
    if not s.llm_enabled:
        print("No OPENAI_API_KEY in .env; nothing to test.")
        return 1
    print(f"provider: {s.openai_base_url}\nmodel:    {s.vision_model or s.openai_model}")
    started = time.time()
    try:
        raw = vision._openai_caller(vision.PROMPT.format(n=slots, catalog=catalog), image, "image/jpeg")
    except Exception as exc:  # noqa: BLE001 - this script exists to show the failure
        print(f"FAILED after {time.time() - started:.1f}s: {exc}")
        return 1
    print(f"answered in {time.time() - started:.1f}s:\n{raw}\n")
    for g in vision._parse(raw, slots):
        print(f"  slot {g.slot}: {g.item} ({g.confidence:.2f})" + (f" box={g.box}" if getattr(g, 'box', None) else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run the script against the active provider**

Run: `cd backend && ../.venv/Scripts/python.exe scripts/vision_smoke.py "%USERPROFILE%/Desktop/fridge-cam-photos/shelf.jpg" 4 "water bottle,milk,eggs,butter"`
Expected: prints provider, model, a JSON answer and per-slot lines (exit 0).

- [ ] **Step 7: Replace the LLM block in `.env.example`** (lines 16–22) with:

```
# --- Vision + chat provider: any OpenAI-compatible endpoint. Keep exactly ONE block active. ---
LLM_PROVIDER=openai

# NVIDIA NIM (demo)                        key: build.nvidia.com -> any model -> Get API Key
OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
OPENAI_API_KEY=nvapi-paste-here
VISION_MODEL=meta/llama-3.2-11b-vision-instruct
OPENAI_MODEL=meta/llama-3.2-11b-vision-instruct

# Google Gemini (practice, free tier)      key: aistudio.google.com
# OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
# OPENAI_API_KEY=paste-gemini-key
# VISION_MODEL=gemini-3.8-flash
# OPENAI_MODEL=gemini-3.8-flash

# Groq (practice, free tier)               key: console.groq.com
# OPENAI_BASE_URL=https://api.groq.com/openai/v1
# OPENAI_API_KEY=paste-groq-key
# VISION_MODEL=qwen/qwen3.6-27b
# OPENAI_MODEL=qwen/qwen3.6-27b

# OpenRouter (paid)
# OPENAI_BASE_URL=https://openrouter.ai/api/v1
# OPENAI_API_KEY=sk-or-paste-here
# VISION_MODEL=openai/gpt-4o-mini
# OPENAI_MODEL=openai/gpt-4o-mini

# No key at all: the chat agent falls back to Ollama (OLLAMA_MODEL) and the camera is disabled.
# OLLAMA_MODEL=llama3.1:8b
```

- [ ] **Step 8: Add a README subsection** right after the paragraph that starts "Weights say *how much* is left" (around line 131):

```markdown
#### Choosing a vision provider

`.env.example` carries four ready blocks — NVIDIA NIM (demo), Google Gemini and Groq (free tiers for practice) and
OpenRouter. Uncomment exactly one, restart the API. All four use the same prompt and code, so practice results
predict demo results. Check any block with one photo:

```powershell
cd backend
..\.venv\Scripts\python.exe scripts\vision_smoke.py path\to\shelf.jpg 4 "milk,eggs,butter,paneer"
```
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/vision.py backend/scripts/vision_smoke.py backend/tests/test_vision.py .env.example README.md
git commit -m "feat(vision): cap model output, provider blocks in .env.example, vision_smoke script

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Rough boxes and timing in the vision service

**Files:**
- Modify: `backend/app/services/vision.py` (PROMPT lines 24-31, `SlotGuess` 34-39, `_parse` 77-95, `analyze_tray` 123-145)
- Test: `backend/tests/test_vision.py`

**Interfaces:**
- Produces: `SlotGuess.box: tuple[float, float, float, float] | None` (x, y, w, h as fractions); `_parse_box(raw) -> tuple | None`; `@dataclass Analysis(blocks: list[dict], guesses: list[SlotGuess], elapsed_ms: int)`; `analyze_tray_detail(db, tray, image, mime, caller=None) -> Analysis | None`. `analyze_tray` keeps its signature and return.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_vision.py`)

```python
def test_parse_box_accepts_fractions_and_clamps():
    assert vision._parse_box([0.1, 0.2, 0.3, 0.4]) == (0.1, 0.2, 0.3, 0.4)
    assert vision._parse_box([0.9, 0.9, 0.5, 0.5]) == (0.9, 0.9, 0.1, 0.1)   # clamped to the image edge


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


def test_prompt_asks_for_boxes_and_tolerates_non_fridge_scenes():
    p = vision.PROMPT.format(n=4, catalog="milk")
    assert '"box"' in p and "0 to 1" in p
    assert "even if the scene does not look like a fridge" in p


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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_vision.py -k "box or prompt_asks or detail" -v`
Expected: FAIL (`AttributeError: module 'app.services.vision' has no attribute '_parse_box'`, etc.)

- [ ] **Step 3: Implement.** In `backend/app/services/vision.py`:

Replace the `PROMPT` constant with:

```python
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
```

Replace the `SlotGuess` dataclass with:

```python
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
```

Add `_parse_box` above `_parse`, and use it inside `_parse`:

```python
def _parse_box(raw) -> Box | None:
    """[x, y, w, h] as fractions of the image. Anything malformed becomes None; boxes are clamped to the image."""
    try:
        x, y, w, h = (float(v) for v in raw)
    except (TypeError, ValueError):
        return None
    if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
        return None
    return (x, y, min(w, 1 - x), min(h, 1 - y))
```

In `_parse`, change the `guesses.append(...)` line to:

```python
            guesses.append(
                SlotGuess(
                    slot=slot,
                    item=str(row.get("item", "")).strip().lower(),
                    confidence=max(0.0, min(1.0, conf)),
                    box=_parse_box(row.get("box")),
                )
            )
```

Replace `analyze_tray` with:

```python
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
```

Add `import time` to the imports at the top of the file.

- [ ] **Step 4: Run all vision tests**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_vision.py -v`
Expected: all PASS (old tests untouched)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/vision.py backend/tests/test_vision.py
git commit -m "feat(vision): optional rough box per slot, analysis timing, prompt tolerant of test scenes

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Debug setting and capture service

**Files:**
- Modify: `backend/app/core/config.py` (add field after `vision_model` line 52; add property near `llm_enabled` line 67)
- Create: `backend/app/services/vision_debug.py`
- Create: `backend/tests/test_vision_debug.py`

**Interfaces:**
- Produces: `Settings.vision_debug_dir: str | None`, `Settings.vision_debug_enabled: bool`; module `vision_debug` with `enabled() -> bool`, `debug_dir() -> Path`, `write_latest(image: bytes, meta: dict) -> None`, `read_latest() -> dict | None`, `remember_device_ip(device_id: int, ip: str | None) -> None`, `device_ip(device_id: int) -> str | None`.

- [ ] **Step 1: Write the failing tests** (`backend/tests/test_vision_debug.py`)

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_vision_debug.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.vision_debug'`

- [ ] **Step 3: Add the setting.** In `backend/app/core/config.py`, after the `vision_model` line add:

```python
    # Dev-only: when set (and not production) the API keeps the latest analysed photo here and serves /vision/debug.
    vision_debug_dir: str | None = None
```

and after the `llm_enabled` property add:

```python
    @property
    def vision_debug_enabled(self) -> bool:
        return bool(self.vision_debug_dir) and not self.is_production
```

- [ ] **Step 4: Create `backend/app/services/vision_debug.py`**

```python
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
```

- [ ] **Step 5: Run the tests**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_vision_debug.py -v`
Expected: 5 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py backend/app/services/vision_debug.py backend/tests/test_vision_debug.py
git commit -m "feat(vision): VISION_DEBUG_DIR setting and atomic latest-photo capture service (dev only)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Capture from the photo routes

**Files:**
- Modify: `backend/app/routes/vision.py` (`_analyze` 28-39, `household_photo` 41-58, `device_photo` 61-70)
- Test: `backend/tests/test_vision_debug.py`

**Interfaces:**
- Consumes: `vision.analyze_tray_detail`, `vision_debug.write_latest`, `vision_debug.remember_device_ip`.
- Produces: `latest.json` shape: `{at, device_id, device_name, device_ip, tray_id, tray_position, model, provider, elapsed_ms, slots:[{slot, item, confidence, kind, matched_name, box}]}`.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_vision_debug.py`)

```python
import io

from app.services import vision
from app.services.vision import SlotGuess


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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_vision_debug.py -k "device_photo or untouched" -v`
Expected: `test_device_photo_writes_debug_files` FAILS (`read_latest()` is None); the other passes already (that is fine: it pins behaviour).

- [ ] **Step 3: Implement.** In `backend/app/routes/vision.py`:

Change the imports to:

```python
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from .. import models
from ..api.deps import current_device, current_household, get_db
from ..core.config import get_settings
from ..services import vision, vision_debug
```

Replace `_analyze` with:

```python
def _analyze(db: Session, tray: models.Tray, data: bytes, mime: str, device_ip: str | None = None) -> dict:
    if not vision.configured():
        raise HTTPException(503, "Vision is not set up on this server: set OPENAI_API_KEY (and VISION_MODEL) to enable it")
    result = vision.analyze_tray_detail(db, tray, data, mime)
    if result is None:
        raise HTTPException(502, "The vision model didn't answer. Try again in a moment")
    _capture(db, tray, data, result, device_ip)
    return {
        "tray_id": tray.id,
        "position": tray.position,
        "slots": [
            {"slot_id": s.id, "position": s.position, "product_id": s.product_id, "vision": b}
            for s, b in zip(tray.slots, result.blocks, strict=True)
        ],
    }


def _capture(db: Session, tray: models.Tray, data: bytes, result: vision.Analysis, device_ip: str | None) -> None:
    """Dev-only: keep this photo and verdict for the /vision/debug page."""
    if not vision_debug.enabled():
        return
    s = get_settings()
    device = db.get(models.Device, tray.device_id)
    by_slot = {g.slot: g for g in result.guesses}
    slots = []
    for slot, block in zip(tray.slots, result.blocks, strict=True):
        guess = by_slot.get(slot.position)
        slots.append(
            {
                "slot": slot.position,
                "item": block["item"] if block else None,
                "confidence": block["confidence"] if block else None,
                "kind": block["kind"] if block else None,
                "matched_name": block["matched_name"] if block else None,
                "box": list(guess.box) if guess and guess.box else None,
            }
        )
    vision_debug.write_latest(
        data,
        {
            "device_id": device.id if device else None,
            "device_name": device.name if device else None,
            "device_ip": device_ip,
            "tray_id": tray.id,
            "tray_position": tray.position,
            "model": s.vision_model or s.openai_model,
            "provider": urlparse(s.openai_base_url).netloc,
            "elapsed_ms": result.elapsed_ms,
            "slots": slots,
        },
    )
```

In `device_photo`, add `request: Request,` as the first parameter after `position: int,` and replace the last two lines with:

```python
    data, mime = await _read_image(image)
    ip = request.client.host if request.client else None
    vision_debug.remember_device_ip(device.id, ip)
    return _analyze(db, tray, data, mime, device_ip=ip)
```

`household_photo` is unchanged (it already calls `_analyze(db, tray, data, mime)`; phone photos are captured too, with `device_ip=None`).

- [ ] **Step 4: Run the whole backend suite**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/vision.py backend/tests/test_vision_debug.py
git commit -m "feat(vision): photo routes write the debug capture and remember the board's IP

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Debug routes: page, latest files, weights, snap relay

**Files:**
- Create: `backend/app/routes/vision_debug.py`
- Create: `backend/app/static/vision_debug.html` (placeholder page in this task; real page in Task 6)
- Modify: `backend/app/main.py` (import list lines 7-21, router list line 59, lifespan lines 27-30)
- Test: `backend/tests/test_vision_debug.py`

**Interfaces:**
- Consumes: `vision_debug.read_latest/debug_dir/device_ip`, `readings.latest_reading(db, slot)`.
- Produces: `GET /vision/debug` (HTML), `GET /vision/debug/latest.json`, `GET /vision/debug/latest.jpg`, `GET /vision/debug/weights -> {"tray_id", "slots": [{"slot", "grams", "at"}]}`, `POST /vision/debug/snap -> {"ok": true, "board": <board json>}`, `GET /vision/debug/board -> <board json>`. All 404 when debug is disabled.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_vision_debug.py`)

```python
import httpx


def test_debug_routes_404_when_disabled(app_client, monkeypatch):
    client, _ = app_client
    monkeypatch.delenv("VISION_DEBUG_DIR", raising=False)
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
        json={"readings": [{"tray_position": 1, "slot_position": 1, "weight_grams": 123.0}]},
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
```

Check the readings payload shape first: `rtk proxy grep -n -A6 "class ReadingIn" backend/app/routes/devices.py`. If the field names differ from `tray_position` / `slot_position` / `weight_grams`, use the real ones in the test.

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_vision_debug.py -k "routes_404 or page_and_latest or snap" -v`
Expected: FAIL (404s where 200 expected, `test_debug_routes_404_when_disabled` passes already)

- [ ] **Step 3: Create `backend/app/routes/vision_debug.py`**

```python
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
```

- [ ] **Step 4: Placeholder page** `backend/app/static/vision_debug.html` (Task 6 replaces it):

```html
<!doctype html><title>Fridge camera</title><h1>Fridge camera</h1><button>Snap now</button>
```

- [ ] **Step 5: Wire it in `backend/app/main.py`.** Add `vision_debug,` to the `from .routes import (...)` list (alphabetical, after `vision`). After the `vision.router` line add:

```python
app.include_router(vision_debug.router, prefix="/vision/debug", tags=["Vision debug"])
```

In `lifespan`, after `validate_production(get_settings())` add:

```python
    s = get_settings()
    if s.vision_debug_dir and s.is_production:
        logging.getLogger("autobasket").warning("VISION_DEBUG_DIR is set but ignored in production")
```

and add `import logging` at the top.

- [ ] **Step 6: Run the whole backend suite**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest -q`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/vision_debug.py backend/app/static/vision_debug.html backend/app/main.py backend/tests/test_vision_debug.py
git commit -m "feat(vision): /vision/debug routes: page, latest photo+verdict, grams, snap relay (dev only)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: The viewer page

**Files:**
- Modify: `backend/app/static/vision_debug.html` (replace the placeholder)
- Modify: `README.md` (after the "Choosing a vision provider" subsection from Task 1)

**Interfaces:**
- Consumes: the five routes from Task 5 and the `latest.json` shape from Task 4.
- Produces: `window.detectors` registry; `detectors.cocossd = { name, load(), detect(img) -> [{label, score, box:[x,y,w,h]}] }` with box in pixels of the drawn image.

- [ ] **Step 1: Write the page**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fridge camera</title>
<style>
  :root { --bg:#f6f8f4; --ink:#1d2a1f; --muted:#5f6f63; --leaf:#2f8f4e; --sky:#2b6fd6; --warn:#b5541b; --card:#fff; }
  @media (prefers-color-scheme: dark) { :root { --bg:#131a15; --ink:#e8efe9; --muted:#9db3a3; --card:#1b241d; } }
  body { margin:0; font:15px/1.4 system-ui, sans-serif; background:var(--bg); color:var(--ink); }
  header { display:flex; flex-wrap:wrap; gap:12px 20px; align-items:center; padding:12px 16px; background:var(--card); }
  header b { font-size:17px; }
  header .meta { color:var(--muted); font-size:13px; }
  main { padding:16px; display:grid; gap:16px; grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr); }
  @media (max-width: 900px) { main { grid-template-columns: 1fr; } }
  .stage { position:relative; background:#000; border-radius:8px; overflow:hidden; aspect-ratio: 4 / 3; }
  .stage img, .stage canvas { position:absolute; inset:0; width:100%; height:100%; }
  .stage img { object-fit:contain; }
  .panel { background:var(--card); border-radius:8px; padding:14px; }
  button { font:inherit; padding:8px 14px; border-radius:6px; border:1px solid var(--leaf); background:var(--leaf); color:#fff; cursor:pointer; }
  button.secondary { background:transparent; color:var(--ink); border-color:var(--muted); }
  button:disabled { opacity:.5; cursor:default; }
  label { margin-right:12px; white-space:nowrap; }
  table { width:100%; border-collapse:collapse; margin-top:8px; }
  td, th { text-align:left; padding:6px 4px; border-bottom:1px solid rgba(128,128,128,.25); }
  .kind-match { color:var(--leaf); } .kind-mismatch { color:var(--warn); } .kind-unknown, .kind-suggestion { color:var(--muted); }
  #banner { display:none; padding:8px 12px; border-radius:6px; background:#fbe9e0; color:#7a2e00; margin-bottom:10px; }
  #banner.show { display:block; }
</style>
</head>
<body>
<header>
  <b>Fridge camera</b>
  <span class="meta" id="provider">provider: –</span>
  <span class="meta" id="timing">model: –</span>
  <span class="meta" id="board">board: –</span>
  <span class="meta" id="calls">model calls this page: 0</span>
</header>
<main>
  <div>
    <div id="banner"></div>
    <div class="stage"><img id="photo" alt="latest shelf photo"><canvas id="overlay"></canvas></div>
  </div>
  <div class="panel">
    <div>
      <button id="snap">Snap now</button>
      <button class="secondary" id="auto" data-every="0">Auto: off</button>
    </div>
    <div style="margin-top:10px">
      <label><input type="checkbox" id="layerDet" checked> detector boxes</label>
      <label><input type="checkbox" id="layerModel" checked> model verdicts</label>
      <label><input type="checkbox" id="layerGrams" checked> grams</label>
    </div>
    <div style="margin-top:6px" class="meta" id="detStatus">detector: loading…</div>
    <table id="slots"><thead><tr><th>slot</th><th>model says</th><th>conf.</th><th>kind</th><th>grams</th></tr></thead><tbody></tbody></table>
    <p class="meta" id="photoAt">no photo yet</p>
  </div>
</main>

<script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.20.0/dist/tf.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.3/dist/coco-ssd.min.js"></script>
<script>
// ---- detector plug-ins: each is { name, load(), detect(img) -> [{label, score, box:[x,y,w,h] in image pixels}] } ----
window.detectors = {
  cocossd: {
    name: "COCO-SSD (browser)",
    model: null,
    async load() { this.model = await cocoSsd.load(); },
    async detect(img) {
      const preds = await this.model.detect(img);
      return preds.map(p => ({ label: p.class, score: p.score, box: p.bbox }));
    },
  },
};
const detector = window.detectors.cocossd;

const $ = id => document.getElementById(id);
const img = $("photo"), canvas = $("overlay"), ctx = canvas.getContext("2d");
let latest = null, grams = {}, detections = [], calls = 0, autoTimer = null;

function banner(msg) { const b = $("banner"); b.textContent = msg || ""; b.classList.toggle("show", !!msg); }

// Map image pixels to the drawn (object-fit: contain) rectangle inside the stage.
function fitRect() {
  const W = canvas.width, H = canvas.height, iw = img.naturalWidth || 4, ih = img.naturalHeight || 3;
  const s = Math.min(W / iw, H / ih), w = iw * s, h = ih * s;
  return { x: (W - w) / 2, y: (H - h) / 2, w, h, s };
}

function draw() {
  const stage = canvas.parentElement;
  canvas.width = stage.clientWidth; canvas.height = stage.clientHeight;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!latest) return;
  const r = fitRect();
  ctx.lineWidth = 2; ctx.font = "14px system-ui";

  if ($("layerModel").checked) {
    const n = latest.slots.length || 1, bw = r.w / n;
    latest.slots.forEach((s, i) => {
      const x = r.x + i * bw;
      ctx.strokeStyle = "rgba(43,111,214,.6)"; ctx.setLineDash([6, 4]); ctx.strokeRect(x, r.y, bw, r.h); ctx.setLineDash([]);
      const text = `${s.slot}: ${s.item ?? "–"}` + (s.confidence != null ? ` ${Math.round(s.confidence * 100)}%` : "");
      ctx.fillStyle = "rgba(43,111,214,.85)"; ctx.fillRect(x + 4, r.y + 4, ctx.measureText(text).width + 10, 20);
      ctx.fillStyle = "#fff"; ctx.fillText(text, x + 9, r.y + 19);
      if (s.box) {
        const [bx, by, bwid, bh] = s.box;
        ctx.strokeStyle = "#2b6fd6"; ctx.strokeRect(r.x + bx * r.w, r.y + by * r.h, bwid * r.w, bh * r.h);
      }
    });
  }
  if ($("layerDet").checked) {
    detections.forEach(d => {
      const [x, y, w, h] = d.box;
      const X = r.x + x * r.s, Y = r.y + y * r.s, Wd = w * r.s, Hd = h * r.s;
      ctx.strokeStyle = "#2f8f4e"; ctx.strokeRect(X, Y, Wd, Hd);
      const text = `${d.label} ${Math.round(d.score * 100)}%`;
      ctx.fillStyle = "rgba(47,143,78,.9)"; ctx.fillRect(X, Y + Hd - 20, ctx.measureText(text).width + 10, 20);
      ctx.fillStyle = "#fff"; ctx.fillText(text, X + 5, Y + Hd - 5);
    });
  }
  if ($("layerGrams").checked) {
    const n = latest.slots.length || 1, bw = r.w / n;
    latest.slots.forEach((s, i) => {
      const g = grams[s.slot];
      if (g == null) return;
      const text = `${Math.round(g)} g`;
      ctx.fillStyle = "rgba(0,0,0,.65)"; ctx.fillRect(r.x + i * bw + 4, r.y + r.h - 26, ctx.measureText(text).width + 10, 22);
      ctx.fillStyle = "#fff"; ctx.fillText(text, r.x + i * bw + 9, r.y + r.h - 10);
    });
  }
}

function renderTable() {
  const tb = $("slots").querySelector("tbody"); tb.innerHTML = "";
  (latest?.slots || []).forEach(s => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${s.slot}</td><td>${s.item ?? "–"}${s.matched_name ? ` → ${s.matched_name}` : ""}</td>` +
      `<td>${s.confidence != null ? Math.round(s.confidence * 100) + "%" : "–"}</td>` +
      `<td class="kind-${s.kind ?? "unknown"}">${s.kind ?? "–"}</td><td>${grams[s.slot] != null ? Math.round(grams[s.slot]) + " g" : "–"}</td>`;
    tb.appendChild(tr);
  });
}

async function refreshGrams() {
  try {
    const w = await (await fetch("/vision/debug/weights")).json();
    grams = Object.fromEntries((w.slots || []).map(s => [s.slot, s.grams]));
  } catch { grams = {}; }
}

async function refreshBoard() {
  try {
    const r = await fetch("/vision/debug/board");
    const b = await r.json();
    $("board").textContent = r.ok ? `board: ${b.ip} · wifi ${b.wifi} · up ${Math.round(b.uptime_s / 60)} min` : `board: ${b.detail}`;
  } catch { $("board").textContent = "board: –"; }
}

async function poll() {
  try {
    const r = await fetch("/vision/debug/latest.json", { cache: "no-store" });
    if (r.status === 404) { $("photoAt").textContent = "no photo yet – press Snap now"; return; }
    const data = await r.json();
    if (!latest || data.at !== latest.at) {
      latest = data;
      $("provider").textContent = `provider: ${data.provider} · ${data.model}`;
      $("timing").textContent = `model: ${data.elapsed_ms} ms`;
      $("photoAt").textContent = `photo at ${new Date(data.at).toLocaleTimeString()} · tray ${data.tray_position} · ${data.device_name ?? ""}`;
      await new Promise(res => { img.onload = res; img.src = `/vision/debug/latest.jpg?t=${encodeURIComponent(data.at)}`; });
      detections = [];
      if (detector.model) { try { detections = await detector.detect(img); } catch (e) { console.warn(e); } }
      await refreshGrams();
      renderTable(); draw();
    }
  } catch (e) { console.warn(e); }
}

async function snap() {
  $("snap").disabled = true; banner("");
  try {
    const r = await fetch("/vision/debug/snap", { method: "POST" });
    const b = await r.json();
    if (!r.ok) banner(b.detail || "snap failed"); else { calls++; $("calls").textContent = `model calls this page: ${calls}`; }
  } catch (e) { banner(String(e)); }
  setTimeout(() => { $("snap").disabled = false; }, 4000);
}

$("snap").onclick = snap;
$("auto").onclick = () => {
  const steps = [0, 5, 10, 30];
  const cur = Number($("auto").dataset.every), next = steps[(steps.indexOf(cur) + 1) % steps.length];
  $("auto").dataset.every = next; $("auto").textContent = next ? `Auto: every ${next} s` : "Auto: off";
  clearInterval(autoTimer); if (next) autoTimer = setInterval(snap, next * 1000);
};
["layerDet", "layerModel", "layerGrams"].forEach(id => $(id).onchange = draw);
window.addEventListener("resize", draw);

(async () => {
  try { await detector.load(); $("detStatus").textContent = `detector: ${detector.name} ready`; if (latest) { detections = await detector.detect(img); draw(); } }
  catch (e) { $("detStatus").textContent = "detector: failed to load (offline?)"; }
})();
poll(); setInterval(poll, 2000); refreshBoard(); setInterval(refreshBoard, 15000);
</script>
</body>
</html>
```

- [ ] **Step 2: Run the routes test again** (it only checks "Snap now" is present)

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_vision_debug.py -v`
Expected: all PASS

- [ ] **Step 3: Manual check.** Add `VISION_DEBUG_DIR=C:/Users/HP/Desktop/fridge-cam-photos/debug` to `.env`, restart the API (`cd backend && ../.venv/Scripts/uvicorn.exe app.main:app --host 0.0.0.0 --port 8000`), open `http://localhost:8000/vision/debug` in Antigravity (Command Palette → "Simple Browser: Show"). Expected: header shows provider and model, page says "no photo yet" until the board posts, detector status becomes "ready".

- [ ] **Step 4: README.** After the "Choosing a vision provider" subsection add:

```markdown
#### Watching the camera live (developer page)

Set `VISION_DEBUG_DIR=some/folder` in `.env` (ignored in production), restart the API, and open
`http://localhost:8000/vision/debug` — in Antigravity / VS Code use *Simple Browser: Show*. The page shows the latest
photo with free in-browser detector boxes (COCO-SSD), the model's verdict per slot, live grams, and a **Snap now**
button that asks the board for a fresh photo. Photos land only in that folder, never in the database.
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/static/vision_debug.html README.md
git commit -m "feat(vision): live viewer page with COCO-SSD boxes, slot verdicts, grams, snap and auto mode

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Firmware "snap now" listener

**Files:**
- Modify: `edge/esp32cam/fridge_cam/fridge_cam.ino` (includes ~line 17-22, OTA block ~line 95-125, `loop()` ~line 290-330, header comment)
- Modify: `edge/README.md` (OTA section)

**Interfaces:**
- Produces on the board: `GET http://<board-ip>/snap -> {"ok":true}` (photo follows within a second), `GET http://<board-ip>/ -> {"tray":1,"ip":"...","wifi":"up","uptime_s":N,"last_photo_s_ago":N}`.

- [ ] **Step 1: Add the listener.** After `#include <ArduinoOTA.h>` add `#include <WebServer.h>`. After the `watchWifi` function add:

```cpp
// ---- "Snap now" listener: the dev page asks the board for a photo. LAN only, no password: it can only
// trigger the same authenticated post the board makes on its own. ----
WebServer snapServer(80);
bool snapStarted = false;
bool snapRequested = false;

void setupSnap() {
  if (snapStarted || WiFi.status() != WL_CONNECTED) return;
  snapServer.on("/snap", []() {
    snapRequested = true;
    snapServer.send(200, "application/json", "{\"ok\":true}");
    logf("[snap] requested by %s", snapServer.client().remoteIP().toString().c_str());
  });
  snapServer.on("/", []() {
    char body[160];
    unsigned long now = millis();
    snprintf(body, sizeof(body), "{\"tray\":%d,\"ip\":\"%s\",\"wifi\":\"%s\",\"uptime_s\":%lu,\"last_photo_s_ago\":%ld}",
             TRAY_POSITION, WiFi.localIP().toString().c_str(), WiFi.status() == WL_CONNECTED ? "up" : "down",
             now / 1000UL, lastPhotoPost ? (long)((now - lastPhotoPost) / 1000UL) : -1L);
    snapServer.send(200, "application/json", body);
  });
  snapServer.begin();
  snapStarted = true;
  logf("[snap] listening on http://%s/snap", WiFi.localIP().toString().c_str());
}
```

In `loop()`, right after `setupOta();` add:

```cpp
  setupSnap();
  if (snapStarted) snapServer.handleClient();
```

Change the photo condition from

```cpp
  if ((settled || photoDue) && canTry) {
    changePending = false;
```

to

```cpp
  if ((settled || photoDue || snapRequested) && (canTry || snapRequested)) {
    changePending = false;
    snapRequested = false;
```

In the header comment, after the OTA bullet, add:

```
    - Answers GET /snap on port 80 (take a photo now, for the developer page) and GET / (status JSON).
```

- [ ] **Step 2: Compile with PlatformIO**

Run: `cd edge/esp32cam/fridge_cam && ~/.platformio/penv/Scripts/pio.exe run -e esp32cam 2>&1 | tail -6`
Expected: `[SUCCESS]`, Flash under 60% of 1966080 bytes.

- [ ] **Step 3: Compile the way CI does** (arduino-cli, example config, scratch copy)

Run:
```bash
S="$TEMP/fridge_cam_ci"; rm -rf "$S"; mkdir -p "$S"
cp edge/esp32cam/fridge_cam/fridge_cam.ino edge/esp32cam/fridge_cam/config.h.example "$S/"; cp "$S/config.h.example" "$S/config.h"
"/c/Users/HP/AppData/Local/Programs/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe" compile --fqbn esp32:esp32:esp32cam "$S" 2>&1 | tail -3
```
Expected: `Sketch uses ... bytes` and no error.

- [ ] **Step 4: Push over Wi-Fi and prove it**

Run: `cd edge/esp32cam/fridge_cam && ~/.platformio/penv/Scripts/pio.exe run -e esp32cam_ota -t upload 2>&1 | grep -E "Authenticating|SUCCESS|FAILED"`
Expected: `Authenticating...OK` and `[SUCCESS]`.
Then, with the API running: `curl -s http://192.168.1.9/ && curl -s http://192.168.1.9/snap`
Expected: status JSON, then `{"ok":true}`, and within ~5 s the API log shows `POST /vision/device/trays/1/photo ... 200`.

- [ ] **Step 5: README.** In `edge/README.md`, after the OTA subsection add:

```markdown
### Snap now

While on Wi-Fi the camera answers `http://<board-ip>/snap` (take and post a photo right away) and
`http://<board-ip>/` (status JSON). The API's developer page at `/vision/debug` uses these; you can also curl them.
```

- [ ] **Step 6: Commit**

```bash
git add edge/esp32cam/fridge_cam/fridge_cam.ino edge/README.md
git commit -m "feat(edge): GET /snap and GET / on the ESP32-CAM for the developer page

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: End-to-end run and screenshot

**Files:**
- Modify: `.env` (local, gitignored): add `VISION_DEBUG_DIR=C:/Users/HP/Desktop/fridge-cam-photos/debug`
- Create: `docs/screenshots/vision-debug.png`
- Modify: `README.md` (embed the screenshot under "Watching the camera live")

- [ ] **Step 1: Restart the API** with the new setting and confirm `GET /vision/debug` is 200 and `GET /health` is 200.
- [ ] **Step 2: Snap from the page** (or `curl -X POST http://localhost:8000/vision/debug/snap`). Expected: the page shows the new photo within 2 s, green detector boxes if anything COCO knows is in view, blue slot bands with the model's items, grams for slot 1.
- [ ] **Step 3: Four-item shelf test** (needs the founder: four groceries in a row, camera 25–40 cm back). Snap, read the verdicts, note the model's accuracy in the commit message.
- [ ] **Step 4: Screenshot** the page (Playwright MCP or the OS snipping tool) to `docs/screenshots/vision-debug.png`; add `![Live camera viewer](docs/screenshots/vision-debug.png)` under the README subsection.
- [ ] **Step 5: Run everything once more**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest -q && ../.venv/Scripts/python.exe -m ruff check .`
Expected: all PASS, ruff clean.

- [ ] **Step 6: Commit and push**

```bash
git add docs/screenshots/vision-debug.png README.md
git commit -m "docs: live camera viewer screenshot and four-item shelf result

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```
