from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.ai_timeslot_service import (
    recommend_time_slots,
)


router = APIRouter(
    prefix="/ai-booking",
    tags=["AI Booking"],
)


class TimeSlotRequest(BaseModel):

    guests: int = Field(
        ...,
        ge=1,
        description="Number of guests",
    )

    requested_time: datetime = Field(
        ...,
        description=(
            "Preferred booking time in ISO format"
        ),
    )


@router.post("/recommend-time")
def recommend_time(
    request: TimeSlotRequest,
    db: Session = Depends(get_db),
):
    """
    AI recommends the best nearby booking time.
    """

    result = recommend_time_slots(
        db=db,
        guests=request.guests,
        requested_time=request.requested_time,
    )

    return result
