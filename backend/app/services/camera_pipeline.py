"""Camera pipeline hooks for YOLO-based table-state monitoring."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.core import camera_utils
from app.core.roi_matching import match_detection_for_roi
from app.core.status_machine import ACTIVE_SESSION_STATUSES, is_valid_transition
from app.core.yolo_models import (
    TableStateDetection,
    detect_table_state,
    detect_table_state_consensus,
    is_table_state_model_ready,
    iter_full_frame_detections,
    smooth_table_state,
)
from app.models import DiningSession, Table
from app.schemas.ai import AIEventCreate
from app.services import ai_service, table_service
from app.services.ollama_service import generate_text

logger = logging.getLogger(__name__)


def process_frame(frame: Any, table_id: str, roi_coords: str | None = None) -> dict[str, Any] | None:
    """Classify a table ROI from a frame.

    Returns a small payload useful for logs/tests. ``clean`` with zero confidence
    means the model produced no ROI box, which is the trained workflow's clean
    fallback.
    """
    roi = camera_utils.parse_roi(roi_coords)
    cropped = camera_utils.crop_roi(frame, roi) if roi else frame
    if cropped is None:
        return None

    detection = detect_table_state(cropped)
    if detection is None:
        detection = TableStateDetection(label="clean", confidence=0.0)

    return {
        "table_id": table_id,
        "label": detection.label,
        "confidence": detection.confidence,
    }


def process_frame_sequence(
    frames: list[Any],
    table_id: str,
    roi_coords: str | None = None,
) -> dict[str, Any] | None:
    """Classify a table ROI from several nearby frames for a steadier result."""
    roi = camera_utils.parse_roi(roi_coords)
    cropped_frames = [
        cropped
        for cropped in (
            camera_utils.crop_roi(frame, roi) if roi else frame
            for frame in frames
        )
        if cropped is not None
    ]
    if not cropped_frames:
        return None

    detection = detect_table_state_consensus(cropped_frames)
    if detection is None:
        detection = TableStateDetection(label="clean", confidence=0.0)

    return {
        "table_id": table_id,
        "label": detection.label,
        "confidence": detection.confidence,
    }


def _latest_active_session(db: Session, table_id: str) -> DiningSession | None:
    return table_service.active_session_for_table(db, table_id)


def _emit_table_updated(table: Table) -> None:
    table_service._emit_table_updated(table)


def _change_status(db: Session, table: Table, new_status: str) -> bool:
    if table.status == new_status or not is_valid_transition(table.status, new_status):
        return False

    old_status = table.status
    session = _latest_active_session(db, table.id)
    table.status = new_status
    table_service._on_status_change(table, old_status, new_status)
    if session:
        session.status = new_status
        if new_status not in ACTIVE_SESSION_STATUSES:
            # camera-driven walkout closes the session, same as close_session
            session.closed_at = datetime.now(timezone.utc)
    table_service.record_history(
        db,
        table.id,
        old_status,
        new_status,
        user_id=None,
        session_id=session.id if session else None,
    )
    logger.info("Camera changed table %s from %s to %s", table.number, old_status, new_status)
    return True


# The camera has authority over exactly four transitions:
#   AVAILABLE → SEATED    (3 consecutive occupied ticks)
#   SEATED    → CLEANING  (3 consecutive guest-free ticks, table left dirty)
#   SEATED    → AVAILABLE (3 consecutive guest-free ticks, table left clean)
#   CLEANING  → AVAILABLE (3 consecutive clean ticks after grace period)
# It NEVER touches payment states — a table in BILLING stays in BILLING no
# matter what the camera sees; there it only watches for departures. ACTIVE
# tables (open orders) are also left alone: those resolve through billing.
CAMERA_SCAN_STATUSES = ("AVAILABLE", "SEATED", "BILLING", "CLEANING")


def _iso_to_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _send_alert(
    db: Session,
    table: Table,
    event_type: str,
    target_role: str,
    prompt: str,
    fallback: str,
) -> None:
    """Create an alert with an Ollama-worded message (template fallback if down)."""
    ai_service.create_alert(
        db,
        AIEventCreate(
            table_id=table.id,
            event_type=event_type,
            target_role=target_role,
            message=generate_text(prompt, fallback=fallback),
        ),
    )


def _apply_tick(db: Session, table: Table, label: str | None, now: datetime) -> bool:
    """Advance one table by one 30-second decision tick.

    ``label`` is the smoothed camera reading for this tick ('clean' / 'dirty' /
    'occupied'), or None when the camera produced no reading. Counters count
    ticks, not video frames, and alerts are edge-triggered: they fire once the
    moment their condition first becomes true, then stay silent until the flag
    is re-armed (status change, or a person reappearing during BILLING).
    Returns True when the table's status changed.
    """
    changed = False
    required = max(settings.consecutive_scans_required, 1)

    if table.status == "AVAILABLE":
        if label == "occupied":
            table.consecutive_person_scans += 1
            if table.consecutive_person_scans >= required:
                changed = _change_status(db, table, "SEATED")
        else:
            # any tick without a person (including "no reading") resets the streak
            table.consecutive_person_scans = 0

    elif table.status == "SEATED":
        if label == "occupied":
            table.consecutive_empty_scans = 0
        elif label in ("clean", "dirty"):
            table.consecutive_empty_scans += 1
            if table.consecutive_empty_scans >= required:
                # Guests gone: the tick label that completes the streak decides
                # where the table lands — mess needs a busser, clean goes back
                # into rotation immediately.
                changed = _change_status(
                    db, table, "CLEANING" if label == "dirty" else "AVAILABLE"
                )
        # label None → no reading this tick; hold the streak as-is

    elif table.status == "BILLING":
        # Watch for guests leaving without paying. Status never changes here.
        if label == "occupied":
            table.consecutive_empty_scans = 0
            # person reappeared — re-arm so a real future departure alerts again
            table.departure_alert_sent = False
        elif label in ("clean", "dirty"):
            table.consecutive_empty_scans += 1
            if table.consecutive_empty_scans >= required:
                from app.services import loss_prevention_service

                exposure = loss_prevention_service.calculate_table_exposure(db, table.id)
                if exposure and exposure.get("unpaid_total", 0) > 0 and not getattr(table, "walkout_alert_sent", False):
                    loss_prevention_service.trigger_walkout_alert(
                        db, table, exposure, reason="Guests vacated while in BILLING without paying"
                    )
                    table.departure_alert_sent = True
                elif not table.departure_alert_sent:
                    _send_alert(
                        db,
                        table,
                        event_type="DEPARTURE_ALERT",
                        target_role="MANAGER",
                        prompt=(
                            f"Restaurant table {table.number} is in BILLING (bill requested, not yet paid) "
                            "and the camera has seen it empty for 3 consecutive scans. Write one short, "
                            "urgent plain-English sentence alerting the manager that the guests may have "
                            "left without paying. No JSON, no codes."
                        ),
                        fallback=(
                            f"Table {table.number} appears empty while still in BILLING — "
                            "guests may have left without paying."
                        ),
                    )
                    table.departure_alert_sent = True
        # label None → no reading this tick; hold counters and flags as-is

    elif table.status == "CLEANING":
        if not table.cleaning_started_at:
            # legacy rows or transitions that skipped the stamp — start the clock now
            table.cleaning_started_at = now.isoformat().replace("+00:00", "Z")
        started = _iso_to_datetime(table.cleaning_started_at)
        elapsed = (now - started).total_seconds() if started else 0.0

        if elapsed < settings.camera_cleaning_grace_seconds:
            return False  # grace period — give staff a minute before judging

        if label == "clean":
            table.consecutive_empty_scans += 1
            if table.consecutive_empty_scans >= max(settings.camera_clean_scans_required, 1):
                changed = _change_status(db, table, "AVAILABLE")
        elif label in ("dirty", "occupied"):
            table.consecutive_empty_scans = 0

        if not changed and label == "dirty":
            if elapsed >= settings.camera_dirty_alert_seconds and not table.dirty_alert_sent:
                _send_alert(
                    db,
                    table,
                    event_type="DIRTY_ALERT",
                    target_role="WAITER",
                    prompt=(
                        f"Restaurant table {table.number} has been waiting for cleaning for over "
                        f"{settings.camera_dirty_alert_seconds // 60} minutes and the camera still sees it dirty. "
                        "Write one short, friendly plain-English sentence asking a waiter to clear it. "
                        "No JSON, no codes."
                    ),
                    fallback=(
                        f"Table {table.number} still looks dirty after "
                        f"{settings.camera_dirty_alert_seconds // 60} minutes — please clear it."
                    ),
                )
                table.dirty_alert_sent = True
            if elapsed >= settings.camera_dirty_escalation_seconds and not table.dirty_escalated:
                _send_alert(
                    db,
                    table,
                    event_type="DIRTY_ALERT",
                    target_role="MANAGER",
                    prompt=(
                        f"Restaurant table {table.number} has now been dirty for over "
                        f"{settings.camera_dirty_escalation_seconds // 60} minutes despite an earlier waiter alert. "
                        "Write one short, firm plain-English sentence escalating this to the manager. "
                        "No JSON, no codes."
                    ),
                    fallback=(
                        f"Escalation: table {table.number} has been dirty for over "
                        f"{settings.camera_dirty_escalation_seconds // 60} minutes and needs attention now."
                    ),
                )
                table.dirty_escalated = True

    return changed


def _apply_no_camera_tick(db: Session, table: Table, now: datetime) -> None:
    """CLEANING tables with no camera coverage: nudge staff after 15 minutes."""
    if not table.cleaning_started_at:
        table.cleaning_started_at = now.isoformat().replace("+00:00", "Z")
        return
    started = _iso_to_datetime(table.cleaning_started_at)
    if started is None:
        return
    elapsed = (now - started).total_seconds()
    if elapsed >= settings.camera_no_camera_cleaning_alert_seconds and not table.dirty_alert_sent:
        _send_alert(
            db,
            table,
            event_type="DIRTY_ALERT",
            target_role="WAITER",
            prompt=(
                f"Restaurant table {table.number} has been in CLEANING for over "
                f"{settings.camera_no_camera_cleaning_alert_seconds // 60} minutes and has no camera coverage. "
                "Write one short plain-English sentence asking a waiter to check it manually. "
                "No JSON, no codes."
            ),
            fallback=(
                f"Table {table.number} has been in CLEANING for over "
                f"{settings.camera_no_camera_cleaning_alert_seconds // 60} minutes "
                "with no camera — please check it manually."
            ),
        )
        table.dirty_alert_sent = True


def _scan_tables(db: Session) -> None:
    """One periodic decision tick over every table the camera has a job for.
    Combines table-state cleanliness detection with YOLO11 ByteTrack person tracking
    and CCTV ↔ FOH status mismatch detection.
    """
    if not settings.camera_enabled:
        return

    now = datetime.now(timezone.utc)
    tables = db.query(Table).all()
    if not tables:
        return

    from app.core.temporal_occupancy import temporal_tracker
    from app.core.vision_engine import vision_engine
    from app.models.vision import Camera, TableROI
    from app.services.mismatch_service import mismatch_service

    model_ready = is_table_state_model_ready()
    detections_by_source: dict[str, list[list[tuple[int, int, int, int, TableStateDetection]]]] = {}
    changed_tables: list[Table] = []

    # Map cameras by stream_url
    cameras = db.query(Camera).all()
    cam_by_url = {c.stream_url: c for c in cameras}

    for table in tables:
        roi = camera_utils.parse_roi(table.roi_coords)

        if not table.camera_url or roi is None:
            if table.status == "CLEANING":
                _apply_no_camera_tick(db, table, now)
            continue

        # 1. Fetch / Cache camera frames
        frame_detections = detections_by_source.get(table.camera_url)
        frames_list = []
        if frame_detections is None:
            frames_list = camera_utils.capture_frame_sequence(
                table.camera_url,
                sample_frames=settings.table_state_sample_frames,
                frame_stride=settings.table_state_sample_stride,
            )
            if model_ready and frames_list:
                frame_detections = [iter_full_frame_detections(frame) for frame in frames_list]
            else:
                frame_detections = []
            detections_by_source[table.camera_url] = frame_detections

        # 2. Legacy Table-State Cleanliness detection (if model ready)
        if model_ready and frame_detections:
            matched = [
                match_detection_for_roi(detections, roi)
                for detections in frame_detections
            ]
            detection = smooth_table_state(matched, treat_none_as_clean=False)
            label = detection.label if detection is not None else None
            if _apply_tick(db, table, label, now):
                changed_tables.append(table)

        # 3. YOLO11 + ByteTrack Person & Mismatch Detection
        if vision_engine.is_ready and frames_list:
            # Run latest frame through vision engine
            sample_frame = frames_list[-1]
            rois_payload = [{
                "table_id": table.id,
                "table_number": str(table.number),
                "bounds": roi,
            }]
            v_res = vision_engine.process_frame(sample_frame, table_rois=rois_payload)
            t_match = v_res.table_matches.get(table.id)
            people_cnt = t_match.people_count if t_match else 0
            conf = t_match.confidence if t_match else 0.0
            ids = [t.track_id for t in t_match.matched_tracks] if t_match else []

            # Update temporal state machine
            t_state = temporal_tracker.update(table.id, people_cnt, conf, ids)

            # Look up or create camera reference
            cam = cam_by_url.get(table.camera_url)
            if not cam:
                cam = Camera(
                    id=f"cam-{table.id[:8]}",
                    tenant_id=table.tenant_id,
                    branch_id=table.branch_id,
                    name=f"Camera for Table {table.number}",
                    stream_url=table.camera_url,
                    calibration_status="READY",
                )
                db.add(cam)
                db.flush()
                cam_by_url[table.camera_url] = cam

            # Evaluate status mismatch
            if settings.cv_mismatch_alert_enabled:
                mismatch_service.evaluate_mismatch(db, table, cam, t_state)

    db.commit()
    for table in changed_tables:
        db.refresh(table)
        _emit_table_updated(table)


async def run_scan_cycle(db: Session) -> None:
    """Run one periodic camera scan without blocking the event loop."""
    started = datetime.now(timezone.utc)
    await asyncio.to_thread(_scan_tables, db)
    logger.debug("Camera pipeline scan cycle finished in %.2fs", (datetime.now(timezone.utc) - started).total_seconds())
