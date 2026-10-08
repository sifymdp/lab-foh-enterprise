from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.table import Table
from app.models.reservation import Reservation
from app.services.ai_waitlist_service import (
    calculate_historical_wait,
    normalize_status,
)


FALLBACK_WAIT_MINUTES = {
    "AVAILABLE": 0,
    "CLEANING": 10,
    "BILLING": 15,
    "SEATED": 45,
    "RESERVED": 30,
}


def get_future_reservation_pressure(
    db: Session,
    slot_time: datetime,
    guests: int,
):
    """
    Calculate how much reservation pressure exists
    around a requested future time.

    Reservations within +/- 30 minutes of the slot
    are considered.
    """

    window_start = slot_time - timedelta(minutes=30)
    window_end = slot_time + timedelta(minutes=30)

    reservations = db.scalars(
        select(Reservation)
        .where(
            Reservation.status == "PENDING",
            Reservation.reserved_for >= window_start,
            Reservation.reserved_for <= window_end,
        )
    ).all()

    total_reserved_guests = sum(
        reservation.party_size
        for reservation in reservations
    )

    reservation_count = len(reservations)

    # Convert reservation pressure into a simple
    # availability penalty.
    pressure_penalty = min(
        total_reserved_guests * 3,
        40,
    )

    # A larger party needs more suitable capacity.
    if total_reserved_guests >= guests:
        pressure_penalty += 10

    return {
        "reservation_count": reservation_count,
        "reserved_guests": total_reserved_guests,
        "pressure_penalty": min(
            pressure_penalty,
            50,
        ),
    }


def get_time_of_day_factor(slot_time: datetime):
    """
    Estimate restaurant demand based on time of day.

    This is a starting model. Later we can replace it
    with a trained ML model using actual historical data.
    """

    hour = slot_time.hour
    minute = slot_time.minute

    decimal_hour = hour + (minute / 60)

    # Typical restaurant lunch peak.
    if 12.0 <= decimal_hour < 14.0:
        return {
            "demand": "HIGH",
            "penalty": 20,
        }

    # Typical restaurant dinner peak.
    if 19.0 <= decimal_hour < 21.0:
        return {
            "demand": "HIGH",
            "penalty": 25,
        }

    # Shoulder periods.
    if 11.0 <= decimal_hour < 12.0:
        return {
            "demand": "MEDIUM",
            "penalty": 8,
        }

    if 14.0 <= decimal_hour < 17.0:
        return {
            "demand": "LOW",
            "penalty": 0,
        }

    if 17.0 <= decimal_hour < 19.0:
        return {
            "demand": "MEDIUM",
            "penalty": 10,
        }

    if 21.0 <= decimal_hour < 22.0:
        return {
            "demand": "MEDIUM",
            "penalty": 8,
        }

    return {
        "demand": "LOW",
        "penalty": 0,
    }


def estimate_future_table_wait(
    db: Session,
    table: Table,
    slot_time: datetime,
):
    """
    Estimate whether a table is likely to be usable
    at a future time.
    """

    status = normalize_status(table.status)

    # Current AVAILABLE table.
    if status == "AVAILABLE":
        base_wait = 0

    else:
        historical_wait = calculate_historical_wait(
            db=db,
            table_id=table.id,
            current_status=status,
        )

        if historical_wait is not None:
            base_wait = historical_wait
        else:
            base_wait = FALLBACK_WAIT_MINUTES.get(
                status,
                30,
            )

    now = datetime.now(timezone.utc)

    # How far into the future is the requested slot?
    minutes_until_slot = (
        slot_time - now
    ).total_seconds() / 60

    # If the requested slot is far enough into the future
    # for the table's expected wait to finish, treat it
    # as potentially available.
    if minutes_until_slot >= base_wait:
        predicted_wait = 0
        predicted_available = True

    else:
        predicted_wait = max(
            0,
            base_wait - minutes_until_slot,
        )
        predicted_available = False

    return {
        "predicted_available": predicted_available,
        "estimated_wait_minutes": round(
            predicted_wait,
            1,
        ),
        "base_turnover_minutes": round(
            base_wait,
            1,
        ),
    }


def score_time_slot(
    db: Session,
    guests: int,
    slot_time: datetime,
):
    """
    Score one future booking time.

    Higher score = better booking opportunity.
    """

    tables = db.scalars(
        select(Table)
    ).all()

    suitable_tables = [
        table
        for table in tables
        if table.capacity >= guests
    ]

    if not suitable_tables:
        return {
            "score": 0,
            "available_tables": 0,
            "estimated_wait_minutes": None,
            "reason": (
                f"No table can accommodate "
                f"{guests} guests."
            ),
        }

    predicted_tables = []

    for table in suitable_tables:

        prediction = estimate_future_table_wait(
            db=db,
            table=table,
            slot_time=slot_time,
        )

        predicted_tables.append(
            {
                "table_number": table.number,
                "capacity": table.capacity,
                **prediction,
            }
        )

    # Count tables predicted to be available.
    available_tables = sum(
        1
        for table in predicted_tables
        if table["predicted_available"]
    )

    # Find the table with the shortest predicted wait.
    best_table = min(
        predicted_tables,
        key=lambda item: item[
            "estimated_wait_minutes"
        ],
    )

    best_wait = best_table[
        "estimated_wait_minutes"
    ]

    # -------------------------------------------------
    # Future reservation pressure.
    # -------------------------------------------------

    reservation_pressure = (
        get_future_reservation_pressure(
            db=db,
            slot_time=slot_time,
            guests=guests,
        )
    )

    # -------------------------------------------------
    # Time-of-day demand.
    # -------------------------------------------------

    demand = get_time_of_day_factor(
        slot_time
    )

    # -------------------------------------------------
    # Calculate score.
    # -------------------------------------------------

    score = 100

    # Reward predicted available tables.
    score += min(
        available_tables * 8,
        24,
    )

    # Penalize predicted waiting.
    score -= min(
        best_wait * 1.5,
        45,
    )

    # Penalize reservation pressure.
    score -= reservation_pressure[
        "pressure_penalty"
    ]

    # Penalize expected busy periods.
    score -= demand["penalty"]

    score = max(
        0,
        min(
            100,
            round(score),
        ),
    )

    return {
        "score": score,
        "available_tables": available_tables,
        "estimated_wait_minutes": round(
            best_wait,
            1,
        ),
        "reservation_pressure": (
            reservation_pressure[
                "reserved_guests"
            ]
        ),
        "reservation_count": (
            reservation_pressure[
                "reservation_count"
            ]
        ),
        "predicted_demand": demand["demand"],
        "recommended_table": (
            best_table["table_number"]
        ),
        "reason": (
            "Time slot evaluated using predicted "
            "table turnover, historical table behavior, "
            "reservation pressure, and expected demand."
        ),
    }


def recommend_time_slots(
    db: Session,
    guests: int,
    requested_time: datetime,
):
    """
    Evaluate nearby future time slots and recommend
    the best one.
    """

    if requested_time.tzinfo is None:
        requested_time = requested_time.replace(
            tzinfo=timezone.utc
        )

    slots = []

    # Evaluate 8 slots across two hours.
    for offset in range(
        0,
        120,
        15,
    ):

        slot_time = (
            requested_time
            + timedelta(minutes=offset)
        )

        result = score_time_slot(
            db=db,
            guests=guests,
            slot_time=slot_time,
        )

        slots.append(
            {
                "time": slot_time.isoformat(),
                **result,
            }
        )

    # Highest score first.
    ranked_slots = sorted(
        slots,
        key=lambda item: (
            -item["score"],
            item["estimated_wait_minutes"]
            if item["estimated_wait_minutes"]
            is not None
            else 9999,
        ),
    )

    best = ranked_slots[0]

    return {
        "guests": guests,
        "requested_time": (
            requested_time.isoformat()
        ),
        "recommended_time": best["time"],
        "recommended_score": best["score"],
        "recommended_wait_minutes": (
            best["estimated_wait_minutes"]
        ),
        "recommended_table": (
            best.get("recommended_table")
        ),
        "predicted_demand": (
            best.get("predicted_demand")
        ),
        "recommended_reason": (
            "The AI selected the time slot with "
            "the best predicted combination of "
            "table availability, historical turnover, "
            "reservation pressure, and expected demand."
        ),
        "time_slots": ranked_slots,
    }
