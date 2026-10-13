"""
Health Guardian - Autonomous Audit & Lifecycle Coordinator
──────────────────────────────────────────────────────────
Coordinates 12-hour comprehensive audits, distributed locking,
incident lifecycle, and alert deduplication.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.models.health_guardian import (
    HealthAlert,
    HealthAudit,
    HealthCheckResult,
    RecoveryActionLog,
    SystemIncident,
)
from app.services.health_guardian.error_classifier import classify_error
from app.services.health_guardian.health_check_registry import run_all_probes
from app.services.health_guardian.recovery_policy_registry import execute_recovery_action

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _worker_host_id() -> str:
    return f"{platform.node()}-{os.getpid()}"


def run_comprehensive_audit(db: Session, audit_type: str = "SCHEDULED_12H") -> dict[str, Any]:
    """
    Executes a comprehensive health audit across all registered subsystems.
    Acquires an execution lock, runs probes, triggers allowlisted recoveries
    for degraded components, records incidents, and schedules the next 12h run.
    """
    now = _utc_now()
    host_id = _worker_host_id()

    # 1. Distributed Execution Lock Check (prevents concurrent duplicate runs)
    active_audit = db.query(HealthAudit).filter(
        HealthAudit.is_active.is_(True),
        HealthAudit.started_at > now - timedelta(minutes=15)
    ).first()

    if active_audit:
        logger.info("Audit already running by lock owner %s, skipping.", active_audit.lock_owner)
        return {"status": "SKIPPED", "reason": "Another audit cycle is currently active"}

    # 2. Create durable audit entry
    audit_id = f"audit-{new_id()}"
    next_run = now + timedelta(hours=12)

    audit_record = HealthAudit(
        id=audit_id,
        audit_type=audit_type,
        overall_status="UNKNOWN",
        scheduled_at=now,
        started_at=now,
        lock_owner=host_id,
        is_active=True,
        next_scheduled_run=next_run,
    )
    db.add(audit_record)
    db.commit()

    start_perf = time.perf_counter()
    overall_status = "HEALTHY"
    recovery_logs_summary: list[dict[str, Any]] = []

    try:
        # 3. Execute all subsystem probes
        probe_results = run_all_probes(db)

        # 4. Process each probe result
        for probe in probe_results:
            comp_name = probe["component"]
            comp_status = probe["status"]
            comp_latency = probe["latency_ms"]
            comp_msg = probe["message"]
            comp_metrics = json.dumps(probe.get("metrics", {}))

            if comp_status in ("FAIL", "WARN") and overall_status == "HEALTHY":
                overall_status = "DEGRADED" if comp_status == "WARN" else "UNHEALTHY"

            # Record HealthCheckResult
            res_record = HealthCheckResult(
                id=f"hcr-{new_id()}",
                audit_id=audit_id,
                component=comp_name,
                status=comp_status,
                latency_ms=comp_latency,
                message=comp_msg,
                metrics_json=comp_metrics,
            )
            db.add(res_record)

            # 5. Handle degradation or failure
            if comp_status in ("FAIL", "WARN"):
                classified = classify_error(comp_name, comp_msg, probe.get("metrics"))

                # Check for existing open incident for this component
                incident = db.query(SystemIncident).filter(
                    SystemIncident.component == comp_name,
                    SystemIncident.status.in_(["OPEN", "RECOVERING"]),
                ).first()

                if not incident:
                    incident = SystemIncident(
                        id=f"inc-{new_id()}",
                        component=comp_name,
                        severity=classified["severity"],
                        error_category=classified["category"],
                        title=f"{comp_name} Health Issue: {comp_status}",
                        description=comp_msg,
                        status="OPEN",
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                    db.add(incident)
                    db.flush()
                else:
                    incident.occurrence_count += 1
                    incident.last_seen_at = now
                    incident.description = comp_msg

                # 6. Automated Safe Recovery Attempt
                rec_action = classified.get("recommended_recovery")
                if rec_action:
                    incident.status = "RECOVERING"
                    rec_result = execute_recovery_action(db, rec_action)

                    rec_log = RecoveryActionLog(
                        id=f"rec-{new_id()}",
                        incident_id=incident.id,
                        action_name=rec_action,
                        status=rec_result["status"],
                        output_summary=json.dumps(rec_result.get("output", rec_result.get("error"))),
                        verification_passed=rec_result["verification_passed"],
                        duration_ms=rec_result.get("duration_ms", 0.0),
                    )
                    db.add(rec_log)

                    if rec_result["status"] == "SUCCESS" and rec_result["verification_passed"]:
                        incident.status = "RESOLVED"
                        incident.resolved_at = _utc_now()
                        incident.resolution_notes = f"Self-healed via automated action {rec_action}"

                    recovery_logs_summary.append({
                        "component": comp_name,
                        "action": rec_action,
                        "result": rec_result["status"],
                        "verified": rec_result["verification_passed"],
                    })

                # Deduplicated Health Alert
                dedup_key = f"{comp_name}:{classified['category']}"
                recent_alert = db.query(HealthAlert).filter(
                    HealthAlert.dedup_key == dedup_key,
                    HealthAlert.created_at > now - timedelta(hours=1),
                ).first()

                if not recent_alert:
                    alert = HealthAlert(
                        id=f"alt-{new_id()}",
                        component=comp_name,
                        severity=classified["severity"],
                        title=f"{comp_name} Degraded",
                        message=comp_msg,
                        dedup_key=dedup_key,
                        channel="SYSTEM_LOG",
                    )
                    db.add(alert)

        duration_ms = (time.perf_counter() - start_perf) * 1000

        # Finalize audit record
        audit_record.overall_status = overall_status
        audit_record.completed_at = _utc_now()
        audit_record.duration_ms = round(duration_ms, 2)
        audit_record.is_active = False
        audit_record.summary_json = json.dumps({
            "probes_count": len(probe_results),
            "recoveries_attempted": len(recovery_logs_summary),
            "recoveries": recovery_logs_summary,
        })
        db.commit()

        logger.info(
            "Health audit %s completed in %.2fms. Overall status: %s",
            audit_id, duration_ms, overall_status
        )

        return {
            "audit_id": audit_id,
            "overall_status": overall_status,
            "duration_ms": round(duration_ms, 2),
            "recoveries": recovery_logs_summary,
            "next_scheduled_run": next_run.isoformat(),
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Health audit %s failed", audit_id)
        # Release lock on error
        try:
            audit_record.is_active = False
            audit_record.overall_status = "UNHEALTHY"
            db.commit()
        except Exception:
            pass
        return {"status": "FAILED", "error": str(exc)}


def run_lightweight_probe(db: Session) -> dict[str, Any]:
    """Runs a fast 60s probe for database and websockets without heavy checks."""
    from app.services.health_guardian.health_check_registry import check_database, check_websockets

    db_res = check_database(db)
    ws_res = check_websockets()

    is_ok = db_res["status"] == "PASS" and ws_res["status"] == "PASS"
    return {
        "status": "PASS" if is_ok else "DEGRADED",
        "database": db_res,
        "websockets": ws_res,
        "timestamp": _utc_now().isoformat(),
    }


def get_latest_health_summary(db: Session) -> dict[str, Any]:
    """Retrieves the latest audit summary and operational status."""
    latest = db.query(HealthAudit).order_by(desc(HealthAudit.started_at)).first()
    open_incidents_count = db.query(func.count(SystemIncident.id)).filter(
        SystemIncident.status.in_(["OPEN", "RECOVERING"])
    ).scalar() or 0

    if not latest:
        # If no audit ran yet, run an initial probe
        return {
            "overall_status": "HEALTHY",
            "last_audit_at": None,
            "next_scheduled_run": (_utc_now() + timedelta(hours=12)).isoformat(),
            "open_incidents_count": open_incidents_count,
            "components": [],
        }

    results = db.query(HealthCheckResult).filter(HealthCheckResult.audit_id == latest.id).all()
    comp_list = [
        {
            "component": r.component,
            "status": r.status,
            "latency_ms": r.latency_ms,
            "message": r.message,
            "metrics": json.loads(r.metrics_json or "{}"),
        }
        for r in results
    ]

    return {
        "audit_id": latest.id,
        "audit_type": latest.audit_type,
        "overall_status": latest.overall_status,
        "last_audit_at": latest.started_at.isoformat() if latest.started_at else None,
        "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
        "duration_ms": latest.duration_ms,
        "next_scheduled_run": latest.next_scheduled_run.isoformat() if latest.next_scheduled_run else None,
        "open_incidents_count": open_incidents_count,
        "components": comp_list,
    }


def list_recent_audits(db: Session, limit: int = 20) -> list[dict[str, Any]]:
    """Returns recent health audits."""
    audits = db.query(HealthAudit).order_by(desc(HealthAudit.started_at)).limit(limit).all()
    return [
        {
            "id": a.id,
            "audit_type": a.audit_type,
            "overall_status": a.overall_status,
            "started_at": a.started_at.isoformat() if a.started_at else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            "duration_ms": a.duration_ms,
            "summary": json.loads(a.summary_json or "{}"),
            "next_scheduled_run": a.next_scheduled_run.isoformat() if a.next_scheduled_run else None,
        }
        for a in audits
    ]


def list_system_incidents(db: Session, status_filter: str | None = None) -> list[dict[str, Any]]:
    """Returns system incidents with recovery action logs."""
    q = db.query(SystemIncident).order_by(desc(SystemIncident.last_seen_at))
    if status_filter:
        q = q.filter(SystemIncident.status == status_filter)

    incidents = q.limit(50).all()
    out = []
    for inc in incidents:
        recs = [
            {
                "id": r.id,
                "action_name": r.action_name,
                "status": r.status,
                "verification_passed": r.verification_passed,
                "duration_ms": r.duration_ms,
                "executed_at": r.executed_at.isoformat() if r.executed_at else None,
            }
            for r in inc.recovery_logs
        ]
        out.append({
            "id": inc.id,
            "component": inc.component,
            "severity": inc.severity,
            "error_category": inc.error_category,
            "title": inc.title,
            "description": inc.description,
            "status": inc.status,
            "occurrence_count": inc.occurrence_count,
            "first_seen_at": inc.first_seen_at.isoformat() if inc.first_seen_at else None,
            "last_seen_at": inc.last_seen_at.isoformat() if inc.last_seen_at else None,
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
            "resolution_notes": inc.resolution_notes,
            "recovery_logs": recs,
        })
    return out


def resolve_system_incident(db: Session, incident_id: str, user_id: str, notes: str) -> bool:
    """Manually marks an incident as resolved by an authorized administrator."""
    inc = db.get(SystemIncident, incident_id)
    if not inc:
        return False
    inc.status = "RESOLVED"
    inc.resolved_at = _utc_now()
    inc.acknowledged_by = user_id
    inc.resolution_notes = notes
    db.commit()
    return True
