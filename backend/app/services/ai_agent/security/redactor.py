"""L6 Persistence & Audit Redactor.

Ensures that logs, conversation memory, and audit rows never retain
sensitive or customer confidential parameters.
"""

from __future__ import annotations

import json
from typing import Any

SENSITIVE_PARAM_KEYS = {
    "password",
    "secret",
    "token",
    "auth",
    "card",
    "cvv",
    "otp",
    "credit_card",
    "customer_email",
    "email",
    "phone",
}


def redact_dictionary(data: dict[str, Any]) -> dict[str, Any]:
    """Returns a copy of data with sensitive tokens replaced with [REDACTED]."""
    cleaned: dict[str, Any] = {}
    for k, v in data.items():
        k_lower = str(k).lower().strip()
        if k_lower in SENSITIVE_PARAM_KEYS:
            cleaned[k] = "[REDACTED]"
        elif isinstance(v, dict):
            cleaned[k] = redact_dictionary(v)
        elif isinstance(v, list):
            cleaned[k] = [
                redact_dictionary(x) if isinstance(x, dict) else x
                for x in v
            ]
        else:
            cleaned[k] = v
    return cleaned


def safe_json_dumps(data: Any) -> str:
    """Serializes data safely after redacting sensitive tokens."""
    if isinstance(data, dict):
        redacted = redact_dictionary(data)
    else:
        redacted = data
    try:
        return json.dumps(redacted, default=str)
    except Exception:
        return "{}"
