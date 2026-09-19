"""Background worker: keeps every household's 'runs out' prediction fresh even when nothing is weighed.

Run alongside the API:  python -m app.worker
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from .database import SessionLocal
from .services.inventory import recompute_all

log = logging.getLogger("autobasket.worker")
RECOMPUTE_EVERY_MINUTES = 15


def run_once() -> int:
    with SessionLocal() as db:
        count = recompute_all(db)
    log.info("recomputed %d inventory rows", count)
    return count


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_once()
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_once, "interval", minutes=RECOMPUTE_EVERY_MINUTES, id="recompute")
    log.info("worker started; recomputing every %d minutes", RECOMPUTE_EVERY_MINUTES)
    scheduler.start()


if __name__ == "__main__":
    main()
