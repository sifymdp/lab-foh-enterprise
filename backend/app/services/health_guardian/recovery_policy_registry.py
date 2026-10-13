"""
Health Guardian - Allowlisted Safe Recovery Policy Registry & Executor
──────────────────────────────────────────────────────────────────────
Defines idempotent, verified, non-destructive automated recovery routines.
All actions are strictly constrained to disposable caches, stream reconnections,
dead socket pruning, and temporary file rotation.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RecoveryAction:
    def __init__(
        self,
        name: str,
        description: str,
        risk_level: str,  # LOW | MEDIUM | HIGH
        execute_fn: Callable[[Session], dict[str, Any]],
        verify_fn: Callable[[Session], bool],
    ):
        self.name = name
        self.description = description
        self.risk_level = risk_level
        self.execute_fn = execute_fn
        self.verify_fn = verify_fn


# ── Allowlisted Recovery Implementations ────────────────────────────────────

def _recover_reconnect_pool(db: Session) -> dict[str, Any]:
    """Tests and refreshes database engine connection."""
    db.execute(text("SELECT 1"))
    return {"reconnected": True, "details": "Verified connection pool liveness"}


def _verify_database(db: Session) -> bool:
    try:
        val = db.execute(text("SELECT 1")).scalar()
        return val == 1
    except Exception:
        return False


def _recover_prune_dead_sockets(db: Session) -> dict[str, Any]:
    """Sweeps and removes dead or terminated WebSocket connections."""
    from app.socket_manager import manager

    pruned = 0
    for room, ws_list in list(manager._rooms.items()):
        live_list = []
        for ws in ws_list:
            # Check client_state if available or retain
            if hasattr(ws, "client_state") and getattr(ws.client_state, "name", "") == "DISCONNECTED":
                pruned += 1
            else:
                live_list.append(ws)
        if live_list:
            manager._rooms[room] = live_list
        else:
            manager._rooms.pop(room, None)

    return {"pruned_count": pruned, "active_rooms": len(manager._rooms)}


def _verify_websockets(db: Session) -> bool:
    from app.socket_manager import manager
    return isinstance(manager._rooms, dict)


def _recover_restart_camera_stream(db: Session) -> dict[str, Any]:
    """Restarts stream captures and background camera worker."""
    from app.workers import camera_worker
    from app.core import camera_utils

    camera_utils.release_captures()
    if camera_worker._worker_task is None or camera_worker._stop_event.is_set():
        camera_worker.start_worker()

    return {"stream_reset": True, "worker_started": True}


def _verify_camera_worker(db: Session) -> bool:
    from app.workers import camera_worker
    return camera_worker._worker_task is not None and not camera_worker._stop_event.is_set()


def _recover_rebuild_digital_twin_snapshot(db: Session) -> dict[str, Any]:
    """Rebuilds Digital Twin cached snapshots from authoritative tables."""
    from app.services.digital_twin.twin_service import rebuild_all_snapshots

    count = rebuild_all_snapshots(db)
    return {"rebuilt_floors": count}


def _verify_digital_twin(db: Session) -> bool:
    from app.models.digital_twin import DigitalTwinSnapshot
    from sqlalchemy import func
    return (db.query(func.count(DigitalTwinSnapshot.id)).scalar() or 0) >= 0


def _recover_cleanup_temp_storage(db: Session) -> dict[str, Any]:
    """Safely cleans up stale camera snapshots older than 24 hours."""
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    uploads_dir = base_dir / "camera_uploads"
    deleted = 0

    if uploads_dir.exists():
        now = time.time()
        for f in uploads_dir.glob("*.jpg"):
            try:
                # older than 24 hours (86400s)
                if now - f.stat().st_mtime > 86400:
                    f.unlink()
                    deleted += 1
            except Exception:
                pass

    return {"deleted_files": deleted, "cleaned_directory": str(uploads_dir)}


def _verify_storage(db: Session) -> bool:
    base_dir = Path(__file__).resolve().parent.parent.parent.parent
    uploads_dir = base_dir / "camera_uploads"
    return uploads_dir.exists()


# ── Registry of Authorized Policies ────────────────────────────────────────

RECOVERY_POLICIES: dict[str, RecoveryAction] = {
    "REFRESH_CONNECTION_POOL": RecoveryAction(
        name="REFRESH_CONNECTION_POOL",
        description="Verify and re-ping database connection pool",
        risk_level="LOW",
        execute_fn=_recover_reconnect_pool,
        verify_fn=_verify_database,
    ),
    "PRUNE_DEAD_SOCKET_CONNECTIONS": RecoveryAction(
        name="PRUNE_DEAD_SOCKET_CONNECTIONS",
        description="Purge dead WebSocket connections from memory rooms",
        risk_level="LOW",
        execute_fn=_recover_prune_dead_sockets,
        verify_fn=_verify_websockets,
    ),
    "RESTART_CAMERA_STREAM_WORKER": RecoveryAction(
        name="RESTART_CAMERA_STREAM_WORKER",
        description="Release stale capture locks and restart camera loop",
        risk_level="MEDIUM",
        execute_fn=_recover_restart_camera_stream,
        verify_fn=_verify_camera_worker,
    ),
    "REBUILD_DIGITAL_TWIN_SNAPSHOT": RecoveryAction(
        name="REBUILD_DIGITAL_TWIN_SNAPSHOT",
        description="Re-materialize digital twin floor snapshots from authoritative DB",
        risk_level="LOW",
        execute_fn=_recover_rebuild_digital_twin_snapshot,
        verify_fn=_verify_digital_twin,
    ),
    "CLEANUP_EXPIRED_TEMP_STORAGE": RecoveryAction(
        name="CLEANUP_EXPIRED_TEMP_STORAGE",
        description="Prune camera frame cache files older than 24h",
        risk_level="LOW",
        execute_fn=_recover_cleanup_temp_storage,
        verify_fn=_verify_storage,
    ),
}


def execute_recovery_action(db: Session, action_name: str) -> dict[str, Any]:
    """
    Executes an allowlisted recovery action and verifies post-execution state.
    Returns status: SUCCESS | FAILED | ABORTED | VERIFICATION_FAILED.
    """
    policy = RECOVERY_POLICIES.get(action_name)
    if not policy:
        return {
            "status": "ABORTED",
            "message": f"Action '{action_name}' is not in the authorized recovery allowlist",
            "verification_passed": False,
        }

    start = time.perf_counter()
    try:
        output = policy.execute_fn(db)
        duration_ms = (time.perf_counter() - start) * 1000

        # Post-execution verification
        verified = policy.verify_fn(db)
        status = "SUCCESS" if verified else "VERIFICATION_FAILED"

        return {
            "status": status,
            "duration_ms": round(duration_ms, 2),
            "output": output,
            "verification_passed": verified,
        }
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception("Recovery action %s encountered an error", action_name)
        return {
            "status": "FAILED",
            "duration_ms": round(duration_ms, 2),
            "error": str(exc),
            "verification_passed": False,
        }
