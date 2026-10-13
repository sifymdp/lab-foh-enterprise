"""
Restaurant Digital Twin - REST API Router
─────────────────────────────────────────
Endpoints for fetching real-time digital twin snapshots, historical event replay,
what-if scenario simulations, and layout versions.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.digital_twin import DigitalTwinSimulation
from app.models.user import User
from app.models.vision import FloorPlanVersion
from app.services.digital_twin.simulation_service import (
    compare_simulations,
    get_simulation_result,
    run_what_if_simulation,
)
from app.services.digital_twin.twin_service import (
    get_digital_twin_snapshot,
    get_historical_replay,
)

router = APIRouter(prefix="/digital-twin", tags=["digital-twin"])


class CreateSimulationIn(BaseModel):
    floor_id: str
    name: str = "Scenario Test"
    scenario_type: str = "CAPACITY_STRESS"  # CAPACITY_STRESS | SECTION_CLOSURE | SURGE_ARRIVAL | STAFF_BOTTLENECK
    assumptions: dict[str, Any] = {}


class CompareSimulationsIn(BaseModel):
    simulation_id_a: str
    simulation_id_b: str


@router.get("/snapshot/{floor_id}")
def get_snapshot(
    floor_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Returns authoritative floor plan geometry, live table states, and operational overlays."""
    res = get_digital_twin_snapshot(db, floor_id, user.tenant_id, user.branch_id)
    if "error" in res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=res["error"])
    return res


@router.get("/replay/{floor_id}")
def get_replay(
    floor_id: str,
    start_time: str | None = Query(None, description="ISO format start time"),
    end_time: str | None = Query(None, description="ISO format end time"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Returns timeline-based historical replay events for floor state changes."""
    now = datetime.now(timezone.utc)
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except ValueError:
            end_dt = now
    else:
        end_dt = now

    if start_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except ValueError:
            start_dt = end_dt - timedelta(hours=4)
    else:
        start_dt = end_dt - timedelta(hours=4)

    return get_historical_replay(db, floor_id, start_dt, end_dt)


@router.post("/simulations")
def create_simulation(
    payload: CreateSimulationIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Creates and evaluates an isolated what-if operational simulation."""
    try:
        return run_what_if_simulation(
            db,
            floor_id=payload.floor_id,
            name=payload.name,
            scenario_type=payload.scenario_type,
            assumptions=payload.assumptions,
            user_id=user.id,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/simulations")
def list_simulations(
    floor_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Lists recent simulations."""
    q = db.query(DigitalTwinSimulation).order_by(desc(DigitalTwinSimulation.created_at))
    if floor_id:
        q = q.filter(DigitalTwinSimulation.floor_id == floor_id)
    sims = q.limit(limit).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "scenario_type": s.scenario_type,
            "floor_id": s.floor_id,
            "results": json.loads(s.results_json or "{}"),
            "duration_ms": s.duration_ms,
            "created_at": s.created_at.isoformat(),
        }
        for s in sims
    ]


@router.get("/simulations/{simulation_id}")
def get_simulation(
    simulation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Retrieves full details and mathematical projections of a simulation."""
    res = get_simulation_result(db, simulation_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    return res


@router.post("/simulations/compare")
def compare_two_simulations(
    payload: CompareSimulationsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Performs side-by-side comparison of two what-if scenarios."""
    try:
        return compare_simulations(db, payload.simulation_id_a, payload.simulation_id_b)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/layout-versions/{floor_id}")
def get_layout_versions(
    floor_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Retrieves layout snapshot version history for the floor."""
    versions = (
        db.query(FloorPlanVersion)
        .filter(FloorPlanVersion.floor_id == floor_id)
        .order_by(desc(FloorPlanVersion.version_number))
        .all()
    )
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "change_summary": v.change_summary,
            "created_by": v.created_by,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]
