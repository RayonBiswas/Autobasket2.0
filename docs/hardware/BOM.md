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

| ✓ | Part | Qty | ≈ ₹ each | Link | Notes |
|---|---|---|---|---|---|
| ☐ | ESP32 DevKitC | 2 | 300–400 | https://robocraze.com/products/esp32-development-board | Wireless per-tray sensor nodes |

## Design notes carried from the spec (§3.3, §7)

- The Pi sits **outside** the fridge; only load cells, camera, LED strip and door switch go inside.
- Flat cables run through the door gasket. Test the seal with a paper strip after install.
- Pi 5 GPIO budget: 8 HX711 × 2 pins + door switch + LED = 18 of 26 usable pins.
- Coat the HX711 boards with conformal spray or nail varnish against condensation.
