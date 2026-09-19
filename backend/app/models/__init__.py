"""ORM models. Import this package once so every table registers on Base.metadata."""

from .auth import Household, HouseholdMember, OtpCode, User
from .catalog import Product, Vendor, VendorOffer
from .device import Device, Slot, Tray
from .enums import (
    EventSource,
    MemberRole,
    OfferSource,
    OrderChannel,
    OrderStatus,
    ProductUnit,
    StockStatus,
    UserRole,
    VendorKind,
)
from .inventory import InventoryEvent, InventoryState
from .orders import Order, OrderItem

__all__ = [
    "User", "OtpCode", "Household", "HouseholdMember",
    "Device", "Tray", "Slot",
    "Product", "Vendor", "VendorOffer",
    "InventoryEvent", "InventoryState",
    "Order", "OrderItem",
    "UserRole", "MemberRole", "ProductUnit", "EventSource", "StockStatus",
    "VendorKind", "OfferSource", "OrderStatus", "OrderChannel",
]
