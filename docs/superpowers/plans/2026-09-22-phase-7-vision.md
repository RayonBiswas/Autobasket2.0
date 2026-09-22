# Phase 7 — Vision: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A photo of a shelf (from the fridge camera or a phone) names what sits in each slot, suggests the slot assignment, and flags when the camera disagrees with what the household said is there.

**Architecture:** `services/vision.py` sends one image to any OpenAI-compatible chat endpoint that accepts images (the existing `OPENAI_*` settings; `VISION_MODEL` overrides the model) with a strict "answer in JSON, one entry per slot, use only these catalog names" prompt, matches each guess to the catalog, and stores a `vision_results` row per slot. The slot view then carries a `vision` block (guess, confidence, kind: suggestion / match / mismatch / unknown). The Camera page uploads a photo per shelf and offers "Use this" per slot. The old blue-pixel water-level demo and its OpenCV dependency go away.

**Tech Stack:** httpx, Pillow-free (the model receives the JPEG as a data URI), FastAPI multipart, React.

**Spec:** roadmap §3.2, §3.4, §6 Phase 7.

## Global Constraints
The model only identifies; weights still decide quantity. Not configured → a clear 503, never a fake answer. Photos are not stored, only a SHA-256 of them and the model's answer. Every schema change via Alembic.

---

### Task 1: Migration 0007
- [ ] `VisionResult`: id, tray_id FK, slot_position int, product_guess (80), matched_product_id FK|None, confidence float, image_sha (64), created_at. Index (tray_id, created_at). Autogenerate `0007_vision_results`. Commit.

### Task 2: Vision service (TDD)
```python
@dataclass
class SlotGuess: slot: int; item: str; confidence: float; product_id: int | None = None
def configured() -> bool
def identify(image: bytes, mime: str, slot_count: int, catalog: list[str], caller=None) -> list[SlotGuess] | None   # None = not configured / failed
def match_catalog(item: str, products: list[Product]) -> Product | None   # exact name, then substring, case-insensitive
def analyze_tray(db, tray, image, mime, caller=None) -> list[dict]   # stores VisionResult rows, returns slot views' vision blocks
def vision_block(db, slot) -> dict | None   # latest result for slot: {item, confidence, matched_product_id, matched_name, kind, at}
```
`kind`: `suggestion` (slot empty, guess matched), `match` (guess == assigned), `mismatch` (guess matched a different product, confidence ≥ 0.6), `unknown` (no catalog match or "empty").
- [ ] Tests (`test_vision.py`): a fake caller returning `{"slots":[{"slot":1,"item":"Amul curd","confidence":0.9},{"slot":2,"item":"milk","confidence":0.8},{"slot":3,"item":"empty","confidence":0.7}]}` on the seeded tray (milk in 1, rice in 2, water in 3, slot 4 empty) → slot 1 mismatch (curd), slot 2 mismatch (milk vs rice), slot 3 unknown, slot 4 absent; unassigned slot + "milk" → suggestion; a caller that raises → None; `match_catalog("Amul Taaza milk 1L")` → milk; not configured → `identify` returns None.
- [ ] Commit `feat(vision): slot identification via image-capable model`.

### Task 3: Routes + cleanup
- [ ] `POST /vision/trays/{tray_id}/photo` (household, multipart `image`, ≤ 8 MB, jpeg/png/webp) → `{tray_id, slots: [...]}`; 503 "Vision is not set up" when unconfigured. `POST /devices/me/trays/{position}/photo` (device token) same. `slot_view` gains `vision`. Delete `routes/vision.py` water-level, remove `opencv-python-headless` and `numpy` from requirements, remove `frontend/src/pages/Detection.jsx`.
- [ ] Tests: upload with the fake caller (monkeypatch `vision.identify`) → slot views show `vision.kind`; unconfigured → 503; another household's tray → 404; device route works with the device token.
- [ ] Commit `feat(vision): photo endpoints, slot vision block; remove water-level demo`.

### Task 4: Camera page
- [ ] `/camera`: per shelf a card with "Take or upload a photo" (`<input type=file accept=image/* capture=environment>`), then per slot: what's assigned, what the camera saw with confidence, and a "Use this" button on suggestions/mismatches (calls `PUT /slots/{id}`), "Camera and scale agree" on matches. Empty state explains the flow. Not-configured notice with the env var names.
- [ ] Lint/build, live test with a real photo of groceries (`docs/screenshots/phase-7-camera.png`), README "What the camera does". Commit, merge, push.

## Self-review
§3.4 cloud model per door-close → T2/T3 device route; auto-suggest + mismatch → T2/T4; delete Camera.jsx/vision.py → T3; done-when (upload a phone photo, app names items) → T4.
