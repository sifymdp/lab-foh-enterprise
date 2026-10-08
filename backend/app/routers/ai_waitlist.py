from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.ai_waitlist_service import estimate_wait_time


router = APIRouter(
    prefix="/ai-booking",
    tags=["AI Booking"],
)


class WaitlistRequest(BaseModel):
    guests: int = Field(
        ...,
        ge=1,
        description="Number of guests",
    )


@router.post("/wait-time")
def get_wait_time(
    request: WaitlistRequest,
    db: Session = Depends(get_db),
):
    """
    AI-assisted waiting-time prediction.
    """

    result = estimate_wait_time(
        db=db,
        guests=request.guests,
    )

    return {
        "guests": request.guests,
        **result,
    }
