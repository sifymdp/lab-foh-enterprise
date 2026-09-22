from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import DiningSession, StatusHistory, Table


# ---------------------------------------------------------
# TIME HELPERS
# ---------------------------------------------------------

def _make_aware(value: datetime) -> datetime:
    """
    SQLite may return datetimes without timezone information.
    This function treats those values as UTC.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def _minutes_between(start: datetime, end: datetime) -> float:
    """
    Return the number of minutes between two timestamps.
    """

    start = _make_aware(start)
    end = _make_aware(end)

    return max(
        (end - start).total_seconds() / 60,
        0,
    )


# ---------------------------------------------------------
# DINING SESSION HISTORY
# ---------------------------------------------------------

def get_average_turnover_minutes(
    db: Session,
    table_id: str | None = None,
    party_size: int | None = None,
) -> float:
    """
    Calculate the historical average dining-session duration.

    Priority:

    1. Same table + same party size
    2. Same table
    3. Same party size across all tables
    4. All completed sessions
    5. Default value
    """

    def calculate_average(sessions: list[DiningSession]) -> float | None:

        durations = []

        for session in sessions:

            if not session.seated_at or not session.closed_at:
                continue

            minutes = _minutes_between(
                session.seated_at,
                session.closed_at,
            )

            if minutes > 0:
                durations.append(minutes)

        if not durations:
            return None

        return round(
            sum(durations) / len(durations),
            1,
        )

    # ---------------------------------------------
    # 1. Same table + same party size
    # ---------------------------------------------

    if table_id and party_size:

        sessions = (
            db.query(DiningSession)
            .filter(
                DiningSession.table_id == table_id,
                DiningSession.party_size == party_size,
                DiningSession.closed_at.isnot(None),
            )
            .all()
        )

        average = calculate_average(sessions)

        if average is not None:
            return average

    # ---------------------------------------------
    # 2. Same table
    # ---------------------------------------------

    if table_id:

        sessions = (
            db.query(DiningSession)
            .filter(
                DiningSession.table_id == table_id,
                DiningSession.closed_at.isnot(None),
            )
            .all()
        )

        average = calculate_average(sessions)

        if average is not None:
            return average

    # ---------------------------------------------
    # 3. Same party size
    # ---------------------------------------------

    if party_size:

        sessions = (
            db.query(DiningSession)
            .filter(
                DiningSession.party_size == party_size,
                DiningSession.closed_at.isnot(None),
            )
            .all()
        )

        average = calculate_average(sessions)

        if average is not None:
            return average

    # ---------------------------------------------
    # 4. All completed sessions
    # ---------------------------------------------

    sessions = (
        db.query(DiningSession)
        .filter(
            DiningSession.closed_at.isnot(None),
        )
        .all()
    )

    average = calculate_average(sessions)

    if average is not None:
        return average

    # ---------------------------------------------
    # 5. No historical data yet
    # ---------------------------------------------

    return 60.0


# ---------------------------------------------------------
# STATUS HISTORY
# ---------------------------------------------------------

def get_average_status_duration_minutes(
    db: Session,
    table_id: str,
    status_name: str,
    default_minutes: float,
) -> float:
    """
    Learn how long a particular table usually stays
    in a particular status using StatusHistory.

    Example:

    CLEANING entered at 7:00
    AVAILABLE entered at 7:08

    CLEANING duration = 8 minutes
    """

    history = (
        db.query(StatusHistory)
        .filter(
            StatusHistory.table_id == table_id,
        )
        .order_by(StatusHistory.changed_at.asc())
        .all()
    )

    durations = []

    for index, record in enumerate(history):

        if record.to_status != status_name:
            continue

        # Need a later status change to know
        # when this status ended.
        if index + 1 >= len(history):
            continue

        next_record = history[index + 1]

        minutes = _minutes_between(
            record.changed_at,
            next_record.changed_at,
        )

        if minutes > 0:
            durations.append(minutes)

    if durations:

        return round(
            sum(durations) / len(durations),
            1,
        )

    return default_minutes


def get_current_status_elapsed_minutes(
    db: Session,
    table_id: str,
    current_status: str,
) -> float:
    """
    Find how long the table has been in its current status.
    """

    latest = (
        db.query(StatusHistory)
        .filter(
            StatusHistory.table_id == table_id,
            StatusHistory.to_status == current_status,
        )
        .order_by(StatusHistory.changed_at.desc())
        .first()
    )

    if not latest:
        return 0.0

    return _minutes_between(
        latest.changed_at,
        datetime.now(timezone.utc),
    )


# ---------------------------------------------------------
# CURRENT SESSION
# ---------------------------------------------------------

def get_active_session(
    db: Session,
    table_id: str,
) -> DiningSession | None:

    return (
        db.query(DiningSession)
        .filter(
            DiningSession.table_id == table_id,
            DiningSession.closed_at.is_(None),
        )
        .order_by(DiningSession.seated_at.desc())
        .first()
    )


def get_session_elapsed_minutes(
    session: DiningSession,
) -> float:
    """
    Calculate how long the current guests
    have already been sitting.
    """

    return _minutes_between(
        session.seated_at,
        datetime.now(timezone.utc),
    )


# ---------------------------------------------------------
# TABLE TURNOVER PREDICTION
# ---------------------------------------------------------

def predict_remaining_minutes(
    db: Session,
    table_id: str,
) -> float:
    """
    Predict remaining dining time for the
    currently active dining session.
    """

    active_session = get_active_session(
        db,
        table_id,
    )

    if not active_session:
        return 0.0

    average_turnover = get_average_turnover_minutes(
        db=db,
        table_id=table_id,
        party_size=active_session.party_size,
    )

    elapsed = get_session_elapsed_minutes(
        active_session,
    )

    remaining = average_turnover - elapsed

    return round(
        max(remaining, 0),
        1,
    )


# ---------------------------------------------------------
# PREDICT WAIT TIME FOR ONE TABLE
# ---------------------------------------------------------

def predict_table_wait_time(
    db: Session,
    table: Table,
) -> float:
    """
    Predict how many minutes before this table
    can become AVAILABLE.
    """

    # ---------------------------------------------
    # AVAILABLE NOW
    # ---------------------------------------------

    if table.status == "AVAILABLE":
        return 0.0

    # ---------------------------------------------
    # RESERVED
    # ---------------------------------------------

    if table.status == "RESERVED":
        return 9999.0

    # ---------------------------------------------
    # SEATED / ACTIVE
    # ---------------------------------------------

    if table.status in ["SEATED", "ACTIVE"]:

        return predict_remaining_minutes(
            db,
            table.id,
        )

    # ---------------------------------------------
    # BILLING
    # ---------------------------------------------

    if table.status == "BILLING":

        average_billing = (
            get_average_status_duration_minutes(
                db=db,
                table_id=table.id,
                status_name="BILLING",
                default_minutes=10.0,
            )
        )

        elapsed = get_current_status_elapsed_minutes(
            db,
            table.id,
            "BILLING",
        )

        remaining = max(
            average_billing - elapsed,
            0,
        )

        # Add estimated cleaning time afterwards
        cleaning_average = (
            get_average_status_duration_minutes(
                db=db,
                table_id=table.id,
                status_name="CLEANING",
                default_minutes=10.0,
            )
        )

        return round(
            remaining + cleaning_average,
            1,
        )

    # ---------------------------------------------
    # PAID
    # ---------------------------------------------

    if table.status == "PAID":

        average_paid = (
            get_average_status_duration_minutes(
                db=db,
                table_id=table.id,
                status_name="PAID",
                default_minutes=5.0,
            )
        )

        elapsed = get_current_status_elapsed_minutes(
            db,
            table.id,
            "PAID",
        )

        cleaning_average = (
            get_average_status_duration_minutes(
                db=db,
                table_id=table.id,
                status_name="CLEANING",
                default_minutes=10.0,
            )
        )

        return round(
            max(average_paid - elapsed, 0)
            + cleaning_average,
            1,
        )

    # ---------------------------------------------
    # CLEANING
    # ---------------------------------------------

    if table.status == "CLEANING":

        average_cleaning = (
            get_average_status_duration_minutes(
                db=db,
                table_id=table.id,
                status_name="CLEANING",
                default_minutes=10.0,
            )
        )

        elapsed = get_current_status_elapsed_minutes(
            db,
            table.id,
            "CLEANING",
        )

        return round(
            max(
                average_cleaning - elapsed,
                0,
            ),
            1,
        )

    # Unknown status fallback
    return 30.0


# ---------------------------------------------------------
# CONFIDENCE CALCULATION
# ---------------------------------------------------------

def calculate_prediction_confidence(
    db: Session,
    table_id: str,
    party_size: int,
) -> int:
    """
    Confidence increases when more historical
    completed sessions exist.
    """

    table_sessions = (
        db.query(DiningSession)
        .filter(
            DiningSession.table_id == table_id,
            DiningSession.closed_at.isnot(None),
        )
        .count()
    )

    matching_party_sessions = (
        db.query(DiningSession)
        .filter(
            DiningSession.table_id == table_id,
            DiningSession.party_size == party_size,
            DiningSession.closed_at.isnot(None),
        )
        .count()
    )

    confidence = 50

    # Historical sessions for this table
    confidence += min(
        table_sessions * 4,
        30,
    )

    # Extra confidence for same-size parties
    confidence += min(
        matching_party_sessions * 3,
        15,
    )

    return min(
        confidence,
        95,
    )


# ---------------------------------------------------------
# MAIN RECOMMENDATION
# ---------------------------------------------------------

def recommend_table_for_party(
    db: Session,
    party_size: int,
) -> dict:
    """
    Find all suitable tables and predict
    the wait time for each one.
    """

    tables = (
        db.query(Table)
        .filter(
            Table.capacity >= party_size,
        )
        .all()
    )

    predictions = []

    for table in tables:

        wait_minutes = predict_table_wait_time(
            db,
            table,
        )

        predictions.append(
            {
                "table_id": table.id,
                "table_number": table.number,
                "capacity": table.capacity,
                "current_status": table.status,
                "estimated_wait_minutes": wait_minutes,
            }
        )

    # Sort:
    #
    # 1. Shortest waiting time
    # 2. Smallest suitable table
    predictions.sort(
        key=lambda item: (
            item["estimated_wait_minutes"],
            item["capacity"],
        )
    )

    if not predictions:

        return {
            "recommended_table": None,
            "estimated_wait_minutes": None,
            "confidence": 0,
            "all_predictions": [],
        }

    best = predictions[0]

    confidence = calculate_prediction_confidence(
        db=db,
        table_id=best["table_id"],
        party_size=party_size,
    )

    return {
        "recommended_table": best,
        "estimated_wait_minutes": best[
            "estimated_wait_minutes"
        ],
        "confidence": confidence,
        "all_predictions": predictions,
    }


def estimate_wait_time(
    db: Session,
    guests: int,
) -> dict:
    """
    Alias for recommend_table_for_party used by ai_waitlist router.
    """
    return recommend_table_for_party(
        db=db,
        party_size=guests,
    )


def normalize_status(status: str | None) -> str:
    """
    Normalize a table status string or enum to an uppercase string.
    """
    if not status:
        return "AVAILABLE"
    if hasattr(status, "value"):
        return str(status.value).upper()
    return str(status).upper()


def calculate_historical_wait(
    db: Session,
    table_id: str,
    current_status: str,
) -> float | None:
    """
    Calculate the estimated remaining wait for a table using historical duration / current status.
    """
    norm = normalize_status(current_status)
    if norm == "AVAILABLE":
        return 0.0
    table = db.query(Table).filter(Table.id == table_id).first()
    if table:
        return predict_table_wait_time(db, table)
    return None

