"""
Two-Speed Vision Pipeline & Centralized Frame Scheduler
─────────────────────────────────────────────────────────
Decouples static physical furniture detection from high-frequency dynamic tracking.

Principles:
1. Static Table Layer:
   - Does NOT run at 25-30 FPS.
   - Runs on camera startup, manager manual trigger, configurable interval (default: 5 min),
     or after persistent layout mismatches.
2. Dynamic Occupancy Layer:
   - Evaluates person detection and ByteTrack tracking at configurable 2-5 FPS,
     independent of camera capture FPS.
3. Telemetry & Hardware Monitoring:
   - Tracks FPS, latencies, CPU/GPU telemetry, and dropped frames.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SchedulerTelemetry:
    camera_fps: float = 25.0
    dynamic_inference_fps: float = 2.0
    table_model_inference_ms: float = 0.0
    person_model_inference_ms: float = 0.0
    tracking_latency_ms: float = 0.0
    total_pipeline_latency_ms: float = 0.0
    cpu_usage_pct: float = 0.0
    gpu_memory_mb: float = 0.0
    dropped_frames_count: int = 0
    last_table_scan_time: float = 0.0
    next_table_scan_time: float = 0.0
    table_scan_interval_minutes: float = 5.0
    is_table_scan_in_progress: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_fps": round(self.camera_fps, 1),
            "dynamic_inference_fps": round(self.dynamic_inference_fps, 1),
            "table_model_inference_ms": round(self.table_model_inference_ms, 2),
            "person_model_inference_ms": round(self.person_model_inference_ms, 2),
            "tracking_latency_ms": round(self.tracking_latency_ms, 2),
            "total_pipeline_latency_ms": round(self.total_pipeline_latency_ms, 2),
            "cpu_usage_pct": round(self.cpu_usage_pct, 1),
            "gpu_memory_mb": round(self.gpu_memory_mb, 1),
            "dropped_frames": self.dropped_frames_count,
            "last_table_scan_seconds_ago": round(time.time() - self.last_table_scan_time, 1) if self.last_table_scan_time > 0 else None,
            "table_scan_interval_minutes": self.table_scan_interval_minutes,
            "is_table_scan_in_progress": self.is_table_scan_in_progress,
        }


class FrameScheduler:
    """
    Manages multi-speed scheduling of vision tasks per camera stream.
    """

    def __init__(
        self,
        camera_id: str,
        target_camera_fps: float = 25.0,
        dynamic_inference_fps: float = 2.5,
        table_scan_interval_minutes: float = 5.0,
    ):
        self.camera_id = camera_id
        self.target_camera_fps = target_camera_fps
        self.dynamic_inference_fps = dynamic_inference_fps
        self.table_scan_interval_minutes = table_scan_interval_minutes

        self.telemetry = SchedulerTelemetry(
            camera_fps=target_camera_fps,
            dynamic_inference_fps=dynamic_inference_fps,
            table_scan_interval_minutes=table_scan_interval_minutes,
        )

        self._last_dynamic_frame_time: float = 0.0
        self._last_camera_frame_time: float = 0.0
        self._frame_count: int = 0
        self._fps_window_start: float = time.monotonic()
        self._manual_table_scan_requested: bool = False

    def request_manual_table_scan(self) -> None:
        """Flags that a manager requested an immediate table layout verification."""
        self._manual_table_scan_requested = True
        logger.info("Manual table layout verification requested for camera '%s'", self.camera_id)

    def should_run_dynamic_tracking(self) -> bool:
        """
        Determines whether the incoming camera frame should run through
        heavy person detection & ByteTrack tracking (e.g. at 2-5 FPS).
        """
        now = time.monotonic()
        min_interval = 1.0 / max(self.dynamic_inference_fps, 0.5)

        if now - self._last_dynamic_frame_time >= min_interval:
            self._last_dynamic_frame_time = now
            return True
        return False

    def should_run_static_table_scan(self) -> bool:
        """
        Determines whether static table layout discovery should execute.
        Rules:
        1. Camera startup (never run before)
        2. Configurable interval has elapsed (default: 5 minutes)
        3. Manager manually requested verification
        """
        if self._manual_table_scan_requested:
            self._manual_table_scan_requested = False
            return True

        now = time.time()
        if self.telemetry.last_table_scan_time == 0.0:
            # Startup scan
            return True

        interval_seconds = self.table_scan_interval_minutes * 60.0
        if now - self.telemetry.last_table_scan_time >= interval_seconds:
            return True

        return False

    def record_table_scan_completed(self, latency_ms: float) -> None:
        """Marks table scan complete and updates telemetry."""
        now = time.time()
        self.telemetry.last_table_scan_time = now
        self.telemetry.next_table_scan_time = now + (self.table_scan_interval_minutes * 60.0)
        self.telemetry.table_model_inference_ms = latency_ms
        self.telemetry.is_table_scan_in_progress = False

    def record_dynamic_tracking_completed(
        self,
        person_latency_ms: float,
        tracking_latency_ms: float,
        total_latency_ms: float,
    ) -> None:
        """Updates dynamic tracking metrics."""
        self.telemetry.person_model_inference_ms = person_latency_ms
        self.telemetry.tracking_latency_ms = tracking_latency_ms
        self.telemetry.total_pipeline_latency_ms = total_latency_ms

        # Compute rolling system metrics
        try:
            import psutil
            self.telemetry.cpu_usage_pct = psutil.cpu_percent()
        except Exception:
            pass

        try:
            import torch
            if torch.cuda.is_available():
                self.telemetry.gpu_memory_mb = torch.cuda.memory_allocated() / (1024 * 1024)
        except Exception:
            pass
