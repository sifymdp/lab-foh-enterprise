from typing import Any
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, Form, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import voice_receptionist_service

router = APIRouter(prefix="/voice", tags=["AI Voice Receptionist"])


class VoiceCallSimulateRequest(BaseModel):
    transcript: str = Field(..., description="Spoken transcript or text message from caller")
    caller_phone: str | None = Field(default=None, description="Optional phone number of caller")


class VoiceParseRequest(BaseModel):
    transcript: str = Field(...)


@router.post("/simulate-call")
def simulate_voice_call(
    payload: VoiceCallSimulateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Simulate an incoming telephone reservation call through the AI Voice Receptionist."""
    if not payload.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty")

    result = voice_receptionist_service.process_voice_reservation(
        db=db,
        transcript=payload.transcript,
        caller_phone=payload.caller_phone,
    )
    return result


@router.post("/parse-only")
def parse_voice_transcript(
    payload: VoiceParseRequest,
) -> dict[str, Any]:
    """Parse transcript parameters (party size, name, time, requests) without creating a booking."""
    return voice_receptionist_service.parse_voice_booking_transcript(payload.transcript)


@router.post("/webhook")
def twilio_voice_webhook(
    SpeechResult: str | None = Form(None),
    From: str | None = Form(None),
    CallSid: str | None = Form(None),
    db: Session = Depends(get_db),
) -> Response:
    """Twilio Voice webhook endpoint returning standard TwiML XML."""
    if SpeechResult and SpeechResult.strip():
        # Caller spoke a request
        result = voice_receptionist_service.process_voice_reservation(
            db=db,
            transcript=SpeechResult,
            caller_phone=From,
        )
        spoken_text = result["voice_response"]

        root = ET.Element("Response")
        say = ET.SubElement(root, "Say", voice="Polly.Amy")
        say.text = spoken_text
        twiml = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")
        return Response(content=twiml, media_type="application/xml")

    # Initial greeting with Gather
    root = ET.Element("Response")
    gather = ET.SubElement(
        root,
        "Gather",
        input="speech",
        action="/voice/webhook",
        method="POST",
        speechTimeout="auto",
        timeout="6",
    )
    say = ET.SubElement(gather, "Say", voice="Polly.Amy")
    say.text = (
        "Hello! Thank you for calling FOH Restaurant. "
        "Please tell me the date, time, party size, and your name to reserve a table."
    )
    twiml = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")
    return Response(content=twiml, media_type="application/xml")
