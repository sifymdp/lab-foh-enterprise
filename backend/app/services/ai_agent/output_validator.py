"""Output Validator and Action Schema Normalizer.

Ensures LLM output conforms to strict structured action allowlists
and eliminates any attempt at arbitrary client-side code execution or unauthorized routes.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

ALLOWED_ACTION_TYPES = {
    "NAVIGATE",
    "SET_FILTER",
    "SET_DATE_RANGE",
    "SET_BRANCH",
    "FOCUS_TABLES",
    "FOCUS_METRIC",
    "HIGHLIGHT_ANOMALY",
    "CONFIRM",
}

ALLOWED_ROUTES = {
    "/dashboard",
    "/floor",
    "/sessions",
    "/reservations",
    "/menu",
    "/kitchen",
    "/kds",
    "/insights",
    "/ai-alerts",
    "/camera-setup",
    "/booking",
    "/revenue",
    "/reports",
}

FORBIDDEN_ROUTE_SUBSTRINGS = {
    "billing",
    "bills",
    "payments",
    "shifts",
    "refunds",
    "roles",
    "overrides",
}


class UIAction(BaseModel):
    type: str
    route: str | None = None
    filter: dict[str, Any] | None = None
    table_ids: list[str] | None = None
    metric: str | None = None
    date_range: dict[str, str] | None = None
    confirm_token: str | None = None


class AgentResponseContent(BaseModel):
    summary: str
    details: str | None = None
    facts: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)


class StructuredAgentOutput(BaseModel):
    intent: str
    classification: str
    actions: list[UIAction] = Field(default_factory=list)
    response: AgentResponseContent
    citations: list[dict[str, Any]] = Field(default_factory=list)


def validate_and_filter_actions(actions_raw: list[dict[str, Any]]) -> list[UIAction]:
    """Validates and filters raw actions returned by model/heuristics.

    Drops any prohibited or unauthorized actions.
    """
    valid_actions: list[UIAction] = []
    for raw in actions_raw:
        action_type = str(raw.get("type", "")).upper().strip()
        if action_type not in ALLOWED_ACTION_TYPES:
            continue

        route = raw.get("route")
        if route:
            # Normalize route
            clean_route = "/" + route.strip().lstrip("/")
            # Check route against allowlist
            if clean_route not in ALLOWED_ROUTES:
                continue
            # Double check against forbidden keywords
            if any(forbidden in clean_route for forbidden in FORBIDDEN_ROUTE_SUBSTRINGS):
                continue
            route = clean_route

        valid_actions.append(
            UIAction(
                type=action_type,
                route=route,
                filter=raw.get("filter") if isinstance(raw.get("filter"), dict) else None,
                table_ids=[str(t) for t in raw.get("table_ids", [])] if isinstance(raw.get("table_ids"), list) else None,
                metric=raw.get("metric"),
                date_range=raw.get("date_range"),
                confirm_token=raw.get("confirm_token"),
            )
        )
    return valid_actions
