"""Background camera scan worker — runs every 30 seconds."""

from __future__ import annotations

import asyncio
import logging
import threading

from app.config import settings
from app.database import SessionLocal
from app.services import camera_pipeline

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_stop_event = threading.Event()


async def _worker_loop() -> None:
    interval = settings.camera_scan_interval_seconds
    logger.info("Camera worker started (interval=%ds)", interval)
    while not _stop_event.is_set():
        try:
            db = SessionLocal()
            try:
                await camera_pipeline.run_scan_cycle(db, stop_event=_stop_event)
            finally:
                db.close()
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Camera scan cycle failed")

        try:
            for _ in range(max(1, interval)):
                if _stop_event.is_set():
                    break
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            break


def start_worker() -> None:
    global _worker_task
    if _worker_task is not None:
        return
    _stop_event.clear()
    _worker_task = asyncio.create_task(_worker_loop())


async def stop_worker() -> None:
    global _worker_task
    if _worker_task is None:
        return
    _stop_event.set()
    _worker_task.cancel()
    try:
        await asyncio.wait_for(_worker_task, timeout=2.0)
    except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
        pass
    _worker_task = None
