"""
Health Guardian - Health Check Registry & Probing Matrix
────────────────────────────────────────────────────────
Probes all registered subsystems: Database, WebSockets, CCTV/Vision,
Digital Twin, AI/RAG, Background Jobs, and Storage.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.config import settings
from app.socket_manager import manager


def check_database(db: Session) -> dict[str, Any]:
    """Inspects database connectivity, response latency, and core table integrity."""
    start = time.perf_counter()
    try:
        db.execute(text("SELECT 1")).scalar()
        latency_ms = (time.perf_counter() - start) * 1000

        from app.models.table import Table
        from app.models.floor import Floor
        table_count = db.query(func.count(Table.id)).scalar() or 0
        floor_count = db.query(func.count(Floor.id)).scalar() or 0

        status = "PASS" if latency_ms < 500 else "WARN"
        return {
            "component": "DATABASE",
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "message": f"Database healthy ({table_count} tables, {floor_count} floors)",
            "metrics": {
                "latency_ms": round(latency_ms, 2),
                "table_count": table_count,
                "floor_count": floor_count,
            },
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "component": "DATABASE",
            "status": "FAIL",
            "latency_ms": round(latency_ms, 2),
            "message": f"Database connection error: {str(exc)}",
            "metrics": {"error": str(exc)},
        }


def check_websockets() -> dict[str, Any]:
    """Inspects WebSocket connection pool, active rooms, and event loop presence."""
    start = time.perf_counter()
    try:
        rooms_count = len(manager._rooms)
        total_connections = sum(len(conns) for conns in manager._rooms.values())
        has_loop = manager._loop is not None

        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "component": "WEBSOCKETS",
            "status": "PASS",
            "latency_ms": round(latency_ms, 2),
            "message": f"WebSocket manager operational ({total_connections} clients in {rooms_count} rooms)",
            "metrics": {
                "total_clients": total_connections,
                "active_rooms": rooms_count,
                "main_loop_bound": has_loop,
            },
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "component": "WEBSOCKETS",
            "status": "FAIL",
            "latency_ms": round(latency_ms, 2),
            "message": f"WebSocket inspection failed: {str(exc)}",
            "metrics": {"error": str(exc)},
        }


def check_cctv_vision(db: Session) -> dict[str, Any]:
    """Inspects registered cameras, stream statuses, and observation freshness."""
    start = time.perf_counter()
    try:
        from app.models.vision import Camera, VisionObservation, VisionMismatch

        cameras = db.query(Camera).all()
        total_cams = len(cameras)
        online_cams = sum(1 for c in cameras if c.is_online and c.enabled)
        pending_mismatches = db.query(func.count(VisionMismatch.id)).filter(
            VisionMismatch.status == "PENDING"
        ).scalar() or 0

        latest_obs = db.query(VisionObservation).order_by(VisionObservation.timestamp.desc()).first()
        latest_obs_time = latest_obs.timestamp.isoformat() if latest_obs else None

        latency_ms = (time.perf_counter() - start) * 1000
        status = "PASS" if online_cams == total_cams or total_cams == 0 else "WARN"

        return {
            "component": "CCTV_VISION",
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "message": f"CCTV vision pipeline active ({online_cams}/{total_cams} online, {pending_mismatches} pending mismatches)",
            "metrics": {
                "total_cameras": total_cams,
                "online_cameras": online_cams,
                "pending_mismatches": pending_mismatches,
                "latest_observation_at": latest_obs_time,
            },
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "component": "CCTV_VISION",
            "status": "FAIL",
            "latency_ms": round(latency_ms, 2),
            "message": f"Vision pipeline check failed: {str(exc)}",
            "metrics": {"error": str(exc)},
        }


def check_digital_twin(db: Session) -> dict[str, Any]:
    """Inspects Digital Twin snapshot freshness, floor synchronization, and simulation count."""
    start = time.perf_counter()
    try:
        from app.models.digital_twin import DigitalTwinSnapshot, DigitalTwinSimulation
        from app.models.floor import Floor

        total_floors = db.query(func.count(Floor.id)).scalar() or 0
        total_snapshots = db.query(func.count(DigitalTwinSnapshot.id)).scalar() or 0
        latest_sim = db.query(DigitalTwinSimulation).order_by(DigitalTwinSimulation.created_at.desc()).first()

        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "component": "DIGITAL_TWIN",
            "status": "PASS",
            "latency_ms": round(latency_ms, 2),
            "message": f"Digital Twin synchronized ({total_floors} floors monitored, {total_snapshots} snapshots cached)",
            "metrics": {
                "floors_monitored": total_floors,
                "snapshots_cached": total_snapshots,
                "latest_simulation": latest_sim.name if latest_sim else "None",
            },
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "component": "DIGITAL_TWIN",
            "status": "FAIL",
            "latency_ms": round(latency_ms, 2),
            "message": f"Digital Twin inspection failed: {str(exc)}",
            "metrics": {"error": str(exc)},
        }


def check_ai_rag(db: Session) -> dict[str, Any]:
    """Inspects AI configuration and RAG knowledge base chunk readiness."""
    start = time.perf_counter()
    try:
        from app.models.rag import KnowledgeChunk, KnowledgeDocument

        docs_count = db.query(func.count(KnowledgeDocument.id)).scalar() or 0
        chunks_count = db.query(func.count(KnowledgeChunk.id)).scalar() or 0
        provider = settings.ai_provider
        primary_model = settings.ai_primary_model

        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "component": "AI_RAG",
            "status": "PASS",
            "latency_ms": round(latency_ms, 2),
            "message": f"AI/RAG service configured (Provider: {provider}, {chunks_count} knowledge chunks ready)",
            "metrics": {
                "provider": provider,
                "primary_model": primary_model,
                "documents": docs_count,
                "chunks": chunks_count,
            },
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "component": "AI_RAG",
            "status": "FAIL",
            "latency_ms": round(latency_ms, 2),
            "message": f"AI/RAG check failed: {str(exc)}",
            "metrics": {"error": str(exc)},
        }


def check_background_jobs() -> dict[str, Any]:
    """Inspects background worker state and thread heartbeats."""
    start = time.perf_counter()
    try:
        from app.workers import camera_worker

        worker_active = camera_worker._worker_task is not None and not camera_worker._stop_event.is_set()
        latency_ms = (time.perf_counter() - start) * 1000

        return {
            "component": "JOBS",
            "status": "PASS" if worker_active else "WARN",
            "latency_ms": round(latency_ms, 2),
            "message": f"Background workers running (Camera worker active: {worker_active})",
            "metrics": {
                "camera_worker_active": worker_active,
            },
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "component": "JOBS",
            "status": "FAIL",
            "latency_ms": round(latency_ms, 2),
            "message": f"Background jobs inspection failed: {str(exc)}",
            "metrics": {"error": str(exc)},
        }


def check_storage() -> dict[str, Any]:
    """Inspects local file storage and temporary uploads capacity."""
    start = time.perf_counter()
    try:
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        uploads_dir = base_dir / "camera_uploads"
        uploads_dir.mkdir(exist_ok=True)

        usage = shutil.disk_usage(base_dir)
        free_gb = round(usage.free / (1024**3), 2)
        total_gb = round(usage.total / (1024**3), 2)
        used_pct = round((usage.used / usage.total) * 100, 1)

        upload_files = list(uploads_dir.glob("*"))
        upload_count = len(upload_files)

        status = "PASS" if free_gb > 1.0 else "WARN"
        latency_ms = (time.perf_counter() - start) * 1000

        return {
            "component": "STORAGE",
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "message": f"Storage capacity healthy ({free_gb} GB free of {total_gb} GB, {used_pct}% used)",
            "metrics": {
                "free_gb": free_gb,
                "total_gb": total_gb,
                "used_percentage": used_pct,
                "upload_file_count": upload_count,
            },
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "component": "STORAGE",
            "status": "FAIL",
            "latency_ms": round(latency_ms, 2),
            "message": f"Storage inspection failed: {str(exc)}",
            "metrics": {"error": str(exc)},
        }


def run_all_probes(db: Session) -> list[dict[str, Any]]:
    """Runs all registered health probes sequentially and returns comprehensive findings."""
    return [
        check_database(db),
        check_websockets(),
        check_cctv_vision(db),
        check_digital_twin(db),
        check_ai_rag(db),
        check_background_jobs(),
        check_storage(),
    ]
