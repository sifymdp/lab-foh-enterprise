"""Operational Tool Handlers and Tool Registrations for the AI Agent."""

from __future__ import annotations

from typing import Any
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.table import Table
from app.models.reservation import Reservation
from app.models.menu_item import MenuItem
from app.models.vision import Camera, VisionMismatch
from app.services.ai_agent.adapters.sanitized_adapters import (
    get_sanitized_menu_performance,
    get_sanitized_reservations,
    get_sanitized_shift_operations,
    get_sanitized_table_snapshot,
)
from app.services.ai_agent.policy.policy_engine import PolicyClassification
from app.services.ai_agent.tools.registry import RegisteredTool, tool_registry


# ── Read-Only Operational Tool Handlers ─────────────────────────────────────

def _handle_get_table_occupancy(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    tables = get_sanitized_table_snapshot(db, user)
    return {
        "tables": [t.model_dump() for t in tables],
        "occupied_count": sum(1 for t in tables if t.status in ("SEATED", "ACTIVE", "BILLING")),
        "available_count": sum(1 for t in tables if t.status == "AVAILABLE"),
    }


def _handle_get_shift_operations(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    summary = get_sanitized_shift_operations(db, user)
    return summary.model_dump()


def _handle_get_reservations(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    reservations = get_sanitized_reservations(db, user)
    return {"reservations": [r.model_dump() for r in reservations]}


def _handle_get_menu_performance(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    items = get_sanitized_menu_performance(db, user)
    # Sort top items by orders placed
    sorted_items = sorted(items, key=lambda x: x.orders_count, reverse=True)
    return {
        "top_performing": [i.model_dump() for i in sorted_items[:10]],
        "slow_moving": [i.model_dump() for i in sorted_items[-5:] if i.orders_count == 0],
    }


def _handle_get_vision_mismatches(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    q = db.query(VisionMismatch)
    if user.tenant_id:
        q = q.filter(VisionMismatch.tenant_id == user.tenant_id)
    mismatches = q.order_by(VisionMismatch.created_at.desc()).limit(15).all()
    return {
        "mismatches": [
            {
                "id": m.id,
                "table_id": m.table_id,
                "table_number": m.table_number,
                "camera_id": m.camera_id,
                "mismatch_type": m.mismatch_type,
                "digital_status": m.digital_status,
                "observed_state": m.observed_state,
                "confidence": m.confidence,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in mismatches
        ]
    }


def _handle_get_camera_health(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    cameras = db.query(Camera).all()
    return {
        "cameras": [
            {
                "id": c.id,
                "name": c.name,
                "is_active": c.is_active,
                "last_seen_at": c.last_seen_at.isoformat() if c.last_seen_at else None,
            }
            for c in cameras
        ]
    }


def _handle_search_foh_knowledge(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    domain = args.get("domain") or "RESTAURANT_SOP"
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain=domain,
        top_k=3,
        user_id=user.id,
    )
    return {
        "query": query,
        "domain": domain,
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_menu_knowledge(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="MENU",
        top_k=3,
        user_id=user.id,
    )
    return {
        "query": query,
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_operational_history(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="OPERATIONAL_HISTORY",
        top_k=3,
        user_id=user.id,
    )
    return {
        "query": query,
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_vision_history(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="VISION",
        top_k=3,
        user_id=user.id,
        user_role=user.role,
    )
    return {
        "query": query,
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_customer_experience(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="CUSTOMER_EXPERIENCE",
        top_k=3,
        user_id=user.id,
        user_role=user.role,
    )
    return {
        "query": query,
        "domain": "CUSTOMER_EXPERIENCE",
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_kitchen_intelligence(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="KITCHEN",
        top_k=3,
        user_id=user.id,
        user_role=user.role,
    )
    return {
        "query": query,
        "domain": "KITCHEN",
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_table_lifecycle(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    table_number = args.get("table_number")
    filters = {"table_number": str(table_number).lstrip("Tt")} if table_number else None
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="TABLE_LIFECYCLE",
        top_k=3,
        user_id=user.id,
        user_role=user.role,
        entity_filters=filters,
    )
    return {
        "query": query,
        "table_number": table_number,
        "domain": "TABLE_LIFECYCLE",
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_predictive_operations(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="PREDICTIVE_OPERATIONS",
        top_k=3,
        user_id=user.id,
        user_role=user.role,
    )
    return {
        "query": query,
        "domain": "PREDICTIVE_OPERATIONS",
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_manager_decisions(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="MANAGER_DECISIONS",
        top_k=3,
        user_id=user.id,
        user_role=user.role,
    )
    return {
        "query": query,
        "domain": "MANAGER_DECISIONS",
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_maintenance_history(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="MAINTENANCE",
        top_k=3,
        user_id=user.id,
        user_role=user.role,
    )
    return {
        "query": query,
        "domain": "MAINTENANCE",
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_supplier_inventory(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="SUPPLIER_INVENTORY",
        top_k=3,
        user_id=user.id,
        user_role=user.role,
    )
    return {
        "query": query,
        "domain": "SUPPLIER_INVENTORY",
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_compliance_safety(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="COMPLIANCE_SAFETY",
        top_k=3,
        user_id=user.id,
        user_role=user.role,
    )
    return {
        "query": query,
        "domain": "COMPLIANCE_SAFETY",
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_restaurant_layout(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=user.branch_id,
        domain="RESTAURANT_LAYOUT",
        top_k=3,
        user_id=user.id,
        user_role=user.role,
    )
    return {
        "query": query,
        "domain": "RESTAURANT_LAYOUT",
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_search_cross_branch_intelligence(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
    query = str(args.get("query") or "").strip()
    result = hybrid_retrieval_service.retrieve(
        query=query,
        tenant_id=user.tenant_id,
        db=db,
        branch_id=None,
        domain="CROSS_BRANCH",
        top_k=3,
        user_id=user.id,
        user_role=user.role,
    )
    return {
        "query": query,
        "domain": "CROSS_BRANCH",
        "context": result.context_text,
        "citations": [c.model_dump() for c in result.citations],
        "top_confidence": result.top_confidence,
        "insufficient_evidence": result.insufficient_evidence,
    }


def _handle_get_table_turnover_analytics(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services.insights_service import compute_insights
    data = compute_insights(db, user.tenant_id)
    return {
        "occupancy": data.get("occupancy", {}),
        "stages": data.get("stages", []),
        "summary": data.get("summary", []),
        "wait_estimate": data.get("wait_estimate"),
    }


# ── Operational Mutation Tool Handlers ──────────────────────────────────────

def _handle_seat_party(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.schemas.session import SeatGuestIn
    from app.services import session_service

    table_num = str(args.get("table_number") or "").lstrip("Tt").strip()
    table = db.query(Table).filter(Table.number == table_num).first()
    if not table:
        raise ValueError(f"Table '{table_num}' not found.")

    party_size = int(args.get("party_size") or 2)
    guest_name = str(args.get("guest_name") or "Walk-in")

    session = session_service.seat_guest(
        db,
        SeatGuestIn(table_id=table.id, guest_name=guest_name, party_size=party_size),
        host_id=user.id,
    )
    return {
        "ok": True,
        "summary": f"Seated party of {party_size} ({guest_name}) at T{table.number}.",
        "table_number": str(table.number),
        "status": session.status,
    }


def _handle_set_table_status(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services import table_service

    table_num = str(args.get("table_number") or "").lstrip("Tt").strip()
    table = db.query(Table).filter(Table.number == table_num).first()
    if not table:
        raise ValueError(f"Table '{table_num}' not found.")

    target_status = str(args.get("status") or "").upper().strip()

    # CRITICAL SECURITY RULE: The AI cannot set tables to BILLING or PAID
    if target_status in ("BILLING", "PAID"):
        raise ValueError(
            f"Action blocked: Setting table status to '{target_status}' is a financial operation "
            "restricted to the human cashier/waiter workflow."
        )

    if target_status not in ("AVAILABLE", "RESERVED", "SEATED", "ACTIVE", "CLEANING"):
        raise ValueError(f"Invalid target status: '{target_status}'.")

    table_service.patch_table_status(db, table.id, target_status, user.id)
    return {
        "ok": True,
        "summary": f"Table T{table.number} status changed to {target_status}.",
        "table_number": str(table.number),
        "status": target_status,
    }


def _handle_86_menu_item(db: Session, user: User, args: dict[str, Any]) -> dict[str, Any]:
    from app.services import menu_service
    from app.schemas.menu import MenuItemUpdate

    item_name = str(args.get("item_name") or "").strip().lower()
    item = db.query(MenuItem).filter(MenuItem.name.ilike(f"%{item_name}%")).first()
    if not item:
        raise ValueError(f"Menu item '{item_name}' not found.")

    available = bool(args.get("available", False))
    menu_service.update_item(db, item.id, MenuItemUpdate(available=available))
    action_label = "available" if available else "86'd (unavailable)"
    return {
        "ok": True,
        "summary": f"Menu item '{item.name}' is now marked {action_label}.",
        "item_name": item.name,
        "available": available,
    }


# ── Registration Function ───────────────────────────────────────────────────

def register_all_operational_tools() -> None:
    """Registers all approved operational tools with the central ToolRegistry."""

    # 1. get_table_occupancy
    tool_registry.register_tool(
        RegisteredTool(
            name="get_table_occupancy",
            description="Returns current table occupancy, active session durations, and floor availability.",
            parameters_schema={"type": "object", "properties": {}, "required": []},
            permission_required="tables.view",
            risk_level="LOW",
            policy_class=PolicyClassification.READ_ONLY_OPERATIONAL,
            handler=_handle_get_table_occupancy,
        )
    )

    # 2. get_shift_operations
    tool_registry.register_tool(
        RegisteredTool(
            name="get_shift_operations",
            description="Returns daily operational volume: seated parties, total covers, orders placed, active tables.",
            parameters_schema={"type": "object", "properties": {}, "required": []},
            permission_required="insights.view",
            risk_level="LOW",
            policy_class=PolicyClassification.OPERATIONAL_ANALYTICS,
            handler=_handle_get_shift_operations,
        )
    )

    # 3. get_reservations
    tool_registry.register_tool(
        RegisteredTool(
            name="get_reservations",
            description="Lists upcoming reservations with guest name, party size, table, and scheduled time.",
            parameters_schema={"type": "object", "properties": {}, "required": []},
            permission_required="booking.view",
            risk_level="LOW",
            policy_class=PolicyClassification.READ_ONLY_OPERATIONAL,
            handler=_handle_get_reservations,
        )
    )

    # 4. get_menu_performance
    tool_registry.register_tool(
        RegisteredTool(
            name="get_menu_performance",
            description="Analyzes menu velocity: top ordered dishes and slow-moving items based on order frequency.",
            parameters_schema={"type": "object", "properties": {}, "required": []},
            permission_required="menu.view",
            risk_level="LOW",
            policy_class=PolicyClassification.OPERATIONAL_ANALYTICS,
            handler=_handle_get_menu_performance,
        )
    )

    # 5. get_vision_mismatches
    tool_registry.register_tool(
        RegisteredTool(
            name="get_vision_mismatches",
            description="Fetches computer-vision occupancy mismatches where CCTV observations disagree with FOH status.",
            parameters_schema={"type": "object", "properties": {}, "required": []},
            permission_required="camera.view",
            risk_level="LOW",
            policy_class=PolicyClassification.VISION_ANALYSIS,
            handler=_handle_get_vision_mismatches,
        )
    )

    # 6. get_camera_health
    tool_registry.register_tool(
        RegisteredTool(
            name="get_camera_health",
            description="Returns operational health and online/offline status of CCTV vision streams.",
            parameters_schema={"type": "object", "properties": {}, "required": []},
            permission_required="camera.view",
            risk_level="LOW",
            policy_class=PolicyClassification.VISION_ANALYSIS,
            handler=_handle_get_camera_health,
        )
    )

    # 7. seat_party
    tool_registry.register_tool(
        RegisteredTool(
            name="seat_party",
            description="Seats walk-in guests at an available dining table.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "table_number": {"type": "string", "description": "e.g. '3' or 'T3'"},
                    "party_size": {"type": "integer"},
                    "guest_name": {"type": "string"},
                },
                "required": ["table_number", "party_size"],
            },
            permission_required="tables.assign",
            risk_level="MEDIUM",
            policy_class=PolicyClassification.CONTROLLED_OPERATIONAL_ACTION,
            handler=_handle_seat_party,
        )
    )

    # 8. set_table_status
    tool_registry.register_tool(
        RegisteredTool(
            name="set_table_status",
            description="Updates an operational table status (AVAILABLE, SEATED, ACTIVE, CLEANING). Cannot set to BILLING or PAID.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "table_number": {"type": "string", "description": "e.g. '2'"},
                    "status": {"type": "string", "description": "AVAILABLE | SEATED | ACTIVE | CLEANING"},
                },
                "required": ["table_number", "status"],
            },
            permission_required="tables.manage",
            risk_level="MEDIUM",
            policy_class=PolicyClassification.CONTROLLED_OPERATIONAL_ACTION,
            handler=_handle_set_table_status,
        )
    )

    # 9. set_menu_availability
    tool_registry.register_tool(
        RegisteredTool(
            name="set_menu_availability",
            description="Marks a menu item available or 86'd (unavailable). Does NOT modify prices.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "item_name": {"type": "string"},
                    "available": {"type": "boolean"},
                },
                "required": ["item_name", "available"],
            },
            permission_required="menu.manage",
            risk_level="MEDIUM",
            policy_class=PolicyClassification.CONTROLLED_OPERATIONAL_ACTION,
            handler=_handle_86_menu_item,
        )
    )

    # 10. search_foh_knowledge (Restaurant SOP RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_foh_knowledge",
            description="Searches restaurant standard operating procedures (SOPs), opening/closing checklists, cleaning targets, and host protocols.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'table cleaning target SOP' or 'host procedure full capacity'"},
                    "domain": {"type": "string", "description": "RESTAURANT_SOP | STAFF_TRAINING"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.READ_ONLY_OPERATIONAL,
            handler=_handle_search_foh_knowledge,
        )
    )

    # 11. search_menu_knowledge (Menu & Allergen RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_menu_knowledge",
            description="Searches menu culinary descriptions, ingredients, allergens, preparation times, and dietary classifications.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'vegetarian dishes with nuts' or 'dairy free desserts'"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.READ_ONLY_OPERATIONAL,
            handler=_handle_search_menu_knowledge,
        )
    )

    # 12. search_operational_history (Operational Bottleneck RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_operational_history",
            description="Searches historical operational events, dining session turnaround bottlenecks, and prolonged cleaning delay records.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'table turnover delays' or 'extended dining sessions'"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.OPERATIONAL_ANALYTICS,
            handler=_handle_search_operational_history,
        )
    )

    # 13. search_vision_history (CCTV Vision Anomaly RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_vision_history",
            description="Searches historical CCTV camera vision discrepancies, detection instability, and table occupancy mismatches.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'repeated CCTV mismatches on table 12'"},
                },
                "required": ["query"],
            },
            permission_required="camera.view",
            risk_level="LOW",
            policy_class=PolicyClassification.VISION_ANALYSIS,
            handler=_handle_search_vision_history,
        )
    )

    # 14. get_table_turnover_analytics (Deterministic Analytics)
    tool_registry.register_tool(
        RegisteredTool(
            name="get_table_turnover_analytics",
            description="Computes real mathematical kitchen speed, table cleaning turnaround, dining durations, and occupancy bottlenecks.",
            parameters_schema={
                "type": "object",
                "properties": {},
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.OPERATIONAL_ANALYTICS,
            handler=_handle_get_table_turnover_analytics,
        )
    )

    # 15. search_customer_experience (Customer Experience RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_customer_experience",
            description="Searches customer complaints, service feedback, review excerpts, service quality issues, and resolution history.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'most common complaints' or 'service speed feedback'"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.READ_ONLY_OPERATIONAL,
            handler=_handle_search_customer_experience,
        )
    )

    # 16. search_kitchen_intelligence (Kitchen Intelligence RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_kitchen_intelligence",
            description="Searches kitchen prep delays, KDS ticket bottlenecks, station workload, and repeatedly delayed dishes.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'why were orders delayed' or 'station bottlenecks'"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.OPERATIONAL_ANALYTICS,
            handler=_handle_search_kitchen_intelligence,
        )
    )

    # 17. search_table_lifecycle (Table Lifecycle RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_table_lifecycle",
            description="Searches operational lifecycle history, seating events, occupancy turnaround, and cleaning duration for individual tables.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'what problems has Table 12 had'"},
                    "table_number": {"type": "string", "description": "Optional table number e.g. '12' or '8'"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.READ_ONLY_OPERATIONAL,
            handler=_handle_search_table_lifecycle,
        )
    )

    # 18. search_predictive_operations (Predictive Operations RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_predictive_operations",
            description="Retrieves forward-looking shift forecasts, rush projections, table demand expectations, and bottleneck predictions.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'what should we prepare for tonight'"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.OPERATIONAL_ANALYTICS,
            handler=_handle_search_predictive_operations,
        )
    )

    # 19. search_manager_decisions (Manager Decision Memory RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_manager_decisions",
            description="Searches organizational memory of historical operational incidents, manager decisions, and verified resolution outcomes.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'have we solved kitchen overload before'"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.OPERATIONAL_ANALYTICS,
            handler=_handle_search_manager_decisions,
        )
    )

    # 20. search_maintenance_history (Maintenance RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_maintenance_history",
            description="Searches equipment troubleshooting, KDS terminal glitches, POS receipt printer jams, and camera stream reconnects.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'KDS screen freeze' or 'printer jam'"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.READ_ONLY_OPERATIONAL,
            handler=_handle_search_maintenance_history,
        )
    )

    # 21. search_supplier_inventory (Supplier & Inventory RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_supplier_inventory",
            description="Searches supplier profiles, delivery schedules, ingredient specifications, and out-of-stock mitigation procedures.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'who supplies seafood' or 'emergency ingredient sourcing'"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.READ_ONLY_OPERATIONAL,
            handler=_handle_search_supplier_inventory,
        )
    )

    # 22. search_compliance_safety (Compliance & Safety RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_compliance_safety",
            description="Searches food hygiene standards, HACCP protocols, severe allergen containment, and emergency safety guidelines.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'allergen procedure' or 'closing hygiene checklist'"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.READ_ONLY_OPERATIONAL,
            handler=_handle_search_compliance_safety,
        )
    )

    # 23. search_restaurant_layout (Restaurant Layout RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_restaurant_layout",
            description="Searches floor plan revisions, table movements, rotation adjustments, and CCTV camera ROI calibrations.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'why was Table 18 moved' or 'table layout changes'"},
                },
                "required": ["query"],
            },
            permission_required=None,
            risk_level="LOW",
            policy_class=PolicyClassification.READ_ONLY_OPERATIONAL,
            handler=_handle_search_restaurant_layout,
        )
    )

    # 24. search_cross_branch_intelligence (Cross-Branch RAG)
    tool_registry.register_tool(
        RegisteredTool(
            name="search_cross_branch_intelligence",
            description="Compares operational turnover, kitchen pacing, and shared patterns across multiple branches for organization leaders.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "e.g. 'compare turnover between branches'"},
                },
                "required": ["query"],
            },
            permission_required="revenue.view_all",
            risk_level="LOW",
            policy_class=PolicyClassification.OPERATIONAL_ANALYTICS,
            handler=_handle_search_cross_branch_intelligence,
        )
    )


# Register all tools at import time
register_all_operational_tools()
