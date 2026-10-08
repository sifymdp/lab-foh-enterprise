from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.ai_booking_service import ai_booking_service
from app.services.ai_wait_prediction import ai_wait_prediction_service
from app.services.ai_training_data import (
    build_clean_training_data,
    summarize_training_data,
)

from app.services.ai_prediction import recommend_table
from app.services.ai_waitlist import (
    predict_waiting_time,
)


router = APIRouter(
    prefix="/ai-booking",
    tags=["AI Smart Booking"]
)


class SmartBookingRequest(BaseModel):
    requested_date: str = Field(
        ...,
        description="Booking date in YYYY-MM-DD format"
    )

    requested_time: str = Field(
        ...,
        description="Booking time in HH:MM format"
    )

    guests: int = Field(
        ...,
        ge=1,
        description="Number of guests"
    )

class WaitPredictionRequest(BaseModel):
    requested_date: str = Field(
        ...,
        description="Booking date in YYYY-MM-DD format"
    )

    requested_time: str = Field(
        ...,
        description="Booking time in HH:MM format"
    )

    guests: int = Field(
        ...,
        ge=1,
        description="Number of guests"
    )

class AIPredictionRequest(BaseModel):
    requested_date: str = Field(
        ...,
        description="Booking date in YYYY-MM-DD format"
    )

    requested_time: str = Field(
        ...,
        description="Booking time in HH:MM format"
    )

    guests: int = Field(
        ...,
        ge=1,
        description="Number of guests"
    )

class AIWaitlistRequest(BaseModel):

    requested_date: str = Field(
        ...,
        description="Booking date in YYYY-MM-DD format"
    )

    requested_time: str = Field(
        ...,
        description="Booking time in HH:MM format"
    )

    guests: int = Field(
        ...,
        ge=1,
        description="Number of guests"
    )

@router.post("/smart-recommend")
def smart_booking_recommendation(
    data: SmartBookingRequest,
    db: Session = Depends(get_db),
):
    """
    AI Smart Booking Recommendation.

    Uses:
    - Real tables
    - Real table capacity
    - Real table status
    - Existing reservations
    """

    try:

        result = ai_booking_service.get_smart_recommendations(
            db=db,
            requested_date=data.requested_date,
            requested_time=data.requested_time,
            guests=data.guests,
        )

        return result

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

@router.get("/training-data-preview")
def training_data_preview(
    db: Session = Depends(get_db),
):
    """
    Preview the cleaned dataset that will eventually
    be used for ML training.
    """

    training_rows = build_clean_training_data(
        db
    )

    summary = summarize_training_data(
        training_rows
    )

    return {
        "training_rows": training_rows,
        "summary": summary,
    }

@router.post("/ai-predict")
def ai_predict(
    data: AIPredictionRequest,
    db: Session = Depends(get_db),
):
    """
    AI-powered table prediction.

    Uses:

    - table capacity
    - current table status
    - historical table behavior
    - reservation pressure
    - requested booking time
    """

    try:
        from datetime import datetime

        requested_datetime = datetime.fromisoformat(
            f"{data.requested_date}T{data.requested_time}"
        )

        result = recommend_table(
            db=db,
            party_size=data.guests,
            requested_time=requested_datetime,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

@router.post("/waitlist-predict")
def waitlist_predict(
    data: AIWaitlistRequest,
    db: Session = Depends(get_db),
):
    """
    AI-powered waiting-list prediction.

    Predicts:

    - expected waiting time
    - demand level
    - confidence
    - reservation pressure
    - table availability
    """

    try:

        from datetime import datetime

        requested_datetime = datetime.fromisoformat(
            f"{data.requested_date}T{data.requested_time}"
        )

        result = predict_waiting_time(
            db=db,
            guests=data.guests,
            requested_time=requested_datetime,
        )

        return result

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

@router.post("/predict-wait")
def predict_wait(
    data: WaitPredictionRequest,
    db: Session = Depends(get_db),
):
    """
    AI restaurant waiting-time prediction.
    """

    try:
        requested_datetime = datetime.fromisoformat(
            f"{data.requested_date}T{data.requested_time}"
        )

        result = ai_wait_prediction_service.predict_wait(
            db=db,
            guests=data.guests,
            requested_datetime=requested_datetime,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )
