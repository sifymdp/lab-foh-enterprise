from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func 
from sqlalchemy.orm import Session

from app.models.table import Table
from app.models.reservation import Reservation


# =========================================================
# WAITING LIST CONFIGURATION
# =========================================================

# Default waiting time when we don't have enough
# information about a table.
DEFAULT_UNKNOWN_WAIT = 30


# Additional waiting time based on current table state.
STATE_WAIT_MINUTES = {
    "AVAILABLE": 0,
    "BILLING": 15,
    "PAID": 5,
    "CLEANING": 10,
    "SEATED": 45,
    "ACTIVE": 40,
    "RESERVED": 30,
}


# =========================================================
# TABLE WAIT ESTIMATION
# =========================================================

def estimate_wait_for_table(
    table: Table,
) -> int:
    """
    Estimate how many minutes are required before
    this table can probably become available.
    """

    status = (
        table.status
        or "AVAILABLE"
    ).upper()

    return STATE_WAIT_MINUTES.get(
        status,
        DEFAULT_UNKNOWN_WAIT,
    )


# =========================================================
# AVAILABLE TABLE COUNT
# =========================================================

def count_available_tables(
    db: Session,
    guests: int,
) -> int:
    """
    Count tables that can accommodate the requested
    number of guests and are currently available.
    """

    tables = db.scalars(
        select(Table)
    ).all()

    count = 0

    for table in tables:

        if table.capacity < guests:
            continue

        status = (
            table.status
            or "AVAILABLE"
        ).upper()

        if status == "AVAILABLE":

            count += 1

    return count


# =========================================================
# BUSY TABLE COUNT
# =========================================================

def count_busy_tables(
    db: Session,
    guests: int,
) -> int:
    """
    Count suitable tables that are currently occupied
    or otherwise unavailable.
    """

    tables = db.scalars(
        select(Table)
    ).all()

    count = 0

    for table in tables:

        if table.capacity < guests:
            continue

        status = (
            table.status
            or "AVAILABLE"
        ).upper()

        if status != "AVAILABLE":

            count += 1

    return count


# =========================================================
# RESERVATION COUNT
# =========================================================

def count_upcoming_reservations(
    db: Session,
    requested_time: datetime,
) -> int:
    """
    Count pending reservations within one hour of
    the requested booking time.
    """

    window_start = requested_time - timedelta(minutes=60)
    window_end = requested_time + timedelta(minutes=60)

    count = db.scalar(
        select(func.count(Reservation.id))
        .where(
            Reservation.status == "PENDING",
            Reservation.reserved_for >= window_start,
            Reservation.reserved_for <= window_end,
        )
    )

    return count or 0


# =========================================================
# PREDICTED WAIT
# =========================================================

def predict_waiting_time(
    db: Session,
    guests: int,
    requested_time: datetime,
) -> dict:
    """
    Main AI-style waiting-list prediction.

    The prediction combines:

    - current table availability
    - table capacity
    - current table status
    - reservation pressure
    - estimated table turnover
    """

    tables = db.scalars(
        select(Table)
    ).all()

    suitable_tables = []

    for table in tables:

        if table.capacity < guests:
            continue

        wait = estimate_wait_for_table(
            table
        )

        suitable_tables.append(
            {
                "table_number": table.number,
                "capacity": table.capacity,
                "status": table.status,
                "estimated_wait_minutes": wait,
            }
        )

    if not suitable_tables:

        return {
            "guests": guests,
            "predicted_wait_minutes": None,
            "demand": "VERY_HIGH",
            "confidence": 40,
            "reason": (
                "No suitable tables are currently "
                "available for this party size."
            ),
            "available_tables": 0,
            "busy_tables": 0,
            "reservation_count": 0,
        }

    # -----------------------------------------------------
    # Current availability
    # -----------------------------------------------------

    available_tables = [
        table
        for table in suitable_tables
        if (
            table["status"] or ""
        ).upper() == "AVAILABLE"
    ]

    busy_tables = [
        table
        for table in suitable_tables
        if (
            table["status"] or ""
        ).upper() != "AVAILABLE"
    ]

    # -----------------------------------------------------
    # Reservation pressure
    # -----------------------------------------------------

    reservation_count = (
        count_upcoming_reservations(
            db,
            requested_time,
        )
    )

    # -----------------------------------------------------
    # Immediate availability
    # -----------------------------------------------------

    if available_tables:

        return {
            "guests": guests,
            "predicted_wait_minutes": 0,
            "demand": (
                "HIGH"
                if reservation_count >= 3
                else "NORMAL"
            ),
            "confidence": 95,
            "reason": (
                "A suitable table is currently "
                "available."
            ),
            "available_tables": len(
                available_tables
            ),
            "busy_tables": len(
                busy_tables
            ),
            "reservation_count": (
                reservation_count
            ),
            "table_predictions": (
                suitable_tables
            ),
        }

    # -----------------------------------------------------
    # No table immediately available.
    #
    # Find the table expected to become available
    # first.
    # -----------------------------------------------------

    wait_times = [
        table["estimated_wait_minutes"]
        for table in busy_tables
    ]

    predicted_wait = min(
        wait_times
    ) if wait_times else DEFAULT_UNKNOWN_WAIT

    # -----------------------------------------------------
    # Demand calculation
    # -----------------------------------------------------

    busy_ratio = (
        len(busy_tables)
        / len(suitable_tables)
    )

    if busy_ratio >= 0.8:

        demand = "VERY_HIGH"

    elif busy_ratio >= 0.5:

        demand = "HIGH"

    elif busy_ratio >= 0.3:

        demand = "MEDIUM"

    else:

        demand = "LOW"

    # Reservation pressure can increase demand.
    if reservation_count >= 3:

        if demand == "MEDIUM":
            demand = "HIGH"

        elif demand == "HIGH":
            demand = "VERY_HIGH"

    # -----------------------------------------------------
    # Confidence
    # -----------------------------------------------------

    confidence = 75

    if reservation_count > 0:
        confidence += 5

    if len(busy_tables) > 0:
        confidence += 5

    confidence = min(
        confidence,
        95,
    )

    # -----------------------------------------------------
    # Explanation
    # -----------------------------------------------------

    if reservation_count > 0:

        reason = (
            f"No suitable table is currently "
            f"available. The earliest estimated "
            f"table availability is about "
            f"{predicted_wait} minutes. "
            f"There are {reservation_count} "
            f"nearby reservations, increasing "
            f"reservation pressure."
        )

    else:

        reason = (
            f"No suitable table is currently "
            f"available. The earliest estimated "
            f"table availability is about "
            f"{predicted_wait} minutes based "
            f"on current table states."
        )

    return {
        "guests": guests,
        "predicted_wait_minutes": (
            predicted_wait
        ),
        "demand": demand,
        "confidence": confidence,
        "reason": reason,
        "available_tables": len(
            available_tables
        ),
        "busy_tables": len(
            busy_tables
        ),
        "reservation_count": (
            reservation_count
        ),
        "table_predictions": (
            suitable_tables
        ),
    }
