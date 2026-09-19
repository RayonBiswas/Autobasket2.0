from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import agent, auth, households, inventory, orders, seed, vendors, vision

app = FastAPI(title="AutoBasket API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(households.router, prefix="/households", tags=["Households"])
app.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
app.include_router(vendors.router, prefix="/vendors", tags=["Vendors"])
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
