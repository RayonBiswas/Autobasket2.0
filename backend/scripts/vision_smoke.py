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
        raw = vision._openai_caller(vision.build_prompt(slots, [c.strip() for c in catalog.split(",") if c.strip()]), image, "image/jpeg")
    except Exception as exc:  # noqa: BLE001 - this script exists to show the failure
        print(f"FAILED after {time.time() - started:.1f}s: {exc}")
        return 1
    print(f"answered in {time.time() - started:.1f}s:\n{raw}\n")
    for g in vision._parse(raw, slots):
        box = getattr(g, "box", None)
        print(f"  slot {g.slot}: {g.item} ({g.confidence:.2f})" + (f" box={box}" if box else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
