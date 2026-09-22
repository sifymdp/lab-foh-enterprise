import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Surface app loggers (camera pipeline, YOLO load, WS) on the console;
# uvicorn only configures its own loggers, so without this the camera
# pipeline runs silently and problems are invisible.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from app.core import camera_utils
from app.core.yolo_models import load_models, unload_models
from app.config import settings
from app.database import Base, SessionLocal, engine, migrate_schema, check_db_health
from app.routers import (
    audit,
    billing,
    auth,
    floors,
    guest,
    insights,
    menu,
    orders,
    payments,
    reservations,
    sessions,
    stream,
    tables,
    users,
    ws,
    cashier_shifts,
    refunds,
    revenue,
    settings as settings_router,
    rbac,
    vision,
    ai,
    ai_features,
    customer,
    ai_booking,
    ai_timeslot,
    ai_waitlist,
    voice,
)
from app.seed import seed_database
from app.workers import camera_worker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    models_loaded = load_models()
    if models_loaded:
        camera_worker.start_worker()
    yield
    stream.stop_all_stream_workers()
    await camera_worker.stop_worker()
    camera_utils.release_captures()
    unload_models()


app = FastAPI(title="FOH Table Management API", version="1.0.0", lifespan=lifespan)

# Allow all localhost origins and dev ports
cors_origins = settings.cors_origin_list + [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(floors.router)
app.include_router(tables.router)
app.include_router(sessions.router)
app.include_router(users.router)
app.include_router(menu.router)
app.include_router(reservations.router)
app.include_router(orders.router)
app.include_router(guest.router)
app.include_router(ws.router)
app.include_router(stream.router)
app.include_router(audit.router)
app.include_router(billing.router)
app.include_router(payments.router)
app.include_router(cashier_shifts.router)
app.include_router(refunds.router)
app.include_router(revenue.router)
app.include_router(settings_router.router)
app.include_router(rbac.router)
app.include_router(insights.router)
app.include_router(vision.router)
app.include_router(ai.router)
app.include_router(ai_features.router)
app.include_router(customer.router)
app.include_router(ai_booking.router)
app.include_router(ai_timeslot.router)
app.include_router(ai_waitlist.router)
app.include_router(voice.router)





@app.get("/health")
def health() -> dict:
    db_status = check_db_health()
    return {
        "ok": db_status["ok"],
        "api": "healthy",
        "database": db_status["status"],
    }

socket_app = app

