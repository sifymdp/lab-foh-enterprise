from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import DiningSession, Table


def get_average_turnover_minutes(
    db: Session,
    table_id: str | None = None,
) -> float:
    """
    Calculate the average completed dining-session duration.

    If table_id is provided, use that table's historical sessions.
    Otherwise use all completed sessions.
    """

    query = db.query(DiningSession).filter(
        DiningSession.closed_at.isnot(None)
    )

    if table_id:
        query = query.filter(DiningSession.table_id == table_id)

    sessions = query.all()

    durations = []

    for session in sessions:

        if not session.seated_at or not session.closed_at:
            continue

        seated_at = session.seated_at
        closed_at = session.closed_at

        # Make naive datetimes timezone-aware if necessary.
        if seated_at.tzinfo is None:
            seated_at = seated_at.replace(tzinfo=timezone.utc)

        if closed_at.tzinfo is None:
            closed_at = closed_at.replace(tzinfo=timezone.utc)

        minutes = (
            closed_at - seated_at
        ).total_seconds() / 60

        if minutes > 0:
            durations.append(minutes)

    if not durations:
        return 60.0

    return round(sum(durations) / len(durations), 1)


def get_session_elapsed_minutes(session: DiningSession) -> float:
    """
    Calculate how many minutes the current customer
    has already spent at the table.
    """

    now = datetime.now(timezone.utc)

    seated_at = session.seated_at

    if seated_at.tzinfo is None:
        seated_at = seated_at.replace(tzinfo=timezone.utc)

    elapsed = (
        now - seated_at
    ).total_seconds() / 60

    return max(elapsed, 0)


def predict_remaining_minutes(
    db: Session,
    table_id: str,
) -> float:
    """
    Predict how many minutes remain before
    the current dining session is expected to finish.
    """

    average_turnover = get_average_turnover_minutes(
        db,
        table_id,
    )

    active_session = (
        db.query(DiningSession)
        .filter(
            DiningSession.table_id == table_id,
            DiningSession.closed_at.is_(None),
        )
        .order_by(DiningSession.seated_at.desc())
        .first()
    )

    if not active_session:
        return 0.0

    elapsed = get_session_elapsed_minutes(active_session)

    remaining = average_turnover - elapsed

    return round(max(remaining, 0), 1)


def predict_table_wait_time(
    db: Session,
    table: Table,
) -> float:
    """
    Predict how long before a table becomes available.
    """

    if table.status == "AVAILABLE":
        return 0.0

    if table.status == "CLEANING":
        # Temporary default cleaning estimate.
        return 10.0

    if table.status in [
        "SEATED",
        "ACTIVE",
        "BILLING",
        "PAID",
    ]:
        return predict_remaining_minutes(
            db,
            table.id,
        )

    if table.status == "RESERVED":
        return 9999.0

    return 30.0


def recommend_table_for_party(
    db: Session,
    party_size: int,
) -> dict:
    """
    Recommend the table with the shortest predicted wait time.
    """

    tables = (
        db.query(Table)
        .filter(Table.capacity >= party_size)
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
                "estimated_wait_minutes": round(
                    wait_minutes,
                    1,
                ),
            }
        )

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

    total_sessions = (
        db.query(DiningSession)
        .filter(
            DiningSession.table_id == best["table_id"],
            DiningSession.closed_at.isnot(None),
        )
        .count()
    )

    confidence = min(
        95,
        50 + (total_sessions * 5),
    )

    return {
        "recommended_table": best,
        "estimated_wait_minutes": best[
            "estimated_wait_minutes"
        ],
        "confidence": confidence,
        "all_predictions": predictions,
    }
