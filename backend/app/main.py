from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_models
from app.routers import auth, bookings, carriers, geocoding, messaging, payments, tracking

settings = get_settings()

app = FastAPI(
    title="LogiConnect API",
    description="Backend for the LogiConnect / FindMyGP marketplace — France ⇄ Sénégal package delivery.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(carriers.router)
app.include_router(bookings.router)
app.include_router(tracking.router)
app.include_router(messaging.router)
app.include_router(payments.router)
app.include_router(geocoding.router)


@app.on_event("startup")
async def on_startup():
    # MVP schema management: create tables if they don't exist yet.
    # For real schema evolution once this is live, replace with Alembic migrations.
    await init_models()


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}
