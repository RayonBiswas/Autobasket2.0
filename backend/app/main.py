from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import auth, vision

app = FastAPI(title="AutoBasket API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(vision.router, prefix="/vision", tags=["Vision"])


@app.get("/")
def root():
    return {"message": "AutoBasket 2.0 Running"}


@app.get("/health")
def health():
    return {"status": "ok"}
