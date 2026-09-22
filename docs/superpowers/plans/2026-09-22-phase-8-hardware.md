# Phase 8 — Real Hardware (ESP32-CAM + Arduino + HX711): Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the simulator with the real fridge: load cells under each slot, a camera that photographs the shelf when the door closes, and a Wi-Fi link that posts both to the API.

**Hardware deviation from the roadmap:** the user has an **ESP32-CAM (AI-Thinker)**, an **Arduino** (Uno/Nano) and **HX711** load-cell amplifiers, not a Raspberry Pi. Two boards, one job each:

```
 load cells ──► HX711 ×N ──► Arduino  ──UART──►  ESP32-CAM ──Wi-Fi──► API
                              (grams,       (door switch, camera,
                               calibration)  posting, retries)
```

- **Arduino `scale_node`**: bit-bangs the HX711s (no library needed), takes a median of samples, keeps per-slot tare/scale in EEPROM, prints `W,<slot>,<grams>` once a second. Calibration over the serial monitor: `T <slot>` (tare, empty platform), `C <slot> <grams>` (a known weight on it).
- **ESP32-CAM `fridge_cam`**: reads those lines on a second UART (GPIO 14 RX / 15 TX), watches the door reed switch (GPIO 13), posts readings every 5 minutes and, 3 s after the door closes, posts readings plus a JPEG of the shelf (flash LED on GPIO 4) to `/vision/device/trays/<pos>/photo`. Device key from Shelves → Add a fridge.

**Why two boards:** the ESP32-CAM exposes only a handful of GPIOs and its camera uses most of them, while HX711s need two pins each; the Arduino has the pins and 5 V for the amplifiers. The UART between them is one wire each way plus a divider.

**Tech Stack:** Arduino IDE 2 (user), arduino-cli (compile check, CI), ESP32 core 3.x, `esp_camera`, `HTTPClient`, `WiFiClientSecure`.

**Spec:** roadmap §3.2, §3.3, §6 Phase 8.

## Global Constraints
No secrets in the repo: Wi-Fi and device key live in `config.h` (gitignored) with a `config.h.example`. Firmware must fail soft: no Wi-Fi or API → keep the latest readings and retry with backoff, never reboot-loop. Everything the README says about wiring must match the pin constants in the sketches.

---

### Task 1: Arduino scale node
- [ ] `edge/arduino/scale_node/scale_node.ino`: `N_SLOTS` (default 4), pin pairs `{2,3},{4,5},{6,7},{8,9}` (DT, SCK), gain 128, `readRaw()` bit-bang with a 200 ms timeout per HX711, `median5()`, per-slot `offset` and `scale` (counts per gram) in EEPROM with a magic byte, serial commands `T n`, `C n grams`, `S` (show), `R` (raw dump), output `W,n,grams` at 1 Hz, `E,n` when a channel is not ready (unplugged).
- [ ] Commit `feat(edge): Arduino HX711 scale node with EEPROM calibration`.

### Task 2: ESP32-CAM fridge camera
- [ ] `edge/esp32cam/fridge_cam/config.h.example` (`WIFI_SSID`, `WIFI_PASS`, `API_URL`, `DEVICE_TOKEN`, `TRAY_POSITION`, `READINGS_EVERY_S`, `SETTLE_MS`, `TLS_INSECURE`), `.gitignore` for `config.h`.
- [ ] `edge/esp32cam/fridge_cam/fridge_cam.ino`: AI-Thinker camera pin map, PSRAM check, SVGA JPEG; `Serial1.begin(9600, SERIAL_8N1, 14, 15)` parser for `W,n,g`; door on GPIO 13 `INPUT_PULLUP` with 50 ms debounce (LOW = closed); on close → wait `SETTLE_MS` → `postReadings()` → `postPhoto()`; `postReadings()` every `READINGS_EVERY_S`; Wi-Fi reconnect loop; exponential backoff 5 s → 5 min on failures; flash LED on during capture; status line on `Serial` (USB) every 30 s.
- [ ] Commit `feat(edge): ESP32-CAM firmware posting readings and door-close photos`.

### Task 3: Wiring guide + compile check
- [ ] `edge/README.md`: parts list, wiring table (HX711 → Arduino pins; Arduino TX → 1 kΩ/2 kΩ divider → ESP32 GPIO 14; ESP32 GPIO 15 → Arduino RX; common GND; reed switch GPIO 13 ↔ GND; 5 V supply for the ESP32-CAM, not the Arduino's 3.3 V pin), flashing the ESP32-CAM (IO0 to GND, USB-TTL, reset), calibration walkthrough, then "This is empty / This is full" in the app, troubleshooting.
- [ ] Compile both sketches with `arduino-cli compile --fqbn arduino:avr:uno` and `--fqbn esp32:esp32:esp32cam` (user installs arduino-cli with `winget install ArduinoSA.CLI`; the ESP32 core is already present in Arduino15). Add a CI job that compiles them.
- [ ] Commit `docs(edge): wiring, flashing and calibration guide; CI compiles firmware`.

## Self-review
§6 Phase 8 bullets: HX711 median-filtered → T1; tare/calibration → T1 (serial) + app; door switch → settle → read → photo (LED on) → POST → T2; offline queue on SD card → replaced by retry/backoff (the ESP32-CAM's SD slot shares pins with the UART we use; noted in README); systemd → n/a on a microcontroller. Done-when: real readings appear on Shelves and a door-close photo appears on Camera.
