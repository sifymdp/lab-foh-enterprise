"""
Health Guardian - Error Classification Engine
─────────────────────────────────────────────
Classifies operational anomalies and probe failures into structured categories,
assigns severity, and evaluates eligibility for automated recovery.
"""

from __future__ import annotations

from typing import Any


class ErrorCategory:
    TRANSIENT = "TRANSIENT"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    AUTH_ERROR = "AUTH_ERROR"
    DATA_INTEGRITY_VIOLATION = "DATA_INTEGRITY_VIOLATION"
    APPLICATION_DEFECT = "APPLICATION_DEFECT"
    SECURITY_INCIDENT = "SECURITY_INCIDENT"
    UNKNOWN = "UNKNOWN"


class Severity:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def classify_error(component: str, error_message: str, details: dict[str, Any] | None = None) -> dict[str, str]:
    """
    Analyzes error message and context to classify category, severity,
    and recommended action.
    """
    msg = (error_message or "").lower()
    details = details or {}

    category = ErrorCategory.UNKNOWN
    severity = Severity.MEDIUM
    recommended_recovery: str | None = None

    if any(k in msg for k in ["timeout", "timed out", "temporary", "connection reset", "econnreset"]):
        category = ErrorCategory.TRANSIENT
        severity = Severity.MEDIUM
        recommended_recovery = "RECONNECT_CLIENT"

    elif any(k in msg for k in ["database locked", "database is locked", "locked", "busy", "pool limit", "max connections", "too many clients"]):
        category = ErrorCategory.RESOURCE_EXHAUSTION
        severity = Severity.HIGH
        recommended_recovery = "REFRESH_CONNECTION_POOL"

    elif any(k in msg for k in ["refused", "unavailable", "bad gateway", "502", "503", "504", "host unreachable"]):
        category = ErrorCategory.DEPENDENCY_UNAVAILABLE
        severity = Severity.HIGH
        recommended_recovery = "RECONNECT_SERVICE_DEPENDENCY"

    elif any(k in msg for k in ["unauthorized", "forbidden", "invalid token", "401", "403"]):
        category = ErrorCategory.AUTH_ERROR
        severity = Severity.HIGH
        recommended_recovery = None  # Human authorization review required

    elif any(k in msg for k in ["integrity", "foreign key", "null constraint", "duplicate key", "unique constraint"]):
        category = ErrorCategory.DATA_INTEGRITY_VIOLATION
        severity = Severity.HIGH
        recommended_recovery = "RECONCILE_SNAPSHOT_CACHE"

    elif any(k in msg for k in ["permission denied", "quota exceeded", "disk full", "enospc"]):
        category = ErrorCategory.RESOURCE_EXHAUSTION
        severity = Severity.CRITICAL
        recommended_recovery = "CLEANUP_EXPIRED_TEMP_STORAGE"

    elif component == "CCTV_VISION" and any(k in msg for k in ["stream", "rtsp", "capture", "camera offline"]):
        category = ErrorCategory.DEPENDENCY_UNAVAILABLE
        severity = Severity.MEDIUM
        recommended_recovery = "RESTART_CAMERA_STREAM_WORKER"

    elif component == "WEBSOCKETS" and any(k in msg for k in ["lag", "dropped", "dead socket"]):
        category = ErrorCategory.TRANSIENT
        severity = Severity.LOW
        recommended_recovery = "PRUNE_DEAD_SOCKET_CONNECTIONS"

    elif component == "DIGITAL_TWIN" and any(k in msg for k in ["desync", "stale snapshot", "hash mismatch"]):
        category = ErrorCategory.TRANSIENT
        severity = Severity.MEDIUM
        recommended_recovery = "REBUILD_DIGITAL_TWIN_SNAPSHOT"

    elif component == "AI_RAG" and any(k in msg for k in ["rate limit", "429", "model unavailable"]):
        category = ErrorCategory.DEPENDENCY_UNAVAILABLE
        severity = Severity.MEDIUM
        recommended_recovery = "SWITCH_TO_AI_FALLBACK_PROVIDER"

    return {
        "category": category,
        "severity": severity,
        "recommended_recovery": recommended_recovery,
    }
