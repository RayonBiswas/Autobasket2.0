from enum import StrEnum


class UserRole(StrEnum):
    HOUSEHOLD = "household"
    VENDOR = "vendor"
    ADMIN = "admin"


class MemberRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class ProductUnit(StrEnum):
    G = "g"
    ML = "ml"
    PCS = "pcs"


class EventSource(StrEnum):
    WEIGHT = "weight"
    VISION = "vision"
    MANUAL = "manual"
    ORDER = "order"


class StockStatus(StrEnum):
    SAFE = "safe"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class VendorKind(StrEnum):
    KIRANA = "kirana"
    PLATFORM = "platform"


class OfferSource(StrEnum):
    PORTAL = "portal"
    SCRAPER = "scraper"
    SEED = "seed"


class OrderStatus(StrEnum):
    PROPOSED = "proposed"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    PAID = "paid"
    ACCEPTED = "accepted"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    VERIFIED = "verified"
    HANDOFF = "handoff"
    CANCELLED = "cancelled"


class OrderChannel(StrEnum):
    KIRANA = "kirana"
    HANDOFF = "handoff"
