from datetime import datetime, date, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reservation, Table


class AIBookingService:
    """
    AI Smart Booking Engine.

    This version uses REAL restaurant data:
    - Real tables
    - Real table capacity
    - Real table status
    - Real reservations

    It recommends the best available table and time.
    """

    # Reservation statuses that mean the table is occupied
    # for the requested booking time.
    ACTIVE_RESERVATION_STATUSES = {
        "PENDING",
        "SEATED",
    }

    def get_smart_recommendations(
        self,
        db: Session,
        requested_date: str,
        requested_time: str,
        guests: int,
    ):
        """
        Find the best table and nearby booking times.

        Example:

        requested_date = "2026-08-24"
        requested_time = "19:30"
        guests = 5
        """

        # ---------------------------------------------------------
        # 1. Convert the customer's date and time into datetime
        # ---------------------------------------------------------

        try:
            booking_date = date.fromisoformat(requested_date)
            booking_time = time.fromisoformat(requested_time)

        except ValueError:
            raise ValueError(
                "Date must be YYYY-MM-DD and time must be HH:MM"
            )

        requested_datetime = datetime.combine(
            booking_date,
            booking_time
        )

        # ---------------------------------------------------------
        # 2. Check nearby time slots
        # ---------------------------------------------------------

        nearby_minutes = [-30, -15, 0, 15, 30]

        recommendations = []

        for minutes in nearby_minutes:

            slot_datetime = requested_datetime + timedelta(
                minutes=minutes
            )

            result = self._find_best_table(
                db=db,
                booking_datetime=slot_datetime,
                guests=guests,
            )

            time_score = self._calculate_time_score(
                slot_datetime.hour
            )

            if result is None:

                recommendations.append(
                    {
                        "time": slot_datetime.strftime("%H:%M"),
                        "available": False,
                        "table_id": None,
                        "table_number": None,
                        "table_capacity": None,
                        "availability_score": 0,
                        "recommended": False,
                    }
                )

                continue

            # Combine table suitability and time suitability.
            final_score = round(
                (result["table_score"] * 0.8)
                + (time_score * 0.2)
            )

            recommendations.append(
                {
                    "time": slot_datetime.strftime("%H:%M"),
                    "available": True,
                    "table_id": result["table_id"],
                    "table_number": result["table_number"],
                    "table_capacity": result["table_capacity"],
                    "availability_score": final_score,
                    "recommended": False,
                }
            )

        # ---------------------------------------------------------
        # 3. Find the highest-scoring option
        # ---------------------------------------------------------

        available_options = [
            item
            for item in recommendations
            if item["available"]
        ]

        if not available_options:

            return {
                "requested_date": requested_date,
                "requested_time": requested_time,
                "guests": guests,
                "available": False,
                "best_time": None,
                "best_table": None,
                "recommendations": recommendations,
                "message": (
                    "No suitable table is available "
                    "around the requested time."
                ),
            }

        best = max(
            available_options,
            key=lambda item: item["availability_score"]
        )

        # ---------------------------------------------------------
        # 4. Mark the best option
        # ---------------------------------------------------------

        best["recommended"] = True

        return {
            "requested_date": requested_date,
            "requested_time": requested_time,
            "guests": guests,
            "available": True,
            "best_time": best["time"],
            "best_table": {
                "id": best["table_id"],
                "number": best["table_number"],
                "capacity": best["table_capacity"],
            },
            "availability_score": best["availability_score"],
            "recommendations": recommendations,
            "message": (
                f"AI recommends Table {best['table_number']} "
                f"at {best['time']}."
            ),
        }

    # =============================================================
    # FIND THE BEST REAL TABLE
    # =============================================================

    def _find_best_table(
        self,
        db: Session,
        booking_datetime: datetime,
        guests: int,
    ):

        # ---------------------------------------------------------
        # Get all tables that are large enough.
        # ---------------------------------------------------------

        tables = db.scalars(
            select(Table)
            .where(Table.capacity >= guests)
        ).all()

        if not tables:
            return None

        # ---------------------------------------------------------
        # Find tables already reserved at this time.
        # ---------------------------------------------------------

        reserved_table_ids = set(
            db.scalars(
                select(Reservation.table_id)
                .where(
                    Reservation.reserved_for <= booking_datetime,
                    Reservation.reserved_until > booking_datetime,
                    Reservation.status.in_(
                        self.ACTIVE_RESERVATION_STATUSES
                    ),
                )
            ).all()
        )

        candidates = []

        for table in tables:

            # -----------------------------------------------------
            # Skip a table that already has a reservation.
            # -----------------------------------------------------

            if table.id in reserved_table_ids:
                continue

            # -----------------------------------------------------
            # Calculate how well the table fits the group.
            # -----------------------------------------------------

            extra_seats = table.capacity - guests

            score = 100

            # We prefer tables that don't have lots of empty seats.
            score -= extra_seats * 8

            # Exact capacity is especially good.
            if table.capacity == guests:
                score += 10

            # -----------------------------------------------------
            # Consider the table's CURRENT status.
            # -----------------------------------------------------

            current_status = (table.status or "").upper()

            if current_status == "AVAILABLE":
                score += 10

            elif current_status == "RESERVED":
                score -= 20

            elif current_status == "CLEANING":
                score -= 10

            elif current_status == "SEATED":
                score -= 15

            # Keep score inside 0-100.
            score = max(0, min(score, 100))

            candidates.append(
                {
                    "table_id": table.id,
                    "table_number": table.number,
                    "table_capacity": table.capacity,
                    "table_score": score,
                }
            )

        if not candidates:
            return None

        # Highest score = best table.
        return max(
            candidates,
            key=lambda item: item["table_score"]
        )

    # =============================================================
    # TIME SCORE
    # =============================================================

    def _calculate_time_score(self, hour: int) -> int:
        """
        Estimate how comfortable the requested time is.

        This is currently a simple intelligent scoring system.
        Later we will replace this part with an actual ML model
        trained using restaurant booking history.
        """

        score = 100

        # Dinner rush
        if hour in [19, 20]:
            score -= 25

        # Lunch rush
        elif hour in [13, 14]:
            score -= 15

        # Very late evening
        elif hour >= 21:
            score -= 10

        return max(20, min(score, 100))


# One shared AI booking service object.
ai_booking_service = AIBookingService()
