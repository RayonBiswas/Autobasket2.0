"""Delivery-app price sources: Blinkit, Zepto, Instamart.

None of these platforms publishes a price API, and scraping their apps is fragile and against their terms of
use, so no live fetcher ships by default. Each adapter is a real slot: plug a fetcher in (an approved data feed,
a partner API, or a scraper you are willing to maintain) and the rest of the system starts using it. Until then
the adapter reports "not configured" and the ranking uses the last known price, marked stale after 30 minutes.
"""

import logging

from ... import models
from .base import Fetcher, ScoutOffer

log = logging.getLogger("autobasket.scout")


class PlatformSource:
    def __init__(self, name: str, vendor_name: str, fetcher: Fetcher | None = None):
        self.name = name
        self.vendor_name = vendor_name
        self.fetcher = fetcher

    @property
    def configured(self) -> bool:
        return self.fetcher is not None

    def fetch(self, product: models.Product, pincode: str | None) -> list[ScoutOffer] | None:
        if self.fetcher is None:
            return None
        try:
            offers = self.fetcher(product, pincode)
        except Exception as exc:  # fail soft: a broken source must never take the others down
            log.warning("price source %s failed for %s: %s", self.name, product.name, exc)
            return None
        return [o for o in offers if o.vendor_name == self.vendor_name] or []


SOURCES: list[PlatformSource] = [
    PlatformSource("blinkit", "Blinkit"),
    PlatformSource("zepto", "Zepto"),
    PlatformSource("instamart", "Instamart"),
]
