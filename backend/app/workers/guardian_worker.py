"""
Enterprise Backend Health Guardian Background Worker
────────────────────────────────────────────────────
Persistent, restart-safe background worker that coordinates:
1. Comprehensive 12-hour automated system health audit & safe self-recovery cycle.
2. Lightweight 60-second periodic heartbeat probe.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone

from app.database import SessionLocal
from app.services.health_guardian.guardian_service import (
    run_comprehensive_audit,
    run_lightweight_probe,
)
from app.models.health_guardian import HealthAudit

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_stop_event = threading.Event()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _guardian_loop() -> None:
    logger.info("Autonomous Health Guardian worker started (12-hour comprehensive cycle enabled)")

    # 1. On startup: inspect durable database state to check if 12h run is due
    try:
        db = SessionLocal()
        try:
            latest = db.query(HealthAudit).order_by(HealthAudit.started_at.desc()).first()
            now = _utc_now()
            next_run = _ensure_utc(latest.next_scheduled_run) if latest else None
            if not latest or not next_run or now >= next_run:
                logger.info("Health Guardian: Comprehensive 12-hour audit is due, initiating...")
                run_comprehensive_audit(db, audit_type="SCHEDULED_12H")
            else:
                logger.info("Health Guardian: Next comprehensive audit scheduled for %s", next_run)
        finally:
            db.close()
    except Exception:
        logger.exception("Initial health check cycle error")

    # 2. Main loop: 60-second heartbeat check
    heartbeat_counter = 0
    while not _stop_event.is_set():
        try:
            await asyncio.sleep(60)
            if _stop_event.is_set():
                break

            heartbeat_counter += 1
            db = SessionLocal()
            try:
                # Lightweight probe every 60s
                run_lightweight_probe(db)

                # Check if 12-hour comprehensive audit is due
                latest = db.query(HealthAudit).order_by(HealthAudit.started_at.desc()).first()
                now = _utc_now()
                next_run = _ensure_utc(latest.next_scheduled_run) if latest else None
                if latest and next_run and now >= next_run:
                    logger.info("Health Guardian: 12-hour schedule trigger reached, initiating audit cycle...")
                    run_comprehensive_audit(db, audit_type="SCHEDULED_12H")
            finally:
                db.close()

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Error in health guardian background loop")


def start_worker() -> None:
    global _worker_task
    if _worker_task is not None:
        return
    _stop_event.clear()
    _worker_task = asyncio.create_task(_guardian_loop())


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
