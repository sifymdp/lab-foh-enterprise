"""Background camera scan worker — runs every 30 seconds."""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.database import SessionLocal
from app.services import camera_pipeline

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None


async def _worker_loop() -> None:
    interval = settings.camera_scan_interval_seconds
    logger.info("Camera worker started (interval=%ds)", interval)
    while True:
        try:
            db = SessionLocal()
            try:
                await camera_pipeline.run_scan_cycle(db)
            finally:
                db.close()
        except Exception:
            logger.exception("Camera scan cycle failed")
        await asyncio.sleep(interval)


def start_worker() -> None:
    global _worker_task
    if _worker_task is not None:
        return
    _worker_task = asyncio.create_task(_worker_loop())


async def stop_worker() -> None:
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None
