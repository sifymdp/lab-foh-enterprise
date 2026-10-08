import logging
import signal
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
    rag,
)
from app.seed import seed_database
from app.workers import camera_worker


import asyncio

async def _kitchen_alerts_background_task():
    while True:
        try:
            await asyncio.sleep(10)
            db = SessionLocal()
            try:
                from app.services import kitchen_alert_service
                kitchen_alert_service.evaluate_kitchen_alerts(db)
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception:
            pass


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
    alert_task = asyncio.create_task(_kitchen_alerts_background_task())
    yield
    # ── Graceful shutdown ──
    alert_task.cancel()
    try:
        await alert_task
    except (asyncio.CancelledError, Exception):
        pass
    # Stop stream workers first to prevent CancelledError cascades
    # from active StreamingResponse connections during shutdown.
    try:
        stream.stop_all_stream_workers()
    except Exception:
        pass
    try:
        await camera_worker.stop_worker()
    except Exception:
        pass
    try:
        camera_utils.release_captures()
    except Exception:
        pass
    try:
        unload_models()
    except Exception:
        pass


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

from starlette.types import ASGIApp, Scope, Receive, Send


class CancellationMiddleware:
    """Catches asyncio.CancelledError during client disconnects or server reload/shutdown

    to prevent unhandled ASGI exceptions from polluting Uvicorn logs.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await self.app(scope, receive, send)
        except (asyncio.CancelledError, GeneratorExit):
            pass


app.add_middleware(CancellationMiddleware)
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
app.include_router(rag.router)





@app.get("/health")
def health() -> dict:
    db_status = check_db_health()
    return {
        "ok": db_status["ok"],
        "api": "healthy",
        "database": db_status["status"],
    }

socket_app = app

