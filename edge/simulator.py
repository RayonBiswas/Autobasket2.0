#!/usr/bin/env python3
"""AutoBasket fridge simulator.

Pretends to be the Raspberry Pi in the fridge: fetches the slot layout from the API, drains each
calibrated slot's weight a little every tick (with occasional "someone shopped" refills), and posts
readings exactly like the real device will.

Environment:
  AB_API_URL         API base URL           (default http://127.0.0.1:8000)
  AB_DEVICE_TOKEN    device bearer token    (required; from the Slots page "Add device" or /seed/dev)
  AB_INTERVAL        seconds between ticks  (default 5)
  AB_START_FRACTION  starting fill 0..1     (default 1.0)
  AB_SEED            RNG seed for reproducible runs (optional)

Usage:
  python edge/simulator.py            # run until Ctrl-C
  python edge/simulator.py --once     # one tick, then exit
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time

import requests

UNASSIGNED_TARE_GRAMS = 50.0


def next_weight(current: float, tare: float, full: float, rng: random.Random) -> tuple[float, bool]:
    """One tick of consumption. Returns (new grams, refilled?)."""
    span = full - tare
    new = current - span * rng.uniform(0.005, 0.03) + rng.uniform(-3, 3)
    refilled = False
    if new < tare + 0.05 * span and rng.random() < 0.25:
        new = full + rng.uniform(-3, 3)
        refilled = True
    return max(tare - 5, new), refilled


def build_payload(slots_state: list[dict]) -> dict:
    return {
        "readings": [
            {"tray": s["tray"], "slot": s["slot"], "weight_grams": round(s["weight"], 1)} for s in slots_state
        ]
    }


def init_state(layout: dict, start_fraction: float, rng: random.Random) -> list[dict]:
    """Flatten the /devices/me layout into per-slot simulation state."""
    state = []
    for tray in layout["trays"]:
        for slot in tray["slots"]:
            tare, full = slot.get("tare_grams"), slot.get("full_grams")
            calibrated = slot.get("product") is not None and tare is not None and full is not None and full > tare
            weight = tare + start_fraction * (full - tare) if calibrated else UNASSIGNED_TARE_GRAMS + rng.uniform(-2, 2)
            state.append(
                {
                    "tray": tray["position"],
                    "slot": slot["position"],
                    "name": slot["product"]["name"] if slot.get("product") else None,
                    "tare": tare,
                    "full": full,
                    "calibrated": calibrated,
                    "weight": weight,
                }
            )
    return state


def tick(state: list[dict], rng: random.Random) -> str:
    """Advance every slot one step; return a one-line human summary."""
    parts = []
    for s in state:
        if s["calibrated"]:
            s["weight"], refilled = next_weight(s["weight"], s["tare"], s["full"], rng)
            pct = round(100 * max(0.0, min(1.0, (s["weight"] - s["tare"]) / (s["full"] - s["tare"]))))
            parts.append(f"{s['name']} {pct}%" + (" (refilled)" if refilled else ""))
        else:
            s["weight"] = UNASSIGNED_TARE_GRAMS + rng.uniform(-2, 2)
    return " | ".join(parts) if parts else "no calibrated slots — assign products on the Slots page"


def fetch_layout(api: str, token: str) -> dict:
    r = requests.get(f"{api}/devices/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    r.raise_for_status()
    return r.json()


def post_readings(api: str, token: str, payload: dict) -> dict:
    r = requests.post(
        f"{api}/devices/me/readings", json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=10
    )
    r.raise_for_status()
    return r.json()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true", help="post one tick and exit")
    parser.add_argument("--interval", type=float, default=float(os.environ.get("AB_INTERVAL", "5")))
    args = parser.parse_args(argv)

    api = os.environ.get("AB_API_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.environ.get("AB_DEVICE_TOKEN")
    if not token:
        print("AB_DEVICE_TOKEN is not set. Create a device on the Slots page (or call /seed/dev) and copy its token.")
        return 2

    seed = os.environ.get("AB_SEED")
    rng = random.Random(int(seed)) if seed else random.Random()
    start_fraction = float(os.environ.get("AB_START_FRACTION", "1.0"))

    layout = fetch_layout(api, token)
    state = init_state(layout, start_fraction, rng)
    print(f"simulating '{layout['device']['name']}' — {len(state)} slots, every {args.interval:g}s")

    n = 0
    while True:
        n += 1
        summary = tick(state, rng)
        result = post_readings(api, token, build_payload(state))
        print(f"tick {n} | {summary} | applied={len(result['applied'])}", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nstopped")
