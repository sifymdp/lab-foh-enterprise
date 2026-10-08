"""
CCTV ↔ FOH Status Mismatch Detection & Resolution Service
──────────────────────────────────────────────────────────
Detects operational discrepancies between physical CCTV observations
and digital FOH system states, records actionable alerts, and handles
human verification workflows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.ids import generate_id
from app.core.temporal_occupancy import TableTemporalState
from app.models import Table, User
from app.models.vision import Camera, VisionMismatch, VisionObservation
from app.services import table_service
from app.socket_manager import emit_sync

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MismatchService:

    @staticmethod
    def evaluate_mismatch(
        db: Session,
        table: Table,
        camera: Camera,
        temporal_state: TableTemporalState,
    ) -> VisionMismatch | None:
        """
        Compares table digital status against temporal vision observation.
        Returns newly created or active VisionMismatch if discrepancy found.
        """
        digital_status = table.status
        obs_state = temporal_state.state
        people_count = temporal_state.people_count
        conf = temporal_state.confidence

        mismatch_type: str | None = None

        # Case 1: Unrecorded Occupancy
        # Digital says AVAILABLE or RESERVED, but people are sitting at the table
        if digital_status in ("AVAILABLE", "RESERVED") and obs_state in ("OCCUPIED_CONFIRMED", "POSSIBLE_OCCUPIED") and people_count > 0:
            if conf >= 0.55:
                mismatch_type = "UNRECORDED_OCCUPANCY"

        # Case 2: Stale Active Occupancy / Ghost Table
        # Digital says ACTIVE/SEATED, but table is confirmed empty
        elif digital_status in ("ACTIVE", "SEATED") and obs_state == "EMPTY_CONFIRMED":
            mismatch_type = "STALE_OCCUPANCY"

        # Case 3: Unpaid Walkout Suspect
        # Digital says BILLING, but table is empty
        elif digital_status == "BILLING" and obs_state == "EMPTY_CONFIRMED":
            mismatch_type = "UNPAID_WALKOUT_SUSPECT"

        # Case 4: Seated at Dirty Table
        # Digital says CLEANING, but guests have seated themselves
        elif digital_status == "CLEANING" and people_count > 0 and obs_state in ("OCCUPIED_CONFIRMED", "POSSIBLE_OCCUPIED"):
            mismatch_type = "SEATED_AT_DIRTY_TABLE"

        if not mismatch_type:
            # If there was a pending mismatch that is no longer occurring, auto-resolve it
            existing_pending = db.execute(
                select(VisionMismatch).where(
                    VisionMismatch.table_id == table.id,
                    VisionMismatch.status == "PENDING",
                )
            ).scalars().all()
            for mm in existing_pending:
                mm.status = "AUTO_RESOLVED"
                mm.resolved_at = _utc_now()
            if existing_pending:
                db.commit()
            return None

        # Check if an identical active mismatch is already pending
        existing = db.execute(
            select(VisionMismatch).where(
                VisionMismatch.table_id == table.id,
                VisionMismatch.mismatch_type == mismatch_type,
                VisionMismatch.status == "PENDING",
            )
        ).scalar_one_or_none()

        if existing:
            # Update existing with latest telemetry
            existing.detected_people = people_count
            existing.confidence = conf
            existing.observed_state = obs_state
            existing.digital_status = digital_status
            db.commit()
            return existing

        # Create new mismatch record
        mismatch_id = generate_id("vmm")
        mismatch = VisionMismatch(
            id=mismatch_id,
            tenant_id=table.tenant_id,
            branch_id=table.branch_id,
            camera_id=camera.id,
            table_id=table.id,
            table_number=str(table.number),
            digital_status=digital_status,
            observed_state=obs_state,
            detected_people=people_count,
            confidence=conf,
            mismatch_type=mismatch_type,
            status="PENDING",
            created_at=_utc_now(),
        )
        db.add(mismatch)
        db.commit()
        db.refresh(mismatch)

        logger.warning(
            "CCTV Status Mismatch detected for Table %s: %s (Digital: %s, CCTV: %s, People: %d)",
            table.number, mismatch_type, digital_status, obs_state, people_count
        )

        # Broadcast mismatch over WebSocket
        try:
            emit_sync(
                "cctv_mismatch_detected",
                {
                    "mismatch_id": mismatch.id,
                    "table_id": table.id,
                    "table_number": str(table.number),
                    "digital_status": digital_status,
                    "observed_state": obs_state,
                    "detected_people": people_count,
                    "confidence": conf,
                    "mismatch_type": mismatch_type,
                    "created_at": mismatch.created_at.isoformat(),
                },
                room=table.floor_id or "default",
            )
        except Exception:
            logger.debug("Failed to broadcast cctv_mismatch_detected socket event")

        return mismatch

    @staticmethod
    def record_observation(
        db: Session,
        table: Table,
        camera: Camera,
        temporal_state: TableTemporalState,
        is_mismatch: bool = False,
        mismatch_type: str | None = None,
    ) -> VisionObservation:
        obs = VisionObservation(
            id=generate_id("vobs"),
            tenant_id=table.tenant_id,
            branch_id=table.branch_id,
            camera_id=camera.id,
            table_id=table.id,
            detected_people_count=temporal_state.people_count,
            tracked_person_ids=str(temporal_state.tracked_ids),
            confidence=temporal_state.confidence,
            occupancy_state=temporal_state.state,
            digital_status=table.status,
            is_mismatch=is_mismatch,
            mismatch_type=mismatch_type,
            timestamp=_utc_now(),
        )
        db.add(obs)
        db.commit()
        return obs

    @staticmethod
    def resolve_mismatch(
        db: Session,
        mismatch_id: str,
        action: str,
        user_id: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """
        Applies human verification to a mismatch:
          - 'CONFIRM_OCCUPIED': sets table digital status to 'SEATED'
          - 'CONFIRM_CLEAN' / 'CONFIRM_AVAILABLE': sets table status to 'AVAILABLE'
          - 'CONFIRM_DEPARTURE': sets table status to 'CLEANING'
          - 'DISMISS': ignores observation without modifying digital state
        """
        mismatch = db.execute(
            select(VisionMismatch).where(VisionMismatch.id == mismatch_id)
        ).scalar_one_or_none()

        if not mismatch:
            raise ValueError(f"Mismatch {mismatch_id} not found")

        table = db.execute(
            select(Table).where(Table.id == mismatch.table_id)
        ).scalar_one_or_none()

        now = _utc_now()
        mismatch.status = "VERIFIED_CONFIRMED" if action != "DISMISS" else "DISMISSED"
        mismatch.verified_by_user_id = user_id
        mismatch.verification_notes = notes or f"Action: {action}"
        mismatch.resolved_at = now

        if table and action != "DISMISS":
            old_status = table.status
            if action == "CONFIRM_OCCUPIED":
                if table.status in ("AVAILABLE", "RESERVED", "CLEANING"):
                    table.status = "SEATED"
                    table_service._on_status_change(table, old_status, "SEATED")
                    table_service.record_history(db, table.id, old_status, "SEATED", user_id=user_id)
            elif action in ("CONFIRM_AVAILABLE", "CONFIRM_CLEAN"):
                table.status = "AVAILABLE"
                table_service._on_status_change(table, old_status, "AVAILABLE")
                table_service.record_history(db, table.id, old_status, "AVAILABLE", user_id=user_id)
            elif action == "CONFIRM_DEPARTURE":
                table.status = "CLEANING"
                table.cleaning_started_at = now.isoformat()
                table_service._on_status_change(table, old_status, "CLEANING")
                table_service.record_history(db, table.id, old_status, "CLEANING", user_id=user_id)

            table_service._emit_table_updated(table)

        db.commit()

        # Emit socket update
        try:
            floor_id = table.floor_id if table else "default"
            emit_sync(
                "cctv_mismatch_resolved",
                {
                    "mismatch_id": mismatch.id,
                    "table_id": mismatch.table_id,
                    "status": mismatch.status,
                    "action": action,
                },
                room=floor_id,
            )
        except Exception:
            pass

        return {
            "success": True,
            "mismatch_id": mismatch.id,
            "status": mismatch.status,
            "action": action,
            "table_status": table.status if table else None,
        }


mismatch_service = MismatchService()
