# Live Vision Viewer + Provider Switch: Design

Date: 2026-09-25
Status: DRAFT — waiting for approval
Audience: the founder (new to coding). Plain words. Every decision has a one-line "why".

---

## 1. What we are building (one paragraph)

A developer page, opened inside the editor, that shows the fridge camera's latest photo with two overlays: instant
free boxes from a detector running in the browser (bottle, cup, apple, banana, ...), and the product's real answer
per slot from the cloud vision model (item, confidence, rough box), plus live grams per slot from the scale. A
"Snap now" button and an "auto every N seconds" toggle make it feel live. Alongside, the vision provider becomes a
one-line switch between NVIDIA NIM (demo), Google Gemini (practice), Groq (practice) and OpenRouter (fallback).

---

## 2. Why

- The founder needs to *see* classification working to trust it and to set up shelves well. Today the server keeps
  only a hash of each photo, so there is nothing to look at.
- Practice should be free (Gemini / Groq free tiers) and the demo should run on NIM. Same prompt and code path for
  all, so practice results predict demo results.
- The first AutoBasket had a browser detector with live boxes (COCO-SSD). It was removed in Phase 7. It is still
  the cheapest way to get convincing boxes, so it comes back as a *viewer layer*, not as the classifier.

---

## 3. What exists today

| Piece | State |
|---|---|
| ESP32-CAM firmware | Posts weights + a JPEG on weight change and every 30 min. OTA updates work (done 2026-09-25). No way to ask for a photo on demand. |
| Backend vision | `services/vision.py`: prompt → any OpenAI-compatible endpoint → JSON per slot → `vision_results` rows. Photo bytes discarded (only sha256 kept). No `max_tokens`, so low-credit accounts get 402 refusals. |
| Providers | `.env` has one block (OpenRouter, nearly out of credit). `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL` / `VISION_MODEL` already drive everything. |
| Web app Camera page | Shows the per-slot verdicts. Never shows the photo (privacy by design). Unchanged by this work. |
| Scale readings | `POST /devices/me/readings`; latest grams per slot live in the readings table. |

---

## 4. Design

### 4.1 Firmware: "snap now" listener (`edge/esp32cam/fridge_cam/fridge_cam.ino`)

- After Wi-Fi connects, start a tiny web listener on port 80 (the core's `WebServer` library, no extra download).
- `GET /snap` → sets a flag, replies `{"ok":true}` at once. In the next loop pass the board posts readings and a
  photo through the normal path, ignoring the retry backoff. Logs `[snap] requested`.
- `GET /` → `{"tray":1,"ip":"...","wifi":"up","uptime_s":...,"last_photo_s_ago":...}` so the page can show board health.
- No password. **Why:** LAN-only, and the worst it can do is take one photo through the normal, authenticated path.
- Pauses like everything else during an OTA update. Goes to the board over Wi-Fi.

### 4.2 Backend

**Setting.** `VISION_DEBUG_DIR` (optional path). When set: the debug routes are mounted and files are written.
When `APP_ENV=production` it is ignored with a startup warning. **Why:** the dev page has no login; it must never
exist on the VPS.

**Vision service changes** (`app/services/vision.py`):
- `max_tokens=400` on the model call. **Why:** the answer is short JSON; without a cap, OpenRouter reserves the
  model's full output budget and refuses low-balance accounts (seen today).
- Prompt gains one sentence: *"When you name an item, also give `box` as `[x, y, w, h]` fractions of the image
  (0 to 1) around it; omit `box` for empty or unknown."* Parser accepts an optional box, validates it (four numbers,
  0–1, positive w/h) and drops bad ones. `SlotGuess` gets `box: tuple | None`. **Not** stored in the database;
  no migration. **Why:** boxes from a language model are rough; they are for the viewer, not for the product.
- Prompt also softened: *"If an item from the list is visible anywhere in the photo, name it even if the scene
  does not look like a fridge."* **Why:** desk tests returned "unknown" for a plainly visible bottle.
- `analyze_tray` returns, besides the blocks, the raw guesses (with boxes) and the elapsed milliseconds.

**Debug capture** (`app/services/vision_debug.py`, new):
- After a successful device or household photo analysis, write `latest.jpg` and `latest.json` into the debug dir:
  `{at, device_name, tray_position, model, base_url_host, elapsed_ms, device_ip, slots:[{slot, item, confidence,
  kind, matched_name, box}]}`. Atomic write (temp file + rename) so the page never reads a half file.
- Remember the last IP each device posted from (in memory). **Why:** the snap relay needs the board's address and
  the board already tells us by posting.

**Routes** (`app/routes/vision_debug.py`, new; mounted under `/vision/debug` only when the dir is set):
- `GET /vision/debug` → the HTML page (served from `app/static/vision_debug.html`, no build step).
- `GET /vision/debug/latest.json`, `GET /vision/debug/latest.jpg`.
- `GET /vision/debug/weights` → latest grams per slot for the tray in `latest.json`, from the readings table.
- `POST /vision/debug/snap` → `GET http://<device_ip>/snap` with a 3 s timeout; returns the board's reply, or 502
  with "board not reachable at <ip>".

**Provider blocks** (`.env.example`, README): four commented blocks, one active:

| Block | Use | `OPENAI_BASE_URL` | `VISION_MODEL` | `OPENAI_MODEL` (chat) |
|---|---|---|---|---|
| NVIDIA NIM | demo | `https://integrate.api.nvidia.com/v1` | `google/gemma-3-27b-it` | `meta/llama-3.3-70b-instruct` |
| Google Gemini | practice | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-3.8-flash` | `gemini-3.8-flash` |
| Groq | practice | `https://api.groq.com/openai/v1` | `qwen/qwen3.6-27b` | `qwen/qwen3.6-27b` |
| OpenRouter | fallback | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini` | `openai/gpt-4o-mini` |

Switching = uncomment one block, restart the API. Keys come from the founder (not yet in `.env`).
A kept script, `backend/scripts/vision_smoke.py <photo.jpg>`, prints the configured provider's raw answer for one
image. **Why:** the ad-hoc checks done today were useful; make them a tool.

### 4.3 The page (`backend/app/static/vision_debug.html`)

One file, plain HTML + JS, opened in Antigravity via *Simple Browser: Show* → `http://localhost:8000/vision/debug`.

- Polls `latest.json` every 2 s; when `at` changes, reloads the photo and redraws.
- **Layer A, detector boxes (green):** TensorFlow.js + COCO-SSD from the jsDelivr CDN, exactly the libraries the
  first AutoBasket used. Runs on the laptop CPU in well under a second per photo. Toggle on/off.
- **Layer B, model verdicts (blue):** the photo split into N vertical slot bands; each band shows the item,
  confidence and kind (match / suggestion / mismatch / unknown). If the model gave a box, draw it. Toggle on/off.
- **Layer C, grams per slot** from `/weights`, shown in each band's corner.
- Header: provider host + model, elapsed ms, board IP and health (from the board's `GET /` via the relay).
- Controls: **Snap now**, **Auto** (5 / 10 / 30 s, off), layer toggles. A visible call counter, because auto mode
  costs one model call per snap.
- Detector plug-in shape: `detectors.cocossd = { load(), detect(img) → [{label, score, box:[x,y,w,h]}] }`. A better
  detector later (YOLO11n via ONNX Runtime Web, or OWLv2 for open-vocabulary "paneer packet") is a new object with
  the same shape and a dropdown entry. **Why:** the founder asked for "COCO-SSD or better"; start with the proven
  one, keep the door open.

### 4.4 Data flow

```
[Snap now] → POST /vision/debug/snap → GET http://board/snap
                                          └→ board: readings + photo → POST /vision/device/trays/1/photo
                                                                          ├→ model (NIM / Gemini / Groq / OpenRouter)
                                                                          ├→ vision_results rows (as today)
                                                                          └→ latest.jpg + latest.json (debug dir)
page polls latest.json → redraw: COCO-SSD boxes (browser) + slot verdicts + grams
```

### 4.5 Errors

| Case | Behaviour |
|---|---|
| Board unreachable | Snap returns 502; page banner "board not reachable at 192.168.1.x". |
| Model fails / 429 | Existing fail-soft: photo route returns 502; page keeps the last result and shows the error. |
| Debug dir missing | Created on first write. |
| Production | Setting ignored, warning logged, routes absent. |
| Half-written file | Prevented by atomic rename. |

---

## 5. Testing

Backend (pytest, no real model): box parsing (valid, missing, malformed); `max_tokens` present in the request body;
debug routes 404 when the setting is unset; files written to a `tmp_path` dir after a stubbed analysis; snap relay
calls the remembered device IP (httpx stubbed) and maps timeouts to 502; production ignores the setting.
Firmware: compiles in PlatformIO and CI; pushed over Wi-Fi; `curl http://<board>/snap` produces a photo post.
Page: manual check in Simple Browser with the four-item shelf test. Providers: `vision_smoke.py` against each key.

## 6. Out of scope

Showing photos to real users in the app's Camera page (privacy design stands); storing boxes in the database;
on-device or local models; YOLO / OWLv2 detectors (future plug-in); the exposure fix for flash photos (separate
small change, already proposed).
