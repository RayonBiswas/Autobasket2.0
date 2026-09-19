# edge — code that runs on the fridge device

| File | What it is |
|---|---|
| `simulator.py` | A fake Raspberry Pi. Drains slot weights over time and posts readings to the API. Use it to develop and demo the whole loop before the hardware arrives. |
| `agent.py` | *(Phase 8)* The real Pi program: HX711 load cells, door switch, camera. Same HTTP contract as the simulator. |

## Run the simulator

1. Start the API (`cd backend; uvicorn app.main:app --reload`).
2. Get a device token: log in to the web app → **Fridge Slots** → **Add device** (or call `POST /seed/dev`, which creates a "Dev Fridge" and returns `device_token`). The token is shown once.
3. Run:

```powershell
$env:AB_DEVICE_TOKEN = "<paste token>"
$env:AB_INTERVAL = "3"
..\.venv\Scripts\python.exe edge\simulator.py
```

Output, one line per tick:

```
tick 12 | milk 43% | rice 71% | water 12% (refilled) | applied=3
```

`applied` is how many slots the API turned into inventory updates — only slots that have a product **and**
are calibrated (Mark empty / Mark full on the Slots page) count. `--once` posts a single tick and exits.

## Contract with the API

- `GET  /devices/me` — the slot layout (positions, product, tare/full grams).
- `POST /devices/me/readings` — `{"readings": [{"tray": 1, "slot": 1, "weight_grams": 565.0}, …]}`.

Both use `Authorization: Bearer <device token>`. The real Pi will use exactly these two calls.
