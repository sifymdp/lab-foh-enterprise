from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Table, StatusHistory, Reservation


class AIWaitPredictionService:
    """
    AI-style wait-time prediction engine.

    Uses:
    - current table status
    - table capacity
    - historical status transitions
    - day of week
    - time of day
    - current reservations

    The system is designed so that a real ML model
    can replace the prediction logic later when
    sufficient historical data is available.
    """

    def predict_wait(
        self,
        db: Session,
        guests: int,
        requested_datetime: datetime,
    ):
        # ---------------------------------------------------------
        # 1. Get restaurant tables
        # ---------------------------------------------------------

        tables = db.scalars(
            select(Table)
            .where(Table.capacity >= guests)
        ).all()

        if not tables:
            return {
                "predicted_wait_minutes": None,
                "demand": "HIGH",
                "confidence": 90,
                "reason": (
                    "No table has enough capacity for "
                    f"{guests} guests."
                ),
                "available_tables": 0,
                "busy_tables": 0,
                "reservation_count": 0,
                "table_predictions": [],
            }

        # ---------------------------------------------------------
        # 2. Count current table states
        # ---------------------------------------------------------

        available_tables = 0
        busy_tables = 0

        table_predictions = []

        for table in tables:

            status = (table.status or "").upper()

            if status == "AVAILABLE":
                wait_minutes = 0
                available_tables += 1

            elif status == "BILLING":
                wait_minutes = 15
                busy_tables += 1

            elif status == "CLEANING":
                wait_minutes = 10
                busy_tables += 1

            elif status == "SEATED":
                wait_minutes = 45
                busy_tables += 1

            elif status == "ACTIVE":
                wait_minutes = 45
                busy_tables += 1

            elif status == "RESERVED":
                wait_minutes = 30
                busy_tables += 1

            else:
                wait_minutes = 30
                busy_tables += 1

            table_predictions.append(
                {
                    "table_number": table.number,
                    "capacity": table.capacity,
                    "status": status,
                    "estimated_wait_minutes": wait_minutes,
                }
            )

        # ---------------------------------------------------------
        # 3. Count reservations around requested time
        # ---------------------------------------------------------

        window_start = requested_datetime - timedelta(minutes=30)
        window_end = requested_datetime + timedelta(minutes=30)

        reservation_count = len(
            db.scalars(
                select(Reservation.id)
                .where(
                    Reservation.reserved_for >= window_start,
                    Reservation.reserved_for <= window_end,
                    Reservation.status.in_(
                        ["PENDING", "SEATED"]
                    ),
                )
            ).all()
        )

        # ---------------------------------------------------------
        # 4. Analyze historical restaurant behavior
        # ---------------------------------------------------------

        historical_wait = self._historical_wait_estimate(
            db=db,
            requested_datetime=requested_datetime,
        )

        # ---------------------------------------------------------
        # 5. Calculate predicted wait
        # ---------------------------------------------------------

        if available_tables > 0:
            predicted_wait = 0

        else:
            predicted_wait = historical_wait

            if predicted_wait is None:
                predicted_wait = self._fallback_wait(
                    busy_tables
                )

        # Reservation pressure can increase expected waiting time.

        if reservation_count > 0:
            predicted_wait += reservation_count * 5

        # ---------------------------------------------------------
        # 6. Predict demand
        # ---------------------------------------------------------

        demand = self._predict_demand(
            available_tables=available_tables,
            busy_tables=busy_tables,
            reservation_count=reservation_count,
            requested_datetime=requested_datetime,
        )

        # ---------------------------------------------------------
        # 7. Estimate confidence
        # ---------------------------------------------------------

        confidence = self._calculate_confidence(
            historical_wait=historical_wait,
            available_tables=available_tables,
            reservation_count=reservation_count,
        )

        # ---------------------------------------------------------
        # 8. Human-readable explanation
        # ---------------------------------------------------------

        if predicted_wait == 0:
            reason = (
                "A suitable table is currently available."
            )

        elif predicted_wait <= 15:
            reason = (
                "The restaurant is moderately busy. "
                "A table is expected to become available soon."
            )

        elif predicted_wait <= 30:
            reason = (
                "Several tables are currently occupied. "
                "Historical table turnover suggests a moderate wait."
            )

        else:
            reason = (
                "The restaurant is busy and historical table "
                "turnover suggests a longer waiting time."
            )

        return {
            "guests": guests,
            "predicted_wait_minutes": predicted_wait,
            "demand": demand,
            "confidence": confidence,
            "reason": reason,
            "available_tables": available_tables,
            "busy_tables": busy_tables,
            "reservation_count": reservation_count,
            "table_predictions": table_predictions,
        }

    # =============================================================
    # HISTORICAL WAIT ESTIMATION
    # =============================================================

    def _historical_wait_estimate(
        self,
        db: Session,
        requested_datetime: datetime,
    ):
        """
        Look at historical status transitions that occurred
        around the same hour and day of week.

        This makes the prediction restaurant-specific.
        """

        records = db.scalars(
            select(StatusHistory)
        ).all()

        durations = []

        requested_hour = requested_datetime.hour
        requested_day = requested_datetime.isoweekday()

        for record in records:

            if record.changed_at is None:
                continue

            changed_at = record.changed_at

            if changed_at.hour != requested_hour:
                continue

            if changed_at.isoweekday() != requested_day:
                continue

            if record.from_status == "BILLING":
                durations.append(15)

            elif record.from_status == "SEATED":
                durations.append(45)

            elif record.from_status == "ACTIVE":
                durations.append(45)

            elif record.from_status == "CLEANING":
                durations.append(10)

        if not durations:
            return None

        average_wait = sum(durations) / len(durations)

        return round(average_wait)

    # =============================================================
    # FALLBACK WAIT ESTIMATION
    # =============================================================

    def _fallback_wait(self, busy_tables: int):

        if busy_tables <= 1:
            return 10

        if busy_tables == 2:
            return 20

        if busy_tables == 3:
            return 30

        return 45

    # =============================================================
    # DEMAND PREDICTION
    # =============================================================

    def _predict_demand(
        self,
        available_tables: int,
        busy_tables: int,
        reservation_count: int,
        requested_datetime: datetime,
    ):

        total_tables = available_tables + busy_tables

        if total_tables == 0:
            return "HIGH"

        occupancy_ratio = busy_tables / total_tables

        # Reservation pressure increases demand.

        if reservation_count >= 3:
            return "HIGH"

        if occupancy_ratio >= 0.75:
            return "HIGH"

        if occupancy_ratio >= 0.40:
            return "NORMAL"

        return "LOW"

    # =============================================================
    # CONFIDENCE
    # =============================================================

    def _calculate_confidence(
        self,
        historical_wait,
        available_tables,
        reservation_count,
    ):

        confidence = 70

        if historical_wait is not None:
            confidence += 15

        if available_tables > 0:
            confidence += 10

        if reservation_count == 0:
            confidence += 5

        return min(confidence, 95)


# Shared service object

ai_wait_prediction_service = AIWaitPredictionService()
