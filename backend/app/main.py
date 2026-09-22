from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings, validate_production
from .routes import (
    agent,
    auth,
    devices,
    households,
    inventory,
    notifications,
    orders,
    payments,
    products,
    recommendations,
    seed,
    slots,
    telegram,
    vendor,
    vendors,
    vision,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_production(get_settings())
    yield


app = FastAPI(title="AutoBasket API", lifespan=lifespan)

_origins = get_settings().cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(households.router, prefix="/households", tags=["Households"])
app.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(devices.router, prefix="/devices", tags=["Devices"])
app.include_router(slots.router, prefix="/slots", tags=["Slots"])
app.include_router(vendors.router, prefix="/vendors", tags=["Vendors"])
app.include_router(vendor.router, prefix="/vendor", tags=["Vendor portal"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(telegram.router, prefix="/telegram", tags=["Telegram"])
app.include_router(payments.router, prefix="/payments", tags=["Payments"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])
app.include_router(agent.router, prefix="/agent", tags=["Agent"])
app.include_router(seed.router, prefix="/seed", tags=["Seed"])
app.include_router(vision.router, prefix="/vision", tags=["Vision"])


@app.get("/")
def root():
    return {"message": "AutoBasket 2.0 Running"}


@app.get("/health")
def health():
    return {"status": "ok"}
