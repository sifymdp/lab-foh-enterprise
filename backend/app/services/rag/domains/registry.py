"""
Unified Enterprise RAG Domain Registry
────────────────────────────────────────
Coordinates master metadata, security classifications, schema specifications,
and unified ingestion/retrieval policies across all 17 FOH knowledge domains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class DomainDefinition:
    """Specification of a distinct knowledge domain within the Enterprise RAG pipeline."""
    key: str
    display_name: str
    description: str
    source_types: list[str]
    required_permission: str | None = None
    allow_cross_branch: bool = False
    requires_forecast_labeling: bool = False
    forbidden_content_patterns: list[str] = field(default_factory=list)
    query_keywords: list[str] = field(default_factory=list)


@dataclass
class RAGMetadata:
    """
    Standardized metadata payload attached to every ingested document and vector chunk.
    Enforces tenant boundaries, entity referencing, and security visibility.
    """
    organization_id: str
    domain: str
    source_type: str
    source_id: str
    branch_id: str | None = None
    timestamp: str = field(default_factory=_utc_now_iso)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    version: int = 1
    status: str = "ACTIVE"
    visibility: str = "INTERNAL"
    # Entity-specific identifiers
    table_id: str | None = None
    camera_id: str | None = None
    station_id: str | None = None
    supplier_id: str | None = None
    incident_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "organization_id": self.organization_id,
            "branch_id": self.branch_id,
            "domain": self.domain,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "timestamp": self.timestamp,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "status": self.status,
            "visibility": self.visibility,
            "table_id": self.table_id,
            "camera_id": self.camera_id,
            "station_id": self.station_id,
            "supplier_id": self.supplier_id,
            "incident_id": self.incident_id,
        }
        if self.extra:
            d.update(self.extra)
        return d


class RAGDomainRegistry:
    """Master registry of all Enterprise RAG domains."""

    def __init__(self) -> None:
        self._domains: dict[str, DomainDefinition] = {}
        self._register_default_domains()

    def register(self, definition: DomainDefinition) -> None:
        norm_key = definition.key.upper()
        self._domains[norm_key] = definition

    def get(self, key: str) -> DomainDefinition | None:
        return self._domains.get(key.upper())

    def list_all(self) -> list[DomainDefinition]:
        return list(self._domains.values())

    def normalize_key(self, key: str) -> str:
        k = key.upper().strip()
        aliases = {
            "KNOWLEDGE": "RESTAURANT_SOP",
            "SOP": "RESTAURANT_SOP",
            "SOPS": "RESTAURANT_SOP",
            "OPERATIONS": "OPERATIONAL_HISTORY",
            "OPERATION": "OPERATIONAL_HISTORY",
            "KITCHEN_INTELLIGENCE": "KITCHEN",
            "KITCHEN_DELAYS": "KITCHEN",
            "CUSTOMER": "CUSTOMER_EXPERIENCE",
            "CUSTOMERS": "CUSTOMER_EXPERIENCE",
            "COMPLAINT": "CUSTOMER_EXPERIENCE",
            "COMPLAINTS": "CUSTOMER_EXPERIENCE",
            "FEEDBACK": "CUSTOMER_EXPERIENCE",
            "TABLE": "TABLE_LIFECYCLE",
            "TABLES": "TABLE_LIFECYCLE",
            "TABLE_PERFORMANCE": "TABLE_LIFECYCLE",
            "PREDICTIONS": "PREDICTIVE_OPERATIONS",
            "PREDICTION": "PREDICTIVE_OPERATIONS",
            "FORECAST": "PREDICTIVE_OPERATIONS",
            "RUSH_FORECAST": "PREDICTIVE_OPERATIONS",
            "MANAGER": "MANAGER_DECISIONS",
            "MANAGER_DECISION": "MANAGER_DECISIONS",
            "DECISIONS": "MANAGER_DECISIONS",
            "EQUIPMENT": "MAINTENANCE",
            "REPAIRS": "MAINTENANCE",
            "LAYOUT": "RESTAURANT_LAYOUT",
            "FLOOR_PLAN": "RESTAURANT_LAYOUT",
            "INVENTORY": "SUPPLIER_INVENTORY",
            "SUPPLIER": "SUPPLIER_INVENTORY",
            "SUPPLIERS": "SUPPLIER_INVENTORY",
            "SAFETY": "COMPLIANCE_SAFETY",
            "COMPLIANCE": "COMPLIANCE_SAFETY",
            "CROSSBRANCH": "CROSS_BRANCH",
            "CROSS_BRANCHES": "CROSS_BRANCH",
        }
        return aliases.get(k, k)

    def _register_default_domains(self) -> None:
        # 1. Base Existing Domains
        self.register(
            DomainDefinition(
                key="RESTAURANT_SOP",
                display_name="Restaurant Operating SOPs",
                description="Standard operating procedures, greeting rules, seating rules, and waitlist protocols.",
                source_types=["manual", "policy", "training_guide"],
                query_keywords=["sop", "procedure", "greeting", "protocol", "policy", "rules"],
            )
        )
        self.register(
            DomainDefinition(
                key="MENU",
                display_name="Menu Culinary & Allergen Knowledge",
                description="Menu items, ingredients, flavor profiles, dietary flags, and preparation timings.",
                source_types=["menu_item", "recipe", "allergen_matrix"],
                query_keywords=["menu", "dish", "recipe", "allergen", "dietary", "flavor", "ingredient"],
            )
        )
        self.register(
            DomainDefinition(
                key="OPERATIONAL_HISTORY",
                display_name="Operational Bottlenecks & Shift History",
                description="Dining session durations, cleaning turnaround times, and shift bottleneck records.",
                source_types=["shift_summary", "turnover_record", "session_log"],
                query_keywords=["turnover", "bottleneck", "delay", "dining duration", "cleaning delay"],
            )
        )
        self.register(
            DomainDefinition(
                key="INCIDENTS",
                display_name="Operational Incident Records",
                description="Operational disruptions, walkout suspect logs, and critical dining escalations.",
                source_types=["incident_report", "walkout_log", "dispute_record"],
                query_keywords=["incident", "walkout", "dispute", "escalation", "emergency"],
            )
        )
        self.register(
            DomainDefinition(
                key="VISION",
                display_name="CCTV Computer Vision Intelligence",
                description="CCTV table occupancy detections, YOLO bounding boxes, and camera discrepancy events.",
                source_types=["cctv_observation", "mismatch_event", "camera_health"],
                required_permission="camera.view",
                query_keywords=["cctv", "camera", "vision", "mismatch", "occupancy detection", "yolo"],
            )
        )
        self.register(
            DomainDefinition(
                key="STAFF",
                display_name="Staff Section & Shift Allocation",
                description="Staff station assignments, section boundaries, and floor coverage guidelines.",
                source_types=["section_assignment", "shift_roster", "server_station"],
                query_keywords=["staff", "server", "busser", "section assignment", "station"],
            )
        )
        self.register(
            DomainDefinition(
                key="RESERVATIONS",
                display_name="Reservation & Booking Policies",
                description="Booking grace periods, no-show release standards, and VIP allocation policies.",
                source_types=["reservation_policy", "grace_period", "booking_rules"],
                query_keywords=["reservation", "booking", "grace period", "no-show", "hold time"],
            )
        )

        # 2. Advanced Specialized Domains (10 Required)
        # Domain 1: CUSTOMER_EXPERIENCE
        self.register(
            DomainDefinition(
                key="CUSTOMER_EXPERIENCE",
                display_name="Customer Experience & Feedback",
                description="Customer complaints, service feedback, review excerpts, service quality issues, and resolutions.",
                source_types=["complaint", "feedback", "review", "service_issue", "resolution_history"],
                query_keywords=[
                    "complaint", "feedback", "review", "customer issue", "service problem",
                    "guest dissatisfaction", "complaining", "service quality"
                ],
            )
        )

        # Domain 2: KITCHEN
        self.register(
            DomainDefinition(
                key="KITCHEN",
                display_name="Kitchen & KDS Operations Intelligence",
                description="Kitchen Display System (KDS) delays, preparation times, station bottlenecks, and delayed dishes.",
                source_types=["kds_delay", "prep_time", "station_bottleneck", "delayed_dish", "kitchen_incident"],
                query_keywords=[
                    "kitchen delay", "kds", "cooking time", "station bottleneck", "grill",
                    "saute", "delayed orders", "kitchen problems", "prep delay"
                ],
            )
        )

        # Domain 3: TABLE_LIFECYCLE
        self.register(
            DomainDefinition(
                key="TABLE_LIFECYCLE",
                display_name="Table Historical Lifecycle & Events",
                description="Lifecycle tracking for each dining table (Available -> Reserved -> Seated -> Active -> Cleaning). Non-financial operational events.",
                source_types=["table_status_change", "seating_event", "cleaning_event", "mismatch_log"],
                forbidden_content_patterns=["total price", "bill amount", "credit card", "payment method", "stripe"],
                query_keywords=[
                    "table lifecycle", "table performance", "status history", "cleaning duration",
                    "seating history", "table 12", "table 8", "table problems"
                ],
            )
        )

        # Domain 4: PREDICTIVE_OPERATIONS
        self.register(
            DomainDefinition(
                key="PREDICTIVE_OPERATIONS",
                display_name="Predictive Operations & Demand Forecasts",
                description="Forward-looking operational expectations, rush forecasts, and staffing bottleneck predictions based on historical patterns.",
                source_types=["demand_forecast", "rush_projection", "bottleneck_prediction"],
                requires_forecast_labeling=True,
                query_keywords=[
                    "prepare for tonight", "busiest period", "likely demand", "peak hours",
                    "predict", "forecast", "what should we prepare", "rush prediction"
                ],
            )
        )

        # Domain 5: MANAGER_DECISIONS
        self.register(
            DomainDefinition(
                key="MANAGER_DECISIONS",
                display_name="Manager Decision & Resolution Memory",
                description="Organizational memory of operational problems, decisions taken, actions implemented, and verified outcomes.",
                source_types=["problem_solution", "shift_intervention", "manager_decision", "outcome_log"],
                query_keywords=[
                    "solved before", "manager decision", "previous solution", "action taken",
                    "similar incident", "how did we resolve", "what did the manager do"
                ],
            )
        )

        # Domain 6: MAINTENANCE
        self.register(
            DomainDefinition(
                key="MAINTENANCE",
                display_name="System & Equipment Maintenance",
                description="Hardware, KDS, POS, receipt printer, camera, network, and equipment repair history and troubleshooting steps.",
                source_types=["equipment_failure", "troubleshooting_guide", "hardware_repair", "incident_ticket"],
                forbidden_content_patterns=["password", "secret", "api_key", "credential", "private_key"],
                query_keywords=[
                    "maintenance", "printer problem", "kds issue", "camera offline",
                    "pos glitch", "network failure", "equipment failure", "repair"
                ],
            )
        )

        # Domain 7: SUPPLIER_INVENTORY
        self.register(
            DomainDefinition(
                key="SUPPLIER_INVENTORY",
                display_name="Supplier, Ingredient & Procurement Policies",
                description="Supplier relationships, ingredient specifications, delivery lead times, and procurement policies. Contextual inventory knowledge.",
                source_types=["supplier_profile", "procurement_policy", "delivery_history", "ingredient_spec"],
                query_keywords=[
                    "supplier", "ingredient source", "procurement", "stock issue",
                    "delivery history", "who provides", "out of stock policy"
                ],
            )
        )

        # Domain 8: COMPLIANCE_SAFETY
        self.register(
            DomainDefinition(
                key="COMPLIANCE_SAFETY",
                display_name="Food Safety, Hygiene & Regulatory Compliance",
                description="HACCP food safety standards, kitchen hygiene checklists, allergen containment, staff safety, and emergency protocols.",
                source_types=["food_safety", "hygiene_checklist", "allergen_protocol", "emergency_policy"],
                query_keywords=[
                    "allergen procedure", "food safety", "hygiene checklist", "closing checklist",
                    "safety incident", "haccp", "health inspection", "emergency procedure"
                ],
            )
        )

        # Domain 9: RESTAURANT_LAYOUT
        self.register(
            DomainDefinition(
                key="RESTAURANT_LAYOUT",
                display_name="Floor Plan, Table Positions & Camera ROI",
                description="Historical record of floor-plan versions, table repositioning, resizing, rotation adjustments, and camera ROI changes.",
                source_types=["floor_plan_version", "table_movement", "roi_calibration", "layout_change"],
                query_keywords=[
                    "floor plan", "table moved", "table position", "layout change",
                    "camera roi", "rotation", "table added", "table removed"
                ],
            )
        )

        # Domain 10: CROSS_BRANCH
        self.register(
            DomainDefinition(
                key="CROSS_BRANCH",
                display_name="Cross-Branch Operational Comparisons",
                description="Comparative operational performance, benchmark metrics, and shared operational patterns across branches for organization leaders.",
                source_types=["branch_comparison", "multi_branch_benchmark", "cross_location_analysis"],
                required_permission="organization.view",
                allow_cross_branch=True,
                query_keywords=[
                    "cross branch", "compare branches", "which branch", "branch a vs branch b",
                    "across locations", "best table turnover across branches"
                ],
            )
        )


# Global singleton instance
domain_registry = RAGDomainRegistry()
