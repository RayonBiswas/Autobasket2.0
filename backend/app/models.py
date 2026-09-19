from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# -------------------------
# HOUSEHOLD
# -------------------------

class Household(Base):
    __tablename__ = "households"

    id = Column(Integer, primary_key=True, index=True)
    adults = Column(Integer, default=2)
    children = Column(Integer, default=1)
    food_habit = Column(String, default="mixed")


# -------------------------
# ITEM
# -------------------------

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    total_qty = Column(Float)
    remaining_qty = Column(Float)
    min_threshold = Column(Float, default=0.0)

    predicted_daily_usage = Column(Float, default=1.0)

    last_order_date = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)


# -------------------------
# VENDOR
# -------------------------

class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    rating = Column(Float)
    vendor_type = Column(String)
    review_count = Column(Integer, default=1)  # 🔥 ADD THIS


# -------------------------
# VENDOR ITEM PRICE
# -------------------------

class VendorItem(Base):
    __tablename__ = "vendor_items"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer)
    item_name = Column(String)
    price = Column(Float)


# -------------------------
# ORDER
# -------------------------

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer)
    vendor_id = Column(Integer)
    status = Column(String, default="confirmed")