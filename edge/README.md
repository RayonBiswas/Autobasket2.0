# edge — the code that runs at the fridge

| Folder / file | What it is |
|---|---|
| `arduino/scale_node/` | Arduino sketch. Reads up to 4 HX711 load-cell amplifiers, keeps calibration in EEPROM, prints grams once a second. |
| `esp32cam/fridge_cam/` | ESP32-CAM sketch. Takes those grams over a serial link, posts weights to the API, and a shelf photo whenever a weight changes (and every 30 min). |
| `simulator.py` | A fake fridge for your laptop. Drains slot weights over time and posts readings. Use it to demo the whole loop without hardware. |

Two boards because the ESP32-CAM has almost no free pins once the camera is wired, while the HX711s need two
pins each and like 5 V. The Arduino does the weighing; the ESP32-CAM does Wi-Fi and the camera. There is no door switch: a weight change is the trigger.

```
 load cells ──► HX711 ×4 ──► Arduino ──serial──► ESP32-CAM ──Wi-Fi──► API (/devices/me/readings, /vision/device/...)
```

## Parts

- Arduino Uno or Nano (5 V), one HX711 amplifier board per slot, one load cell (5 kg bar type is fine) per slot.
- ESP32-CAM (AI-Thinker) with its OV2640 camera, plus a USB-to-serial adapter (FTDI/CH340, 3.3 V logic) to flash it.
- Two resistors (1 kΩ and 2 kΩ) for the serial divider, a 5 V 2 A supply.

## Wiring

**HX711 → Arduino** (one board per slot):

| HX711 pin | Slot 1 | Slot 2 | Slot 3 | Slot 4 |
|---|---|---|---|---|
| DT  | D2 | D4 | D6 | D8 |
| SCK | D3 | D5 | D7 | D9 |
| VCC | 5V | 5V | 5V | 5V |
| GND | GND | GND | GND | GND |

Load cell to HX711: red → E+, black → E−, white → A−, green → A+ (swap white/green if readings go negative).

**Arduino ↔ ESP32-CAM** (common ground is required):

| From | To | Note |
|---|---|---|
| Arduino TX (D1) | 1 kΩ → ESP32 GPIO 14, with 2 kΩ from GPIO 14 to GND | divides 5 V down to ~3.3 V; the ESP32 is not 5 V tolerant |
| ESP32 GPIO 15 | Arduino RX (D0) | 3.3 V is a valid high for the Arduino |
| Arduino GND | ESP32 GND | |

Because the Arduino's D0/D1 are also its USB serial pins, unplug the ESP32 link (or just GPIO 15 → D0) while
uploading a sketch to the Arduino.

**Power and light:**

| What | Where |
|---|---|
| Flash LED | built in on GPIO 4, used during the photo |
| Power | 5 V into the ESP32-CAM's 5V pin (it draws up to ~300 mA with Wi-Fi + flash; do not power it from the Arduino's 3.3 V pin) |

GPIO 14/15 are the SD-card pins, so the SD slot is unavailable; the firmware does not need it.

## Flashing

1. Arduino IDE 2 → Boards Manager → install **esp32 by Espressif** (already present on this PC) and select
   **AI Thinker ESP32-CAM**. Arduino Uno/Nano needs nothing extra.
2. `arduino/scale_node/scale_node.ino`: open, upload to the Arduino (no libraries needed).
3. `esp32cam/fridge_cam/`: copy `config.h.example` to `config.h`, fill in Wi-Fi, `API_URL` and the device key
   (app → Shelves → Add a fridge). To upload: connect the USB-serial adapter (5V→5V, GND→GND, TX→U0R, RX→U0T),
   tie **IO0 to GND**, press reset, upload, then remove the IO0 jumper and press reset again.
4. Open the serial monitor at 115200 for the ESP32-CAM. You should see `[wifi] connected`, `[cam] ready`, then
   `[status] ... slots=4` once the Arduino is talking.

With an **ESP32-CAM-MB** (the USB base board) there are no adapter wires and no IO0 jumper: dock the camera, plug in
USB, upload. The MB hides the GPIO pins, so the final install needs the camera off the MB and on a breadboard or
perfboard, powered by 5 V, with GPIO 14/15/GND going to the Arduino. That is why the firmware updates itself over
Wi-Fi: flash once over USB, then never dock it again.

### PlatformIO instead of the Arduino IDE

Each sketch folder has a `platformio.ini`, so "Open Project" in PlatformIO on either folder gives Build, Upload and
Serial Monitor buttons. `edge/arduino/scale_node` has environments for Nano (new and old bootloader) and Uno.

### Updating the camera over Wi-Fi (OTA)

The camera firmware listens for password-protected updates as `fridge-cam-<TRAY_POSITION>.local`. It needs the
two-slot flash layout, which `platformio.ini` sets (`min_spiffs.csv`); in the Arduino IDE choose Partition Scheme
"Minimal SPIFFS" for the first USB flash or OTA has nowhere to write.

1. Set `OTA_PASS` in `config.h` to a long random string before the USB flash. An empty value disables OTA.
2. Copy `ota_local.ini.example` to `ota_local.ini` (gitignored) and put the same password and the board's IP
   (printed at boot as `[wifi] connected, ip ...`) in it.
3. From `edge/esp32cam/fridge_cam`: `pio run -e esp32cam_ota -t upload`. The board logs `[ota] update starting`,
   reboots, and comes back on the new firmware. Wi-Fi name, API URL and any code change all go this way.

If Wi-Fi stays down for 30 minutes the board restarts itself once; that is the only self-reboot it does.

### Snap now

While on Wi-Fi the camera answers `http://<board-ip>/snap` (take and post a photo right away) and
`http://<board-ip>/` (status JSON). The API's developer page at `/vision/debug` uses these; you can also curl them.

Compile check from the terminal (optional): install arduino-cli with `winget install ArduinoSA.CLI`, then

```powershell
arduino-cli core install arduino:avr esp32:esp32
arduino-cli compile --fqbn arduino:avr:uno edge/arduino/scale_node
arduino-cli compile --fqbn esp32:esp32:esp32cam edge/esp32cam/fridge_cam
```

## Calibrating

In the Arduino serial monitor (9600 baud, "Newline" line ending), once per slot:

1. Empty platform → type `T 1` (tare slot 1).
2. Put a known weight on it (a sealed 1 L water bottle is 1000 g) → type `C 1 1000`.
3. `S` prints the stored offset and scale; they survive power cycles.

Then in the app, on Shelves: choose the product for the slot and tap **This is empty** once with the empty pack
and **This is full** once with a full one. From then on the percentage and "runs out on Thursday" are automatic.

## Run the simulator instead

1. Start the API (`cd backend; uvicorn app.main:app --reload`).
2. Get a device token: web app → **Shelves** → **Add a fridge** (or `POST /seed/dev`, which creates a "Dev Fridge").
3. Run:

```powershell
$env:AB_DEVICE_TOKEN = "<paste token>"
$env:AB_INTERVAL = "3"
..\.venv\Scripts\python.exe edge\simulator.py
```

`--backfill-days 14` first posts two weeks of history so the learner has something to learn from.

## Contract with the API

- `GET  /devices/me` — the slot layout (positions, product, tare/full grams).
- `POST /devices/me/readings` — `{"readings": [{"tray": 1, "slot": 1, "weight_grams": 565.0}, …]}`.
- `POST /vision/device/trays/{position}/photo` — multipart `image` (JPEG) of that shelf.

All three use `Authorization: Bearer <device key>`. The ESP32-CAM uses exactly these calls; when deployed, point
`API_URL` at `https://<your-domain>/api`.

## Troubleshooting

- `E,<slot>` lines from the Arduino: that HX711 is not answering. Check VCC/GND and the DT/SCK pins.
- Readings drift with temperature: normal for bar load cells; the app's learner ignores jitter under 2 %.
- `[cam] init failed`: the camera ribbon is not seated, or the board has no PSRAM (the firmware then falls back to VGA).
- `[api] ... -> 401`: the device key is wrong or was regenerated in the app.
- HTTPS to a public server with `TLS_INSECURE 0` fails: add the server's root CA in `fridge_cam.ino` (`secure.setCACert`).
