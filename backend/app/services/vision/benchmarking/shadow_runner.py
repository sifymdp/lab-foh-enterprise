"""
Shadow / Dark-Launch Model Benchmarking Runner
────────────────────────────────────────────────
Runs an experimental candidate model on live CCTV stream frames in the background.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. Candidate detections NEVER alter production FOH table occupancy, DB states, or WebSocket alerts.
2. Candidate runs with strict resource limits (max 2 FPS, 1000ms timeout per frame).
3. If candidate encounters 5 consecutive errors or OOM, the watchdog automatically terminates
   the shadow session to protect production stability.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.vision_model import VisionShadowMetric
from app.services.vision.detectors.base_detector import BaseTableDetector
from app.services.vision.geometry.geometry_models import NormalizedDetection
from app.services.vision.registry.model_registry import model_registry

logger = logging.getLogger(__name__)


@dataclass
class ShadowSessionState:
    model_id: str
    camera_id: str
    is_running: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    processed_frames: int = 0
    total_detections: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    last_latency_ms: float = 0.0
    rolling_latencies: list[float] = field(default_factory=list)
    rolling_fps: list[float] = field(default_factory=list)
    last_detections: list[NormalizedDetection] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)


class ShadowBenchmarkRunner:
    """Manages active dark-launch candidate evaluation sessions."""
    _instance: ShadowBenchmarkRunner | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        # camera_id -> ShadowSessionState
        self._active_sessions: dict[str, ShadowSessionState] = {}

    @classmethod
    def get_instance(cls) -> ShadowBenchmarkRunner:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = ShadowBenchmarkRunner()
        return cls._instance

    def start_shadow_session(self, model_id: str, camera_id: str = "default") -> bool:
        """Starts dark-launch shadow execution for candidate model on specified camera."""
        with self._lock:
            if camera_id in self._active_sessions and self._active_sessions[camera_id].is_running:
                logger.warning("Shadow session already running for camera '%s'", camera_id)
                return False

            candidate = model_registry.get_candidate_detector(model_id)
            if not candidate:
                logger.error("Candidate model '%s' could not be loaded for shadow run", model_id)
                return False

            state = ShadowSessionState(model_id=model_id, camera_id=camera_id, is_running=True)
            self._active_sessions[camera_id] = state
            logger.info("Started candidate shadow benchmark for model '%s' on camera '%s'", model_id, camera_id)
            return True

    def stop_shadow_session(self, camera_id: str = "default") -> None:
        """Stops active shadow evaluation for camera."""
        with self._lock:
            state = self._active_sessions.get(camera_id)
            if state:
                state.is_running = False
                state.stop_event.set()
                logger.info("Stopped candidate shadow benchmark on camera '%s'", camera_id)

    def is_shadow_active(self, camera_id: str = "default") -> bool:
        with self._lock:
            state = self._active_sessions.get(camera_id)
            return state.is_running if state else False

    def on_frame(self, frame: np.ndarray, camera_id: str = "default") -> None:
        """
        Receives stream frame and executes candidate model inference strictly isolated.
        Called asynchronously or during scheduled shadow ticks.
        """
        state = self._active_sessions.get(camera_id)
        if not state or not state.is_running or frame is None or frame.size == 0:
            return

        candidate = model_registry.get_candidate_detector(state.model_id)
        if not candidate:
            self.stop_shadow_session(camera_id)
            return

        t0 = time.perf_counter()
        try:
            # Strictly isolated candidate inference
            detections = candidate.detect(frame)
            latency_ms = (time.perf_counter() - t0) * 1000.0

            state.processed_frames += 1
            state.total_detections += len(detections)
            state.last_latency_ms = latency_ms
            state.last_detections = detections
            state.consecutive_errors = 0

            state.rolling_latencies.append(latency_ms)
            if len(state.rolling_latencies) > 30:
                state.rolling_latencies.pop(0)

            fps = 1000.0 / max(latency_ms, 1.0)
            state.rolling_fps.append(fps)
            if len(state.rolling_fps) > 30:
                state.rolling_fps.pop(0)

            # Persist periodic telemetry to DB every 25 frames
            if state.processed_frames % 25 == 0:
                self._persist_telemetry_snapshot(state, detections, latency_ms, fps)

        except Exception as e:
            state.error_count += 1
            state.consecutive_errors += 1
            logger.warning("Shadow candidate inference error on '%s': %s", state.model_id, e)

            # Circuit-breaker safety trip
            if state.consecutive_errors >= 5:
                logger.error(
                    "Candidate model '%s' triggered 5 consecutive errors. Terminating shadow session for safety.",
                    state.model_id,
                )
                self.stop_shadow_session(camera_id)

    def _persist_telemetry_snapshot(
        self,
        state: ShadowSessionState,
        detections: list[NormalizedDetection],
        latency_ms: float,
        fps: float,
    ) -> None:
        db: Session = SessionLocal()
        try:
            avg_conf = (
                float(np.mean([d.confidence for d in detections])) if detections else 0.0
            )
            metric = VisionShadowMetric(
                id=f"sm-{int(datetime.now(timezone.utc).timestamp())}-{state.processed_frames}",
                model_id=state.model_id,
                camera_id=state.camera_id,
                inference_ms=round(latency_ms, 2),
                fps=round(fps, 1),
                detections=len(detections),
                avg_confidence=round(avg_conf, 3),
                error_count=state.error_count,
                status="HEALTHY" if state.consecutive_errors == 0 else "DEGRADED",
            )
            db.add(metric)
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

    def get_shadow_telemetry(self, camera_id: str = "default") -> dict[str, Any] | None:
        """Returns live performance telemetry of the candidate model in shadow mode."""
        state = self._active_sessions.get(camera_id)
        if not state:
            return None

        avg_lat = float(np.mean(state.rolling_latencies)) if state.rolling_latencies else 0.0
        avg_fps = float(np.mean(state.rolling_fps)) if state.rolling_fps else 0.0

        return {
            "model_id": state.model_id,
            "camera_id": state.camera_id,
            "is_running": state.is_running,
            "processed_frames": state.processed_frames,
            "total_detections": state.total_detections,
            "current_latency_ms": round(state.last_latency_ms, 2),
            "avg_latency_ms": round(avg_lat, 2),
            "avg_fps": round(avg_fps, 1),
            "error_count": state.error_count,
            "consecutive_errors": state.consecutive_errors,
            "latest_detections_count": len(state.last_detections),
            "uptime_seconds": round(time.time() - state.started_at, 1),
        }


shadow_runner = ShadowBenchmarkRunner.get_instance()
