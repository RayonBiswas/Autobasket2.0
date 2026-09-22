"""Background worker: keeps every household's 'runs out' prediction fresh even when nothing is weighed.

Run alongside the API:  python -m app.worker
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from . import models
from .database import SessionLocal
from .services.inventory import recompute_all, reorder_list
from .services.proposals import propose_reorders
from .services.scout import refresh_product

log = logging.getLogger("autobasket.worker")
RECOMPUTE_EVERY_MINUTES = 15
REFRESH_PRICES_EVERY_MINUTES = 30


def run_once() -> int:
    with SessionLocal() as db:
        count = recompute_all(db)
    log.info("recomputed %d inventory rows", count)
    return count


def propose_once() -> int:
    """Ask every household about anything that needs reordering. Returns proposals created."""
    created = 0
    with SessionLocal() as db:
        for household in db.query(models.Household).all():
            created += len(propose_reorders(db, household))
    log.info("sent %d reorder proposal(s)", created)
    return created


def refresh_prices_once() -> int:
    """Refresh platform prices for every product some household needs to reorder. Returns products touched."""
    touched = 0
    with SessionLocal() as db:
        for household in db.query(models.Household).all():
            for row in reorder_list(db, household):
                product = db.get(models.Product, row["product_id"])
                result = refresh_product(db, product, household.pincode)
                touched += 1
                if result["refreshed"]:
                    log.info("refreshed %s prices for %s", result["refreshed"], product.name)
    log.info("price refresh checked %d product(s)", touched)
    return touched


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_once()
    propose_once()
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_once, "interval", minutes=RECOMPUTE_EVERY_MINUTES, id="recompute")
    scheduler.add_job(refresh_prices_once, "interval", minutes=REFRESH_PRICES_EVERY_MINUTES, id="refresh_prices")
    scheduler.add_job(propose_once, "interval", minutes=RECOMPUTE_EVERY_MINUTES, id="propose", jitter=60)
    log.info("worker started; recomputing every %d minutes", RECOMPUTE_EVERY_MINUTES)
    scheduler.start()


if __name__ == "__main__":
    main()
