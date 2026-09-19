"""Unit tests for edge/simulator.py (imported by path; it is not a package)."""

import importlib.util
import random
from pathlib import Path

SIM_PATH = Path(__file__).resolve().parents[2] / "edge" / "simulator.py"
spec = importlib.util.spec_from_file_location("simulator", SIM_PATH)
simulator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simulator)


def test_next_weight_stays_in_range_and_refills():
    rng = random.Random(1)
    tare, full = 50.0, 1080.0
    weight = full
    refills = 0
    for _ in range(200):
        weight, refilled = simulator.next_weight(weight, tare, full, rng)
        assert weight >= tare - 5
        assert weight <= full + 3
        refills += refilled
    assert refills >= 1


def test_build_payload_shape():
    payload = simulator.build_payload([{"tray": 1, "slot": 2, "weight": 123.456}])
    assert payload == {"readings": [{"tray": 1, "slot": 2, "weight_grams": 123.5}]}


def test_init_state_and_tick_from_layout():
    layout = {
        "device": {"id": 1, "name": "Dev Fridge"},
        "trays": [
            {
                "position": 1,
                "slots": [
                    {"position": 1, "product": {"name": "milk"}, "tare_grams": 50, "full_grams": 1080},
                    {"position": 2, "product": None, "tare_grams": None, "full_grams": None},
                ],
            }
        ],
    }
    rng = random.Random(7)
    state = simulator.init_state(layout, 0.5, rng)
    assert state[0]["calibrated"] is True
    assert abs(state[0]["weight"] - 565) < 1e-6
    assert state[1]["calibrated"] is False

    summary = simulator.tick(state, rng)
    assert summary.startswith("milk ")
    assert state[0]["weight"] < 565
