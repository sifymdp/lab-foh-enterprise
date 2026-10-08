"""
System & Equipment Maintenance RAG Knowledge Extractor
────────────────────────────────────────────────────────
Stores operational maintenance history, equipment failure logs, troubleshooting guides,
and verified hardware repairs (KDS terminals, POS printers, CCTV cameras, network devices).

CRITICAL SECURITY CONSTRAINT:
Strictly zero credentials, passwords, API tokens, or network secrets may ever be stored.
"""

from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.services.rag.domains.registry import RAGMetadata
from app.services.rag.ingestion.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)

DEFAULT_MAINTENANCE_RECORDS = [
    {
        "title": "Kitchen KDS Terminal 2 Display Freeze & Reconnect Procedure",
        "source": "FOH Equipment Maintenance Log",
        "equipment_id": "KDS-TERM-02",
        "content": """# KDS Terminal 2 Touchscreen Freeze Incident & Resolution

## 1. Equipment & Problem Description
- **Equipment**: Kitchen Display Screen #2 (Saute Station touch terminal).
- **Symptom**: Display freezes intermittently and does not acknowledge order bump gestures during high-humidity cooking periods.
- **Root Cause**: Thermal throttle on the passive heatsink combined with grease accumulation on the capacitive touch digitizer.

## 2. Verified Troubleshooting & Repair Steps
1. Power down the terminal using the physical rocker switch located under the rubber moisture seal.
2. Clean the capacitive glass surface using an isopropyl alcohol wipe (70% concentration). Avoid spraying liquids directly onto the bezel.
3. Inspect the Ethernet cable clip to ensure connection status LED is solid amber and blinking green.
4. Reboot the terminal; system automatically reconnects to the local WebSocket gateway within 20 seconds.

## 3. Recurring Issue Prevention
- Relocated the terminal mount 40cm away from the open salamander broiler to improve ambient airflow.
- Scheduled weekly digitizer cleaning during Monday morning prep.
""",
    },
    {
        "title": "Front Host Stand Receipt & Chit Printer Jams",
        "source": "FOH Equipment Maintenance Log",
        "equipment_id": "PRINTER-HOST-01",
        "content": """# Host Stand Thermal Printer Paper Jams & Recovery

## 1. Equipment & Problem Description
- **Equipment**: Epson TM-T88VI Thermal Receipt Printer (Host Stand).
- **Symptom**: Red error LED blinks rapidly, cutter fails to cycle, and paper feed jams.
- **Root Cause**: Thermal paper rolls loaded backwards, or paper dust accumulation inside the autocutter track.

## 2. Standard Clearing Procedure
1. Turn off power switch on the side panel.
2. Push the blue cover release lever forward to pop open the paper compartment.
3. If the autocutter blade is stuck in the closed position, rotate the internal thumbwheel until the blade retracts completely.
4. Remove damaged paper, insert roll with paper unrolling from the bottom of the roll (facing the thermal print head).
5. Close cover firmly until an audible click is heard; run self-test by holding the feed button while powering on.
""",
    },
    {
        "title": "CCTV Camera Stream RTSP Reconnect & RTSP Dropouts",
        "source": "FOH Equipment Maintenance Log",
        "equipment_id": "CAM-MAIN-01",
        "content": """# CCTV Overhead Dining Room Camera Stream Dropouts

## 1. Equipment & Problem Description
- **Equipment**: Hikvision / RTSP Overhead Wide-Angle Camera 1 (Table 1 - 12 zone).
- **Symptom**: YOLO vision engine reports 'CAMERA_STREAM_OFFLINE' or frame delivery stuttering.
- **Root Cause**: PoE switch port power negotiation timeout during local network DHCP lease renewal.

## 2. Resolution Steps
1. In the Camera Setup interface (`/camera-setup`), verify ping connectivity to the camera IP address.
2. If offline, power cycle the PoE port on the network switch (Port 4).
3. The video streaming worker automatically re-attempts RTSP connection with exponential backoff (up to 30 seconds).
4. Do not adjust camera lens focus manually; digital ROI bounding boxes are calibrated to the fixed focal length.
""",
    },
]


def seed_maintenance_knowledge(
    db: Session,
    tenant_id: str,
    branch_id: str | None = None,
) -> int:
    """Seeds baseline equipment maintenance and troubleshooting knowledge."""
    count = 0
    for record in DEFAULT_MAINTENANCE_RECORDS:
        meta = RAGMetadata(
            organization_id=tenant_id,
            branch_id=branch_id,
            domain="MAINTENANCE",
            source_type="maintenance_log",
            source_id=record.get("equipment_id", f"maint_{count + 1}"),
            extra={"equipment_id": record.get("equipment_id")},
        ).to_dict()

        res = ingestion_service.ingest_document(
            db=db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            domain="MAINTENANCE",
            source_name=record["source"],
            title=record["title"],
            raw_content=record["content"],
            metadata=meta,
        )
        if res.get("status") in ("SUCCESS", "UNCHANGED"):
            count += 1
    logger.info("Seeded %d maintenance records for tenant %s.", count, tenant_id)
    return count
