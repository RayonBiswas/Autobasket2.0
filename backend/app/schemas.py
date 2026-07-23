from pydantic import BaseModel


class ItemCreate(BaseModel):
    name: str
    total_qty: float
    remaining_qty: float
    min_threshold: float


class VendorCreate(BaseModel):
    name: str
    vendor_type: str
    rating: float
    price: float