"""The one interface every price source implements."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ... import models


@dataclass
class ScoutOffer:
    """One price for one product at one seller, as reported by a source."""

    vendor_name: str
    price: float
    in_stock: bool = True
    eta_minutes: int | None = None


# A fetcher answers "what does this seller charge for this product in this pincode?" or raises.
Fetcher = Callable[[models.Product, str | None], list[ScoutOffer]]


class PriceSource(Protocol):
    name: str

    def fetch(self, product: models.Product, pincode: str | None) -> list[ScoutOffer] | None:
        """Return offers, or None when the source is not configured or failed (the caller keeps old prices)."""
        ...
