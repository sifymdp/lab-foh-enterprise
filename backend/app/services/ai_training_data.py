from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.status_history import StatusHistory


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

# Very short reservation changes are usually caused by
# API testing rather than real restaurant activity.
MIN_RESERVATION_SECONDS = 5

# We don't want unrealistic durations to enter the
# machine-learning dataset.
#
# 6 hours is already much longer than a normal table
# transition in this project.
MAX_STATE_DURATION_SECONDS = 6 * 60 * 60


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------

def seconds_between(
    start: datetime,
    end: datetime,
) -> float:
    """
    Return the number of seconds between two timestamps.
    """

    return (end - start).total_seconds()


def is_test_reservation_change(
    from_status: Optional[str],
    to_status: str,
    duration_seconds: float,
) -> bool:
    """
    Detect rapid reservation changes that are most likely
    caused by testing the reservation API.
    """

    reservation_transition = (
        (
            from_status == "AVAILABLE"
            and to_status == "RESERVED"
        )
        or
        (
            from_status == "RESERVED"
            and to_status == "AVAILABLE"
        )
    )

    if (
        reservation_transition
        and duration_seconds < MIN_RESERVATION_SECONDS
    ):
        return True

    return False


def is_valid_duration(
    duration_seconds: float,
) -> bool:
    """
    Check whether a duration is realistic enough to use
    for machine-learning training.
    """

    if duration_seconds <= 0:
        return False

    if duration_seconds > MAX_STATE_DURATION_SECONDS:
        return False

    return True


# ---------------------------------------------------------
# Build clean state-duration dataset
# ---------------------------------------------------------

def build_clean_training_data(
    db: Session,
):
    """
    Convert raw status-history records into a clean dataset.

    IMPORTANT:

    The records are processed separately for each table.

    For each record:

        current status
              Γåô
        next status
              Γåô
        time between them

    Example:

        SEATED at 12:00
              Γåô
        BILLING at 12:30

        SEATED duration = 30 minutes
    """

    rows = db.scalars(
        select(StatusHistory)
        .order_by(
            StatusHistory.table_id,
            StatusHistory.changed_at,
        )
    ).all()

    # -----------------------------------------------------
    # Group records by table.
    # -----------------------------------------------------

    table_records = {}

    for row in rows:

        table_records.setdefault(
            row.table_id,
            [],
        ).append(row)

    training_rows = []

    # -----------------------------------------------------
    # Process each table independently.
    # -----------------------------------------------------

    for table_id, records in table_records.items():

        for index in range(
            len(records) - 1
        ):

            current = records[index]

            next_record = records[index + 1]

            # Safety check.
            if (
                current.table_id
                != next_record.table_id
            ):
                continue

            # The table's current state lasted until
            # the next state change.
            duration_seconds = seconds_between(
                current.changed_at,
                next_record.changed_at,
            )

            # Ignore invalid durations.
            if not is_valid_duration(
                duration_seconds
            ):
                continue

            # Ignore rapid reservation testing.
            if is_test_reservation_change(
                current.from_status,
                current.to_status,
                duration_seconds,
            ):
                continue

            training_rows.append(
                {
                    "table_id": table_id,

                    # The state the table entered.
                    "state": current.to_status,

                    # The state that came after it.
                    "next_status": next_record.to_status,

                    # How long the table stayed in that state.
                    "duration_seconds": round(
                        duration_seconds,
                        2,
                    ),

                    # Timestamp when the state started.
                    "started_at": (
                        current.changed_at.isoformat()
                    ),

                    # Useful AI features.
                    "hour": current.changed_at.hour,

                    "day_of_week": (
                        current.changed_at.weekday()
                    ),
                }
            )

    return training_rows


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------

def summarize_training_data(
    training_rows,
):
    """
    Summarize the cleaned dataset.

    This helps us understand whether we have enough
    useful data before training the ML model.
    """

    summary = {
        "total_clean_records": len(
            training_rows
        ),
        "states": {},
    }

    for row in training_rows:

        state = row["state"]

        summary["states"].setdefault(
            state,
            {
                "count": 0,
                "durations": [],
            },
        )

        summary["states"][
            state
        ]["count"] += 1

        summary["states"][
            state
        ]["durations"].append(
            row["duration_seconds"]
        )

    # -----------------------------------------------------
    # Calculate statistics.
    # -----------------------------------------------------

    for state, data in summary[
        "states"
    ].items():

        durations = data["durations"]

        if durations:

            data["average_seconds"] = round(
                sum(durations)
                / len(durations),
                2,
            )

            data["minimum_seconds"] = round(
                min(durations),
                2,
            )

            data["maximum_seconds"] = round(
                max(durations),
                2,
            )

        # Remove the raw list from the response.
        del data["durations"]

    return summary
