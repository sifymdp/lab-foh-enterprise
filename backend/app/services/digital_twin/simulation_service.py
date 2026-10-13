"""
Restaurant Digital Twin - What-If Simulation Sandbox Engine
──────────────────────────────────────────────────────────
Provides deterministic mathematical projections for hypothetical floor scenarios:
- Temporary section closures (e.g., Patio weather closures)
- Surge customer arrivals (+20%, +50%)
- Staffing reductions & kitchen preparation bottlenecks
Completely isolated in-memory calculations; never modifies operational records.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.models.digital_twin import DigitalTwinSimulation
from app.models.floor import Floor
from app.models.table import Table

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_what_if_simulation(
    db: Session,
    floor_id: str,
    name: str,
    scenario_type: str,
    assumptions: dict[str, Any],
    user_id: str | None = None,
) -> dict[str, Any]:
    """
    Simulates operational impact of floor modifications or load surges.
    """
    start_time = time.perf_counter()
    floor = db.get(Floor, floor_id)
    if not floor:
        raise ValueError("Floor not found")

    tables = db.query(Table).filter(Table.floor_id == floor_id).all()
    baseline_capacity = sum(t.capacity for t in tables)
    baseline_table_count = len(tables)

    disabled_table_ids = set(assumptions.get("disabled_table_ids", []))
    closed_sections = set(assumptions.get("closed_sections", []))
    arrival_surge_pct = float(assumptions.get("arrival_surge_pct", 0.0))
    staff_count = int(assumptions.get("staff_count", max(1, baseline_table_count // 4)))

    # Filter active simulated tables
    sim_tables = [
        t for t in tables
        if t.id not in disabled_table_ids and t.section_id not in closed_sections
    ]
    sim_capacity = sum(t.capacity for t in sim_tables)
    sim_table_count = len(sim_tables)

    # Deterministic projections
    capacity_reduction_pct = round(
        ((baseline_capacity - sim_capacity) / max(1, baseline_capacity)) * 100, 1
    )

    # Base turn time is ~60 minutes. Less staff increases turnaround time by 15% per missing waiter
    standard_staff = max(1, baseline_table_count // 4)
    staff_ratio = min(2.0, max(0.5, staff_count / standard_staff))
    projected_turn_time_min = round(60.0 / staff_ratio, 1)

    # Surge arrivals impact wait times
    effective_demand = 1.0 + (arrival_surge_pct / 100.0)
    supply_ratio = sim_capacity / max(1, baseline_capacity)
    bottleneck_factor = effective_demand / max(0.1, supply_ratio)

    estimated_wait_time_min = round(max(0.0, (bottleneck_factor - 1.0) * 45.0), 1)
    workload_pressure_score = min(100, round(bottleneck_factor * 50.0))

    results = {
        "scenario_type": scenario_type,
        "baseline": {
            "table_count": baseline_table_count,
            "total_capacity": baseline_capacity,
            "standard_staff": standard_staff,
            "avg_turn_time_min": 60.0,
        },
        "simulation": {
            "active_table_count": sim_table_count,
            "active_capacity": sim_capacity,
            "capacity_loss_percent": capacity_reduction_pct,
            "assigned_staff": staff_count,
            "projected_turn_time_min": projected_turn_time_min,
            "estimated_peak_wait_min": estimated_wait_time_min,
            "workload_pressure_score": workload_pressure_score,
            "recommended_actions": [],
        },
    }

    # Actionable guidance
    if estimated_wait_time_min > 20:
        results["simulation"]["recommended_actions"].append(
            "Activate waitlist buffer and notify hosts to pace arrivals."
        )
    if workload_pressure_score > 75:
        results["simulation"]["recommended_actions"].append(
            "Alert kitchen manager to stage popular prep batches."
        )
    if capacity_reduction_pct > 30:
        results["simulation"]["recommended_actions"].append(
            "Reallocate reservations from closed sections to primary indoor dining."
        )

    duration_ms = (time.perf_counter() - start_time) * 1000

    # Persist simulation
    sim_record = DigitalTwinSimulation(
        id=f"sim-{new_id()}",
        tenant_id=floor.tenant_id,
        branch_id=floor.branch_id,
        floor_id=floor_id,
        name=name,
        scenario_type=scenario_type,
        assumptions_json=json.dumps(assumptions),
        results_json=json.dumps(results),
        status="COMPLETED",
        duration_ms=round(duration_ms, 2),
        created_by_user_id=user_id,
    )
    db.add(sim_record)
    db.commit()

    return {
        "simulation_id": sim_record.id,
        "name": sim_record.name,
        "scenario_type": scenario_type,
        "results": results,
        "duration_ms": round(duration_ms, 2),
        "created_at": sim_record.created_at.isoformat(),
    }


def get_simulation_result(db: Session, simulation_id: str) -> dict[str, Any] | None:
    """Retrieves stored simulation results."""
    sim = db.get(DigitalTwinSimulation, simulation_id)
    if not sim:
        return None
    return {
        "id": sim.id,
        "name": sim.name,
        "scenario_type": sim.scenario_type,
        "assumptions": json.loads(sim.assumptions_json or "{}"),
        "results": json.loads(sim.results_json or "{}"),
        "duration_ms": sim.duration_ms,
        "created_at": sim.created_at.isoformat(),
    }


def compare_simulations(db: Session, sim_id_a: str, sim_id_b: str) -> dict[str, Any]:
    """Compares two simulations side-by-side."""
    a = get_simulation_result(db, sim_id_a)
    b = get_simulation_result(db, sim_id_b)
    if not a or not b:
        raise ValueError("One or both simulations could not be found")

    res_a = a["results"]["simulation"]
    res_b = b["results"]["simulation"]

    return {
        "simulation_a": a,
        "simulation_b": b,
        "comparison": {
            "capacity_diff": res_b["active_capacity"] - res_a["active_capacity"],
            "wait_time_diff_min": round(res_b["estimated_peak_wait_min"] - res_a["estimated_peak_wait_min"], 1),
            "pressure_diff": res_b["workload_pressure_score"] - res_a["workload_pressure_score"],
        },
    }
