from datetime import datetime, timedelta
from statistics import mean
from typing import Optional

from sqlalchemy import select, func 
from sqlalchemy.orm import Session

from app.models.table import Table
from app.models.reservation import Reservation
from app.models.status_history import StatusHistory


# =========================================================
# CONFIGURATION
# =========================================================

# Default expected dining duration.
#
# This is only used when we do not yet have enough
# historical information.
DEFAULT_DINING_MINUTES = 60


# Estimated time for different table states.
#
# These are fallback values.
STATE_WAIT_MINUTES = {
    "AVAILABLE": 0,
    "RESERVED": 30,
    "SEATED": 45,
    "ACTIVE": 40,
    "BILLING": 15,
    "PAID": 5,
    "CLEANING": 10,
}


# =========================================================
# HISTORICAL DATA
# =========================================================

def get_historical_dining_time(
    db: Session,
    table_id: str,
) -> Optional[float]:
    """
    Estimate the normal dining duration for a table.

    We look for complete:

        SEATED -> ... -> AVAILABLE

    cycles.

    Very short or extremely long test values are ignored.
    """

    records = db.scalars(
        select(StatusHistory)
        .where(StatusHistory.table_id == table_id)
        .order_by(StatusHistory.changed_at)
    ).all()

    if not records:
        return None

    dining_durations = []
    seating_started_at = None

    for record in records:

        if record.changed_at is None:
            continue

        if record.to_status == "SEATED":
            seating_started_at = record.changed_at

        elif (
            record.to_status == "AVAILABLE"
            and seating_started_at is not None
        ):
            duration = (
                record.changed_at - seating_started_at
            ).total_seconds()

            minutes = duration / 60

            # Ignore unrealistic test data.
            if 2 <= minutes <= 240:
                dining_durations.append(minutes)

            seating_started_at = None

    if not dining_durations:
        return None

    return round(
        mean(dining_durations),
        2,
    )


# =========================================================
# RESERVATION PRESSURE
# =========================================================

def get_reservation_pressure(
    db: Session,
    requested_time: datetime,
) -> int:
    """
    Count pending reservations around the requested time.

    Reservations within 30 minutes before or after the
    requested booking time are considered reservation pressure.
    """

    window_start = requested_time - timedelta(minutes=30)
    window_end = requested_time + timedelta(minutes=30)

    count = db.scalar(
        select(func.count(Reservation.id))
        .where(
            Reservation.reserved_for >= window_start,
            Reservation.reserved_for <= window_end,
            Reservation.status == "PENDING",
        )
    )

    return count or 0


# =========================================================
# TABLE WAIT ESTIMATION
# =========================================================

def estimate_table_wait(
    table: Table,
    requested_time: datetime,
    historical_minutes: Optional[float] = None,
) -> int:
    """
    Estimate how long until a table can become available.

    Current table state provides the immediate estimate.
    Historical dining duration can improve the estimate when
    the table is currently occupied.
    """

    status = (
        table.status or "AVAILABLE"
    ).upper()

    # Already available.
    if status == "AVAILABLE":
        return 0

    # If we have historical dining information,
    # use it to improve the estimate.
    if historical_minutes is not None:

        if status in {"SEATED", "ACTIVE"}:
            return round(historical_minutes)

        if status == "BILLING":
            return min(
                round(historical_minutes),
                STATE_WAIT_MINUTES["BILLING"],
            )

    # Fall back to known state estimates.
    return STATE_WAIT_MINUTES.get(
        status,
        30,
    )

# =========================================================
# TABLE SCORE
# =========================================================

def calculate_table_score(
    table: Table,
    party_size: int,
    requested_time: datetime,
    historical_minutes: Optional[float],
    reservation_pressure: int,
) -> float:
    """
    Calculate an AI-style recommendation score.

    Higher score = better table.

    Factors:

    1. Capacity suitability
    2. Current availability
    3. Waiting time
    4. Historical behavior
    5. Reservation pressure
    """

    score = 100.0

    status = (
        table.status
        or "AVAILABLE"
    ).upper()

    # -----------------------------------------------------
    # Capacity
    # -----------------------------------------------------

    if table.capacity < party_size:
        return -1

    # Prefer tables that fit the party without
    # wasting too much capacity.

    extra_seats = (
        table.capacity
        - party_size
    )

    score -= extra_seats * 3

    # -----------------------------------------------------
    # Current status
    # -----------------------------------------------------

    if status == "AVAILABLE":

        score += 30

    elif status == "BILLING":

        score += 5

    elif status == "CLEANING":

        score -= 5

    elif status == "SEATED":

        score -= 25

    elif status == "ACTIVE":

        score -= 30

    elif status == "RESERVED":

        score -= 35

    else:

        score -= 20

    # -----------------------------------------------------
    # Waiting time
    # -----------------------------------------------------

    wait_minutes = estimate_table_wait(
    table,
    requested_time,
    historical_minutes,
   )

    score -= wait_minutes * 0.5

    # -----------------------------------------------------
    # Historical behavior
    # -----------------------------------------------------

    if historical_minutes is not None:

        if historical_minutes <= 30:
            score += 12

        elif historical_minutes <= 45:
            score += 10

        elif historical_minutes <= 60:
            score += 6

        elif historical_minutes <= 90:
            score += 3

        elif historical_minutes <= 150:
            score += 0

        else:
            score -= 10

    # -----------------------------------------------------
    # Reservation pressure
    # -----------------------------------------------------

    if reservation_pressure > 0:

        score -= 5

    return round(
        score,
        2,
    )


# =========================================================
# MAIN AI RECOMMENDATION
# =========================================================

def recommend_table(
    db: Session,
    party_size: int,
    requested_time: datetime,
):
    """
    Main AI table recommendation function.
    """

    tables = db.scalars(
        select(Table)
    ).all()

    predictions = []

    reservation_pressure = (
        get_reservation_pressure(
            db,
            requested_time,
        )
    )

    for table in tables:

        # Ignore tables that cannot fit the party.
        if table.capacity < party_size:
            continue

        historical_minutes = (
            get_historical_dining_time(
                db,
                table.id,
            )
        )

        wait_minutes = (
            estimate_table_wait(
                table,
                requested_time,
            )
        )

        score = calculate_table_score(
            table,
            party_size,
            requested_time,
            historical_minutes,
            reservation_pressure,
        )

        if score < 0:
            continue

        predictions.append(
            {
                "table_id": table.id,
                "table_number": table.number,
                "capacity": table.capacity,
                "current_status": table.status,
                "estimated_wait_minutes": wait_minutes,
                "historical_dining_minutes": (
                    historical_minutes
                ),
                "reservation_pressure": (
                    reservation_pressure
                ),
                "score": score,
            }
        )

    # Best table first.
    predictions.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    recommended = (
        predictions[0]
        if predictions
        else None
    )

    return {
        "guests": party_size,
        "requested_time": (
            requested_time.isoformat()
        ),
        "recommended_table": recommended,
        "all_predictions": predictions,
    }
