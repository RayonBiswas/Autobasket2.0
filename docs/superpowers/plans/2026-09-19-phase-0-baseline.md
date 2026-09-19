# Phase 0 — Baseline & Hardware Order: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the existing app runs on this Windows machine with one clean Python environment, fix the one known bug, make the database URL configurable, and produce the hardware order list — so Phases 1+ start from a known-good base while hardware ships.

**Architecture:** No structural changes. One root `.venv` (Python 3.12 via `uv`) replaces the two half-installed venvs. `database.py` reads `DATABASE_URL` from the environment with the current SQLite path as default. A hardware BOM markdown is added under `docs/hardware/`.

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy 2, pytest, Node 24 / Vite, git.

**Spec:** `docs/superpowers/specs/2026-09-19-smart-fridge-roadmap-design.md` — §2 (audit), §6 Phase 0, §7 (BOM), §10 (tools).

## Global Constraints

- Python **3.12** for the project venv (3.14 lacks wheels for some deps). Managed by `uv`.
- Tests run with `pytest backend/tests -q` from the repo root (matches `.github/workflows/ci.yml`).
- Never run `rm -rf`, `git reset --hard`, or force-push without asking the user first (user rule).
- All commits end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Tell the user in one line what a file-changing command does before running it.

---

### Task 1: One Python environment, all tests green

**Files:**
- Modify: `backend/requirements.txt`
- Delete (with user permission): `.venv/` (Python 3.14), `backend/venv/` (Python 3.12, incomplete)
- Create: `.venv/` (Python 3.12 via uv)

**Interfaces:**
- Produces: `.venv/Scripts/python.exe` — the interpreter every later task and phase uses.

- [ ] **Step 1: Add the two missing runtime deps to requirements**

`app/routes/vision.py` imports `cv2` and `numpy` but `requirements.txt` does not list them, so `app.main` cannot be imported in a fresh install. Append:

```
opencv-python-headless>=4.10.0
numpy>=1.26.0
```

- [ ] **Step 2: Ask the user for permission to remove the two old venvs**

Say: "I want to delete `.venv/` (Python 3.14, incomplete) and `backend/venv/` (Python 3.12, incomplete) and create one fresh `.venv/` on Python 3.12. This deletes ~1 GB of installed packages, nothing of yours. OK?" Wait for yes.

- [ ] **Step 3: Recreate the environment**

Run (PowerShell):
```powershell
Remove-Item -Recurse -Force .venv, backend\venv
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r backend\requirements.txt
.venv\Scripts\python.exe --version
```
Expected: `Python 3.12.x`

- [ ] **Step 4: Run the existing test suite**

Run: `.venv\Scripts\python.exe -m pytest backend/tests -q`
Expected: `5 passed`. Paste the output to the user.

- [ ] **Step 5: Confirm the full app imports (this is what CI's server would do)**

Run: `.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'backend'); from app.main import app; print('routes:', len(app.routes))"`
Expected: `routes: <number ≥ 15>`

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: list opencv and numpy in requirements so the API imports on a fresh install

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Backend and frontend run locally

**Files:** none modified. Evidence-gathering task.

- [ ] **Step 1: Start the API in the background**

Run: `cd backend; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000` (background)

- [ ] **Step 2: Hit the root and seed endpoints**

Run:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/
Invoke-RestMethod -Method Post http://127.0.0.1:8000/seed/vendors
Invoke-RestMethod http://127.0.0.1:8000/vendors/compare/milk | ConvertTo-Json -Depth 3
```
Expected: `{"message":"AutoBasket 2.0 Running"}`, `{"message":"Sample vendors added"}`, and 3 ranked vendors for milk with `final_score` values. Paste to the user.

- [ ] **Step 3: Install and build the frontend**

Run: `cd frontend; npm ci; npm run build`
Expected: `✓ built in …` and a `dist/` folder. Paste the last 5 lines.

- [ ] **Step 4: Tell the user how to open the UI themselves**

Say: run `cd frontend; npm run dev` in a second terminal and open http://localhost:5173 — Dashboard and Detection pages should render. (Do not leave `npm run dev` running from this session; the user owns that terminal.)

- [ ] **Step 5: Stop the background API server** (TaskStop on the background task).

---

### Task 3: Fix `build_shopping_list` status mismatch (TDD)

**Files:**
- Modify: `backend/app/agent/tools.py:259-276`
- Test: `backend/tests/test_shopping_list.py` (new)

**Interfaces:**
- Consumes: `tools.build_shopping_list(db, max_items=5) -> {"shopping_list": [...], "message": str}`; `predictor.predict_status()` emits status ∈ {`safe`, `warning`, `critical`}.
- Produces: unchanged signature; `priority` is `"urgent"` for `critical`, `"soon"` for `warning`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_shopping_list.py
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import models
from app.agent import tools


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_critical_item_appears_as_urgent_in_shopping_list(db_session):
    # 2 adults + 1 child drink ~1.15 L milk/day (predictor base table).
    # 1 L left -> < 1 day -> status "critical".
    db_session.add(models.Household(adults=2, children=1, food_habit="mixed"))
    db_session.add(models.Item(
        name="milk", total_qty=10, remaining_qty=1, min_threshold=2,
        last_updated=datetime.utcnow(),
    ))
    db_session.commit()

    result = tools.build_shopping_list(db_session)

    names = [row["name"] for row in result["shopping_list"]]
    assert names == ["milk"]
    assert result["shopping_list"][0]["priority"] == "urgent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest backend/tests/test_shopping_list.py -v`
Expected: FAIL — `assert [] == ['milk']` (critical items are filtered out because the code looks for `"danger"`).

- [ ] **Step 3: Fix the two string literals**

In `backend/app/agent/tools.py`:

```python
# line 261 — was: if item["status"] in {"warning", "danger"}
needs_attention = [item for item in pantry_status["inventory"] if item["status"] in {"warning", "critical"}]
```
```python
# line 270 — was: "urgent" if item["status"] == "danger" else "soon"
"priority": "urgent" if item["status"] == "critical" else "soon"
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv\Scripts\python.exe -m pytest backend/tests -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agent/tools.py backend/tests/test_shopping_list.py
git commit -m "fix: shopping list now includes critical items (status was compared to 'danger')

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `DATABASE_URL` from environment (TDD)

**Files:**
- Modify: `backend/app/database.py`
- Modify: `.env.example`
- Test: `backend/tests/test_database_config.py` (new)

**Interfaces:**
- Produces: `app.database.get_database_url() -> str` — returns `os.environ["DATABASE_URL"]` if set, else `"sqlite:///./autobasket.db"`. Phase 1 will point this at PostgreSQL.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_database_config.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_default_is_local_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app import database
    assert database.get_database_url() == "sqlite:///./autobasket.db"


def test_env_overrides_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/autobasket")
    from app import database
    assert database.get_database_url() == "postgresql+psycopg://u:p@localhost:5432/autobasket"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest backend/tests/test_database_config.py -v`
Expected: FAIL — `AttributeError: module 'app.database' has no attribute 'get_database_url'`

- [ ] **Step 3: Implement**

Replace `backend/app/database.py` with:

```python
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DEFAULT_DATABASE_URL = "sqlite:///./autobasket.db"


def get_database_url() -> str:
    """DATABASE_URL from the environment, else the local SQLite file."""
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


DATABASE_URL = get_database_url()

# check_same_thread is a SQLite-only flag; other drivers reject it.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
```

Append to `.env.example`:

```
# Database (Phase 1 switches this to PostgreSQL)
# DATABASE_URL=sqlite:///./autobasket.db
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv\Scripts\python.exe -m pytest backend/tests -q`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/database.py backend/tests/test_database_config.py .env.example
git commit -m "feat: read DATABASE_URL from environment with SQLite default

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Hardware bill of materials as an order checklist

**Files:**
- Create: `docs/hardware/BOM.md`

**Interfaces:** none (document).

- [ ] **Step 1: Write the BOM file**

```markdown
# Hardware BOM — Dev Kit (1 fridge, 2 trays × 4 slots)

Order date: ____  Expected arrival: ____
Prices: India retail, Sept 2026. Confirm on the page before paying.

## Order now (Phase 0)

| ✓ | # | Part | Qty | ≈ ₹ each | Link | Notes |
|---|---|---|---|---|---|---|
| ☐ | 1 | Raspberry Pi 5, 4 GB | 1 | 5,500–6,200 | https://robu.in/product/raspberry-pi-5-model-4gb/ | Official reseller |
| ☐ | 2 | Raspberry Pi 27 W USB-C power supply | 1 | ~1,200 | robu.in / robocraze.com | Pi 5 underpowers on phone chargers |
| ☐ | 3 | Raspberry Pi 5 Active Cooler | 1 | ~500 | same | 24×7 operation |
| ☐ | 4 | Raspberry Pi 5 official case | 1 | ~800 | same | Fits the cooler |
| ☐ | 5 | microSD 32 GB, A2/U3 (SanDisk Extreme or Samsung EVO) | 1 | ~600 | Amazon | A2 rating matters for the OS |
| ☐ | 6 | Raspberry Pi Camera Module 3 **Wide** | 1 | ~3,650 incl. GST | https://www.electropi.in/raspberry-pi-camera-module-3-wide | 120° lens sees a whole tray |
| ☐ | 7 | **Pi 5 camera cable, 22-pin → 15-pin, 50 cm or 1 m** | 1 | 200–400 | search "Raspberry Pi 5 camera cable 500mm" on robu.in | ⚠ The cable in the camera box does NOT fit a Pi 5 |
| ☐ | 8 | 5 kg load cell + HX711 amplifier kit | 8 | 250–400 | https://robu.in/product/5-kg-load-cell-with-hx711ad-module-shell-and-4p-dupont-wire-kit/ | One per slot; buy 8 (or 10 for spares) |
| ☐ | 9 | Magnetic reed switch (door sensor, wired, normally-open) | 1 | ~50 | robu.in / Amazon | Tells the Pi when the door closes |
| ☐ | 10 | 5 V USB white LED strip, 30 cm | 1 | ~300 | Amazon | Fridge light turns off when the door closes; we need light for photos |
| ☐ | 11 | Female-female + male-female jumper wires (40 pcs each) | 1 set | ~150 | any | |
| ☐ | 12 | Perfboard 7×9 cm + 40-pin female header ×2 | 1 | ~200 | any | To fan out 8 HX711 boards neatly |
| ☐ | 13 | 3 mm acrylic sheet, 8 pieces cut 10 × 10 cm, + M3 × 20 mm standoffs (16) | 1 set | ~500 | local laser-cut shop or Amazon | Slot platforms sit on the load cells |
| ☐ | 14 | 500 g calibration weight (or use a sealed 500 ml water bottle ≈ 520 g) | 1 | 0–200 | | Calibration |

**Estimated total: ₹16,000 – 20,000.**

## Later (Phase 11, only if wired trays prove annoying)

| ☐ | ESP32 DevKitC | 2 | 300–400 | https://robocraze.com/products/esp32-development-board | Wireless per-tray sensor nodes |

## Design notes carried from the spec (§3.3, §7)

- The Pi sits **outside** the fridge; only load cells, camera, LED strip and door switch go inside.
- Flat cables run through the door gasket. Test the seal with a paper strip after install.
- Pi 5 GPIO budget: 8 HX711 × 2 pins + door switch + LED = 18 of 26 usable pins.
- Coat the HX711 boards with conformal spray or nail varnish against condensation.
```

- [ ] **Step 2: Commit**

```bash
git add docs/hardware/BOM.md
git commit -m "docs: hardware bill of materials for the dev kit

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Push and hand off

- [ ] **Step 1: Push**

Run: `git push origin main`
Expected: `main -> main` with the new commit range.

- [ ] **Step 2: Report to the user**

Paste: test output (`8 passed`), the API responses from Task 2, the frontend build tail, and the commit list. Then say: "Phase 0 done. Order the BOM (docs/hardware/BOM.md) and install Docker Desktop — both needed before Phase 1 can finish. Stop."

---

## Self-review

- **Spec coverage (Phase 0 bullets):** run locally ✓ (T1–T2), tests green ✓ (T1), bug fix + test ✓ (T3), `DATABASE_URL` in `.env` ✓ (T4), BOM file ✓ (T5), commit untracked config — already done in commit `9cbed1a` ✓, hardware ordered — user action, prompted in T6 ✓.
- **Placeholders:** none; every code step has full content.
- **Type consistency:** `get_database_url()` defined in T4 and referenced only there; `build_shopping_list` signature unchanged.
