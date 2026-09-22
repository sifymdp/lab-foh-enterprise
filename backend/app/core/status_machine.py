"""
Table Status Machine — Centralized lifecycle, valid transition graph, and protection rules.

Table Statuses:
  AVAILABLE    - Ready for guests
  RESERVED     - Held for upcoming reservation
  SEATED       - Guests seated, awaiting order placement
  ACTIVE       - Dining session active with placed order(s)
  BILLING      - Bill presented, awaiting payment / settlement
  CLEANING     - Guests departed, table undergoing sanitization / busing
  MAINTENANCE  - Table out of service
"""
from datetime import datetime, timezone
import logging
from typing import Literal

from sqlalchemy.orm import Session
from app.models.table import Table
from app.models.status_history import StatusHistory
from app.core.ids import new_id

logger = logging.getLogger(__name__)

TableStatusType = Literal[
    "AVAILABLE",
    "RESERVED",
    "SEATED",
    "ACTIVE",
    "BILLING",
    "CLEANING",
    "MAINTENANCE",
]

# Valid state transitions graph: from_status -> set of allowed to_statuses
VALID_TRANSITIONS: dict[str, set[str]] = {
    "AVAILABLE": {"RESERVED", "SEATED", "MAINTENANCE"},
    "RESERVED": {"SEATED", "AVAILABLE", "MAINTENANCE"},
    "SEATED": {"ACTIVE", "AVAILABLE", "CLEANING"},
    "ACTIVE": {"BILLING", "SEATED", "CLEANING", "AVAILABLE"},
    "BILLING": {"CLEANING", "ACTIVE", "AVAILABLE"},
    "CLEANING": {"AVAILABLE", "SEATED", "MAINTENANCE"},
    "MAINTENANCE": {"AVAILABLE", "CLEANING"},
}

ACTIVE_SESSION_STATUSES = {"SEATED", "ACTIVE", "BILLING"}


class InvalidTransitionError(Exception):
    """Raised when an illegal status transition is requested."""
    def __init__(self, from_status: str, to_status: str, reason: str | None = None):
        self.from_status = from_status
        self.to_status = to_status
        self.reason = reason or f"Illegal transition from '{from_status}' to '{to_status}'"
        super().__init__(self.reason)


class ProtectedStateError(Exception):
    """Raised when an automated system (e.g. CCTV) attempts to modify a protected state."""
    pass


def is_valid_transition(from_status: str, to_status: str, is_admin_override: bool = False) -> bool:
    """Check if the transition is permitted by the state graph."""
    if is_admin_override:
        return True
    from_s = from_status.upper()
    to_s = to_status.upper()
    if from_s == to_s:
        return True
    return to_s in VALID_TRANSITIONS.get(from_s, set())


def can_cctv_transition(from_status: str, to_status: str) -> tuple[bool, str]:
    """
    Validate whether automated CCTV / Computer Vision pipeline is permitted
    to execute this transition.

    Core Protection Rules:
    1. BILLING state is strictly protected: CCTV can NEVER auto-transition a table out of BILLING.
    2. CCTV can detect arrivals: AVAILABLE -> SEATED.
    3. CCTV can detect clean tables: CLEANING -> AVAILABLE.
    4. CCTV can NEVER change ACTIVE -> AVAILABLE directly (must create mismatch alert instead).
    """
    from_s = from_status.upper()
    to_s = to_status.upper()

    if from_s == "BILLING":
        return False, "CCTV cannot automatically change table status while in BILLING state. Staff action required."

    if from_s == "ACTIVE" and to_s in ("AVAILABLE", "CLEANING"):
        return False, "CCTV cannot auto-clear an ACTIVE dining session. Discrepancy alert logged instead."

    if from_s == "AVAILABLE" and to_s == "SEATED":
        return True, "CCTV guest arrival confirmed."

    if from_s == "CLEANING" and to_s == "AVAILABLE":
        return True, "CCTV cleanliness confirmed."

    return False, f"Automated CCTV transition from {from_s} to {to_s} is disallowed."


def transition_table(
    db: Session,
    table: Table,
    target_status: str,
    source: str = "MANUAL",
    user_id: str | None = None,
    reason: str | None = None,
    admin_override: bool = False,
) -> Table:
    """
    Execute a verified table status transition.
    Records transition in StatusHistory table for full auditability.
    """
    current_status = (table.status or "AVAILABLE").upper()
    target_status = target_status.upper()

    if current_status == target_status:
        return table

    # 1. Protection rule check for CCTV
    if source.upper() in ("CCTV", "VISION", "AUTOMATED"):
        allowed, msg = can_cctv_transition(current_status, target_status)
        if not allowed:
            logger.warning(f"Rejected CCTV transition for Table {table.number}: {msg}")
            raise ProtectedStateError(msg)

    # 2. General transition rule check
    if not is_valid_transition(current_status, target_status, is_admin_override=admin_override):
        msg = f"Invalid status transition for Table {table.number} from '{current_status}' to '{target_status}'"
        logger.error(msg)
        raise InvalidTransitionError(current_status, target_status, msg)

    # 3. Apply status change and reset edge flags
    now = datetime.now(timezone.utc)
    table.status = target_status
    table.consecutive_person_scans = 0
    table.consecutive_empty_scans = 0
    table.dirty_alert_sent = False
    table.dirty_escalated = False
    table.departure_alert_sent = False

    if target_status == "CLEANING":
        table.cleaning_started_at = now.isoformat()
    elif target_status != "CLEANING":
        table.cleaning_started_at = None

    # 4. Record status history in DB
    history = StatusHistory(
        id=new_id(),
        table_id=table.id,
        from_status=current_status,
        to_status=target_status,
        changed_by=user_id,
        changed_at=now,
    )
    db.add(history)
    db.flush()

    logger.info(f"Table {table.number} transitioned {current_status} -> {target_status} via {source}")
    return table
