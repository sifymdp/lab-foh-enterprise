"""AI Agent Orchestrator.

Central engine coordinating Intent, Financial Firewall, Policy Engine,
OpenRouter multi-model tool loop, Deterministic fallback, Output Validation,
and Audit Logging.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.permissions import (
    PERM_AI_ASSISTANT_USE,
    has_user_permission,
    is_authorized_for_financial_reporting,
)
from app.models.user import User
from app.services.ai_agent.audit import record_ai_audit
from app.services.ai_agent.context.conversation_store import conversation_store
from app.services.ai_agent.context.date_resolver import (
    extract_comparison_periods,
    resolve_date_expression,
)
from app.services.ai_agent.llm.model_router import model_router
from app.services.ai_agent.output_validator import (
    AgentResponseContent,
    StructuredAgentOutput,
    UIAction,
    validate_and_filter_actions,
)
from app.services.ai_agent.policy.policy_engine import (
    PolicyClassification,
    policy_engine,
)
from app.services.ai_agent.security.egress_scanner import (
    EgressLeakDetected,
    sanitize_response_text,
    scan_payload_for_financial_leak,
)
from app.services.ai_agent.security.financial_firewall import (
    SAFE_FINANCIAL_REFUSAL_MESSAGE,
    SAFE_FINANCIAL_RESTRICTED_MESSAGE,
    SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE,
    is_financial_query,
    is_financial_reporting_query,
    is_financial_transaction_action,
)
from app.services.ai_agent.tools.registry import tool_registry
from app.services.financial_reporting_service import financial_reporting_service

logger = logging.getLogger(__name__)


class AIOrchestrator:
    """Production-grade AI Orchestrator with complete financial isolation."""

    def process_request(
        self,
        db: Session,
        user: User,
        query: str,
        conversation_id: str | None = None,
        app_context: dict[str, Any] | None = None,
    ) -> StructuredAgentOutput:
        start_time = time.time()
        conv_id = conversation_id or f"conv_{user.id}"

        # ── 1. RBAC Check for AI Access ──
        if not has_user_permission(db, user, PERM_AI_ASSISTANT_USE):
            record_ai_audit(
                db=db,
                user_id=user.id,
                tenant_id=user.tenant_id,
                branch_id=user.branch_id,
                conversation_id=conv_id,
                classification="SECURITY_ACTION",
                intent="unauthorized_ai_access",
                permission_result="DENIED",
                policy_result="BLOCKED",
                execution_result="BLOCKED",
                blocked_reason="Missing permission: ai.assistant.use",
                latency_ms=(time.time() - start_time) * 1000,
            )
            return StructuredAgentOutput(
                intent="access_denied",
                classification="SECURITY_ACTION",
                actions=[],
                response=AgentResponseContent(
                    summary="Access Denied: You do not have permission to use the AI Assistant.",
                ),
            )

        # ── 2. L1 Financial Firewall Checks ──
        # A. Financial Transaction / Mutation Actions (UNCONDITIONALLY BLOCKED FOR ALL USERS)
        mutation_check = is_financial_transaction_action(query)
        if mutation_check.blocked:
            record_ai_audit(
                db=db,
                user_id=user.id,
                tenant_id=user.tenant_id,
                branch_id=user.branch_id,
                conversation_id=conv_id,
                classification="FINANCIAL_TRANSACTION_ACTION",
                intent="financial_mutation_blocked",
                permission_result="DENIED",
                policy_result="BLOCKED",
                execution_result="BLOCKED",
                blocked_reason=mutation_check.reason,
                latency_ms=(time.time() - start_time) * 1000,
            )
            return StructuredAgentOutput(
                intent="financial_mutation_blocked",
                classification="FINANCIAL_TRANSACTION_ACTION",
                actions=[],
                response=AgentResponseContent(
                    summary=SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE,
                ),
            )

        # B. Read-Only Financial Reporting (OWNER-ONLY ACCESS)
        reporting_check = is_financial_reporting_query(query)
        if reporting_check.is_reporting_query:
            if not is_authorized_for_financial_reporting(user, db):
                record_ai_audit(
                    db=db,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    branch_id=user.branch_id,
                    conversation_id=conv_id,
                    classification="FINANCIAL_REPORT",
                    intent="financial_reporting_unauthorized",
                    permission_result="DENIED",
                    policy_result="BLOCKED",
                    execution_result="BLOCKED",
                    blocked_reason="Financial reporting is restricted to authorized Owner accounts.",
                    latency_ms=(time.time() - start_time) * 1000,
                )
                return StructuredAgentOutput(
                    intent="financial_reporting_unauthorized",
                    classification="FINANCIAL_REPORT",
                    actions=[],
                    response=AgentResponseContent(
                        summary=SAFE_FINANCIAL_RESTRICTED_MESSAGE,
                    ),
                )

            # Authorized Owner: Handle Read-Only Financial Reporting
            return self._handle_owner_financial_reporting(
                db=db,
                user=user,
                query=query,
                conv_id=conv_id,
                start_time=start_time,
            )

        # ── 3. Date & Operational Context Resolution ──
        resolved_date = resolve_date_expression(query)
        conv_ctx = conversation_store.get_or_create(conv_id)

        # ── 4. Deterministic Operational Fast-Path & Fallback Engine ──
        # If cloud model is not configured, or for quick navigation/occupancy queries
        provider = model_router.get_active_provider()
        provider_name = provider.get_provider_name()

        # Try LLM Tool Loop if configured
        actions_list: list[dict[str, Any]] = []
        final_text = ""

        # Build ground system prompt with strictly operational information
        from app.services.ai_agent.adapters.sanitized_adapters import (
            get_sanitized_table_snapshot,
        )
        table_snapshots = get_sanitized_table_snapshot(db, user)
        occupied_count = sum(1 for t in table_snapshots if t.status in ("SEATED", "ACTIVE", "BILLING"))
        available_count = sum(1 for t in table_snapshots if t.status == "AVAILABLE")
        cleaning_count = sum(1 for t in table_snapshots if t.status == "CLEANING")

        snapshot_str = (
            f"Active floor status: {len(table_snapshots)} total tables. "
            f"{occupied_count} occupied, {available_count} available, {cleaning_count} in cleaning. "
            f"User: {user.name} ({user.role})."
        )
        if resolved_date:
            snapshot_str += f" Interpreted date range: {resolved_date.label}."

        system_prompt = (
            "You are the FOH Operational AI Assistant. You assist restaurant owners and managers with "
            "floor operations, table occupancy, wait times, kitchen bottlenecks, menu availability, SOPs, and CCTV vision.\n"
            "STRICT RULES:\n"
            "1. You have ZERO access to revenue, bills, payments, taxes, or pricing. Never attempt to infer money values.\n"
            "2. Ground all numerical facts in tool outputs. If asked about restaurant SOPs, procedures, or policies, call search_foh_knowledge.\n"
            "3. If asked about ingredients, allergens, or dishes, call search_menu_knowledge.\n"
            "4. If asked about table turnover, delays, or bottlenecks, call get_table_turnover_analytics and search_operational_history.\n"
            "5. If asked about CCTV anomalies, call search_vision_history.\n"
            "6. When answering analytical or operational questions, structure clearly into:\n"
            "   - FACT: Numbers and live status directly from tools.\n"
            "   - OBSERVATION: Signals from camera vision or operational logs.\n"
            "   - INFERENCE: Root causes grounded in SOP targets or historical data.\n"
            "   - RECOMMENDATION: Specific action steps for floor/kitchen staff.\n"
            "7. If navigating, specify the target page (e.g. /floor, /reservations, /menu, /kitchen, /kds, /camera-setup, /insights).\n\n"
            f"CURRENT OPERATIONAL STATE:\n{snapshot_str}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
        ]
        # Append short-term conversation context
        for past in conv_ctx.recent_messages[-6:]:
            messages.append(past)
        messages.append({"role": "user", "content": query})

        # Scan outbound messages before egress
        try:
            scan_payload_for_financial_leak(messages)
        except EgressLeakDetected as err:
            logger.error("Outbound leak prevented by Egress Scanner: %s", err)
            return StructuredAgentOutput(
                intent="leak_prevented",
                classification="FINANCIAL_READ",
                actions=[],
                response=AgentResponseContent(summary=SAFE_FINANCIAL_REFUSAL_MESSAGE),
            )

        tool_specs = tool_registry.get_openai_tool_specs()
        model_used = "none"
        collected_citations: list[dict[str, Any]] = []

        # Execute Multi-Round Tool Calling (Max 4 rounds)
        for _ in range(4):
            reply_msg, model_used, provider_name = model_router.chat_with_fallback(
                messages=messages,
                tools=tool_specs,
                role="primary",
            )

            if not reply_msg:
                # LLM unavailable -> use deterministic operational rules
                final_text, actions_list, det_cits = self._deterministic_operational_engine(
                    db, user, query, table_snapshots
                )
                collected_citations.extend(det_cits)
                break

            tool_calls = reply_msg.get("tool_calls")
            if not tool_calls:
                final_text = str(reply_msg.get("content") or "").strip()
                break

            messages.append(reply_msg)
            for tc in tool_calls:
                fn = tc.get("function", {})
                t_name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                parsed_args = {}
                try:
                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    pass

                # Execute through controlled tool registry
                t_res, ok, err_msg = tool_registry.execute_tool(db, user, t_name, parsed_args)

                # Collect citations if returned by RAG tools
                if isinstance(t_res, dict) and "citations" in t_res:
                    for cit in t_res["citations"]:
                        if cit not in collected_citations:
                            collected_citations.append(cit)

                # Record audit
                record_ai_audit(
                    db=db,
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    branch_id=user.branch_id,
                    conversation_id=conv_id,
                    classification="OPERATIONAL_ANALYTICS",
                    intent=t_name,
                    tool=t_name,
                    params=parsed_args,
                    permission_result="ALLOWED" if ok else "DENIED",
                    policy_result="ALLOWED" if ok else "BLOCKED",
                    execution_result="SUCCESS" if ok else "FAILED",
                    blocked_reason=err_msg,
                    model_used=model_used,
                    provider_used=provider_name,
                )

                # If this was an operational action, translate to UI action
                if t_name == "seat_party" and ok:
                    actions_list.append({"type": "NAVIGATE", "route": "/floor"})
                    actions_list.append({"type": "SET_FILTER", "filter": {"status": "occupied"}})
                elif t_name == "get_table_occupancy":
                    actions_list.append({"type": "NAVIGATE", "route": "/floor"})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": json.dumps(t_res),
                })

        # Sanitize final text
        clean_text = sanitize_response_text(final_text)

        # ── 5. Navigation & Contextual UI Actions Heuristics ──
        q_lower = query.lower()
        cit_domains = {c.get("domain") for c in collected_citations if isinstance(c, dict)}

        if re.search(r"\b(?:menu|dishes|food\s+items|recipes?|ingredients?|supplier)\b", q_lower) or "SUPPLIER_INVENTORY" in cit_domains or "MENU" in cit_domains:
            if not any(a.get("route") == "/menu" for a in actions_list):
                actions_list.append({"type": "NAVIGATE", "route": "/menu"})

        if re.search(r"\b(?:floor|busy\s+tables|occupied\s+tables|who\s+is\s+seated|table\s+\d+|table\s+moved|layout)\b", q_lower) or "TABLE_LIFECYCLE" in cit_domains or "RESTAURANT_LAYOUT" in cit_domains:
            if not any(a.get("route") == "/floor" for a in actions_list):
                actions_list.append({"type": "NAVIGATE", "route": "/floor"})
                if "occupied" in q_lower or "busy" in q_lower:
                    actions_list.append({"type": "SET_FILTER", "filter": {"status": "occupied"}})

        if re.search(r"\b(?:reservations?|upcoming\s+bookings?|prepare\s+for\s+tonight|tonight|forecast|rush\s+projection|projections?)\b", q_lower) or "PREDICTIVE_OPERATIONS" in cit_domains:
            if not any(a.get("route") == "/reservations" for a in actions_list):
                actions_list.append({"type": "NAVIGATE", "route": "/reservations"})

        if re.search(r"\b(?:kitchen|kds|bottlenecks?|delayed\s+orders?|orders?\s+delayed|cooking\s+time|station)\b", q_lower) or "KITCHEN" in cit_domains:
            if not any(a.get("route") == "/kds" for a in actions_list):
                actions_list.append({"type": "NAVIGATE", "route": "/kds"})

        if re.search(r"\b(?:turnover|turnaround|insights?|bottlenecks?|delays?|complaint|complaints|complaining|feedback|sentiment)\b", q_lower) or "CUSTOMER_EXPERIENCE" in cit_domains:
            if not any(a.get("route") == "/insights" for a in actions_list):
                actions_list.append({"type": "NAVIGATE", "route": "/insights"})

        if re.search(r"\b(?:cctv|vision|cameras?|mismatch(?:es)?|maintenance|screen\s+freeze|hardware)\b", q_lower) or "VISION" in cit_domains or "MAINTENANCE" in cit_domains:
            if not any(a.get("route") == "/camera-setup" for a in actions_list):
                actions_list.append({"type": "NAVIGATE", "route": "/camera-setup"})

        # Validate actions through allowlist
        validated_actions = validate_and_filter_actions(actions_list)

        # Update conversation context
        conversation_store.update_context(
            conv_id=conv_id,
            intent="operational_inquiry",
            new_user_msg=query,
            new_assistant_msg=clean_text,
        )

        # Record top-level audit event
        record_ai_audit(
            db=db,
            user_id=user.id,
            tenant_id=user.tenant_id,
            branch_id=user.branch_id,
            conversation_id=conv_id,
            classification="OPERATIONAL_ANALYTICS",
            intent="operational_inquiry",
            model_used=model_used,
            provider_used=provider_name,
            latency_ms=(time.time() - start_time) * 1000,
        )

        return StructuredAgentOutput(
            intent="operational_assistance",
            classification="OPERATIONAL_ANALYTICS",
            actions=validated_actions,
            citations=collected_citations,
            response=AgentResponseContent(
                summary=clean_text or "Operational inquiry completed.",
                citations=collected_citations,
            ),
        )

    def _handle_owner_financial_reporting(
        self,
        db: Session,
        user: User,
        query: str,
        conv_id: str,
        start_time: float,
    ) -> StructuredAgentOutput:
        """Executes authorized read-only financial reporting for restaurant Owners."""
        from datetime import datetime, timezone
        from app.services.ai_agent.security.egress_scanner import scan_payload_for_financial_leak

        # 1. Period Comparison (e.g. "Compare September revenue with August")
        comparison = extract_comparison_periods(query)
        if comparison:
            res = financial_reporting_service.compare_revenue(
                db=db,
                tenant_id=user.tenant_id,
                branch_id=user.branch_id,
                period_a=comparison.period_a,
                period_b=comparison.period_b,
                label_a=comparison.label_a,
                label_b=comparison.label_b,
            )
            pct_sign = "+" if res.percentage_change >= 0 else ""
            summary_msg = (
                f"📊 **Revenue Comparison: {res.period_a_label} vs {res.period_b_label}**\n\n"
                f"• **{res.period_a_label}**: ₹{res.period_a_revenue:,.2f}\n"
                f"• **{res.period_b_label}**: ₹{res.period_b_revenue:,.2f}\n"
                f"• **Variance**: ₹{res.absolute_change:,.2f} ({pct_sign}{res.percentage_change}% - Trend: {res.trend})\n\n"
                f"Opening the Revenue Dashboard for comparative period analysis."
            )
            raw_actions = [
                {
                    "type": "NAVIGATE",
                    "route": "/revenue",
                    "filter": {"comparison": "true", "period_a": comparison.label_a, "period_b": comparison.label_b},
                }
            ]
            record_ai_audit(
                db=db,
                user_id=user.id,
                tenant_id=user.tenant_id,
                branch_id=user.branch_id,
                conversation_id=conv_id,
                classification="FINANCIAL_REPORT",
                intent="compare_revenue",
                tool="financial_reporting_service.compare_revenue",
                permission_result="ALLOWED",
                policy_result="ALLOWED",
                execution_result="SUCCESS",
                latency_ms=(time.time() - start_time) * 1000,
            )
            val_actions = validate_and_filter_actions(raw_actions)
            return StructuredAgentOutput(
                intent="financial_reporting",
                classification="FINANCIAL_REPORT",
                actions=val_actions,
                response=AgentResponseContent(summary=summary_msg),
            )

        # 2. Payment Method Summary (e.g. "Show payment-method summary")
        q_lower = query.lower()
        if "payment" in q_lower and ("method" in q_lower or "breakdown" in q_lower or "summary" in q_lower):
            resolved_date = resolve_date_expression(query)
            d_start = resolved_date.start_date if resolved_date else datetime.now(timezone.utc).date()
            d_end = resolved_date.end_date if resolved_date else d_start
            pay_summary = financial_reporting_service.get_payment_method_summary(
                db=db,
                tenant_id=user.tenant_id,
                branch_id=user.branch_id,
                start_date=d_start,
                end_date=d_end,
            )
            label = resolved_date.label if resolved_date else "Today"
            summary_msg = (
                f"💳 **Payment Method Breakdown ({label})**\n\n"
                f"• **💵 Cash**: ₹{pay_summary.cash:,.2f}\n"
                f"• **💳 Card / POS**: ₹{pay_summary.card:,.2f}\n"
                f"• **📱 UPI**: ₹{pay_summary.upi:,.2f}\n"
                f"• **📱 QR**: ₹{pay_summary.qr:,.2f}\n"
                f"• **🌐 Online**: ₹{pay_summary.online:,.2f}\n"
                f"• **Total Sales**: ₹{pay_summary.total:,.2f}\n\n"
                f"Opening the Revenue Dashboard payment methods view."
            )
            raw_actions = [
                {
                    "type": "NAVIGATE",
                    "route": "/revenue",
                    "filter": {"tab": "payment_methods", "date": d_start.isoformat()},
                }
            ]
            record_ai_audit(
                db=db,
                user_id=user.id,
                tenant_id=user.tenant_id,
                branch_id=user.branch_id,
                conversation_id=conv_id,
                classification="FINANCIAL_REPORT",
                intent="payment_method_summary",
                tool="financial_reporting_service.get_payment_method_summary",
                permission_result="ALLOWED",
                policy_result="ALLOWED",
                execution_result="SUCCESS",
                latency_ms=(time.time() - start_time) * 1000,
            )
            val_actions = validate_and_filter_actions(raw_actions)
            return StructuredAgentOutput(
                intent="financial_reporting",
                classification="FINANCIAL_REPORT",
                actions=val_actions,
                response=AgentResponseContent(summary=summary_msg),
            )

        # 3. Daily or Period Revenue Reports
        resolved_date = resolve_date_expression(query)
        today_date = datetime.now(timezone.utc).date()

        if resolved_date and resolved_date.start_date != resolved_date.end_date:
            # Multi-day or monthly report
            report = financial_reporting_service.get_financial_report(
                db=db,
                tenant_id=user.tenant_id,
                branch_id=user.branch_id,
                start_date=resolved_date.start_date,
                end_date=resolved_date.end_date,
            )
            summary_msg = (
                f"📈 **Financial Report for {resolved_date.label}**\n\n"
                f"• **Net Sales**: ₹{report.net_sales:,.2f}\n"
                f"• **Gross Sales**: ₹{report.gross_sales:,.2f}\n"
                f"• **Total Transactions**: {report.transaction_count} paid bills\n"
                f"• **Taxes & Discounts**: Tax ₹{report.tax_total:,.2f} | Discounts ₹{report.discount_total:,.2f}\n"
                f"• **Primary Tender**: Cash ₹{report.payment_methods.cash:,.2f} | Card ₹{report.payment_methods.card:,.2f} | UPI ₹{report.payment_methods.upi:,.2f}\n\n"
                f"I have opened the Revenue Dashboard filtered for {resolved_date.label}."
            )
            raw_actions = [
                {
                    "type": "NAVIGATE",
                    "route": "/revenue",
                    "filter": {"date": resolved_date.start_date.isoformat(), "range": resolved_date.label},
                }
            ]
            tool_used = "financial_reporting_service.get_financial_report"
        else:
            # Single-day report (today, yesterday, specific date)
            target_date = resolved_date.start_date if resolved_date else today_date
            daily = financial_reporting_service.get_daily_financial_summary(
                db=db,
                tenant_id=user.tenant_id,
                branch_id=user.branch_id,
                target_date=target_date,
            )
            label = resolved_date.label if resolved_date else "Today"
            summary_msg = (
                f"💰 **Revenue Summary for {label} ({target_date.isoformat()})**\n\n"
                f"• **Net Revenue**: ₹{daily.net_sales:,.2f}\n"
                f"• **Gross Revenue**: ₹{daily.gross_sales:,.2f}\n"
                f"• **Bills Summary**: {daily.paid_bills} paid, {daily.pending_bills} pending, {daily.cancelled_bills} cancelled\n"
                f"• **Payment Breakdown**: Cash ₹{daily.payment_methods.cash:,.2f} | Card ₹{daily.payment_methods.card:,.2f} | UPI ₹{daily.payment_methods.upi:,.2f}\n\n"
                f"I have opened the Revenue page and loaded records for {target_date.isoformat()}."
            )
            raw_actions = [
                {
                    "type": "NAVIGATE",
                    "route": "/revenue",
                    "filter": {"date": target_date.isoformat()},
                }
            ]
            tool_used = "financial_reporting_service.get_daily_financial_summary"

        # Audit event recording
        record_ai_audit(
            db=db,
            user_id=user.id,
            tenant_id=user.tenant_id,
            branch_id=user.branch_id,
            conversation_id=conv_id,
            classification="FINANCIAL_REPORT",
            intent="revenue_summary",
            tool=tool_used,
            permission_result="ALLOWED",
            policy_result="ALLOWED",
            execution_result="SUCCESS",
            latency_ms=(time.time() - start_time) * 1000,
        )

        scan_payload_for_financial_leak(summary_msg, is_financial_report=True)
        val_actions = validate_and_filter_actions(raw_actions)

        return StructuredAgentOutput(
            intent="financial_reporting",
            classification="FINANCIAL_REPORT",
            actions=val_actions,
            response=AgentResponseContent(summary=summary_msg),
        )

    def _deterministic_operational_engine(
        self,
        db: Session,
        user: User,
        query: str,
        table_snapshots: list[Any],
    ) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        """Provides instant deterministic operational answers when cloud LLM is offline or unconfigured."""
        from app.services.rag.retrieval.hybrid_retrieval import hybrid_retrieval_service
        q = query.lower()
        actions = []
        citations: list[dict[str, Any]] = []

        # 1. SOP & Standard Operating Procedures RAG
        if re.search(r"\b(sop|procedure|policy|checklist|protocol|guideline|cleaning\s+target|no[\s-]show|grace\s+period)\b", q):
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="RESTAURANT_SOP",
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                reply_lines = [
                    "📋 **Official Front-of-House Standard Operating Procedure**\n",
                    rag_res.context_text,
                    "\n*All operational staff must follow established dining room targets.*",
                ]
                return "\n".join(reply_lines), actions, cits

        # 2. Customer Experience & Complaints RAG
        if re.search(r"\b(complaint|complaints|complaining|feedback|reviews?|guest\s+dissatisfaction|service\s+issue|service\s+problem|service\s+quality)\b", q):
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="CUSTOMER_EXPERIENCE",
                user_id=user.id,
                user_role=user.role,
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                actions.append({"type": "NAVIGATE", "route": "/insights"})
                reply_lines = [
                    "⭐ **Customer Experience & Service Quality Knowledge**\n",
                    rag_res.context_text,
                    "\n*Navigating to Operational Insights for guest pacing and shift analytics.*",
                ]
                return "\n".join(reply_lines), actions, cits

        # 3. Kitchen Intelligence & KDS Delay RAG
        if re.search(r"\b(why\s+were\s+orders\s+delayed|delayed\s+orders?|delayed\s+dishes|station\s+bottleneck|kitchen\s+station|prep\s+delay|cooking\s+time|saute|grill)\b", q):
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="KITCHEN",
                user_id=user.id,
                user_role=user.role,
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                actions.append({"type": "NAVIGATE", "route": "/kds"})
                reply_lines = [
                    "🍳 **Kitchen Operations & Station Intelligence**\n",
                    rag_res.context_text,
                    "\n*Navigating to the Kitchen Display System (KDS) for live ticket flows.*",
                ]
                return "\n".join(reply_lines), actions, cits

        # 4. Table Lifecycle RAG (Operational lifecycle, zero billing data)
        if re.search(r"\b(table\s+\d+|table\s+lifecycle|cleaning\s+duration|table\s+performance|why\s+does\s+table\s+\d+\s+stay)\b", q):
            # Extract table number if present
            tbl_match = re.search(r"table\s+(\d+)", q)
            tbl_filter = {"table_number": tbl_match.group(1)} if tbl_match else None
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="TABLE_LIFECYCLE",
                user_id=user.id,
                user_role=user.role,
                entity_filters=tbl_filter,
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                actions.append({"type": "NAVIGATE", "route": "/floor"})
                reply_lines = [
                    "🪑 **Table Operational Lifecycle & History**\n",
                    rag_res.context_text,
                    "\n*Navigating to Table Operations floor canvas.*",
                ]
                return "\n".join(reply_lines), actions, cits

        # 5. Predictive Operations RAG (Forecasts & Recommendations)
        if re.search(r"\b(prepare\s+for\s+tonight|busiest\s+period|likely\s+demand|peak\s+hours|rush\s+projection|what\s+should\s+we\s+prepare|predict|forecast)\b", q):
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="PREDICTIVE_OPERATIONS",
                user_id=user.id,
                user_role=user.role,
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                actions.append({"type": "NAVIGATE", "route": "/reservations"})
                reply_lines = [
                    "🔮 **Predictive Operations & Demand Projections**\n",
                    rag_res.context_text,
                    "\n*Note: Predictions are operational forecasts based on historical pacing and confirmed bookings.*",
                ]
                return "\n".join(reply_lines), actions, cits

        # 6. Manager Decision Memory RAG
        if re.search(r"\b(solved\s+before|manager\s+decision|previous\s+solution|action\s+taken|similar\s+incident|what\s+did\s+the\s+manager\s+do)\b", q):
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="MANAGER_DECISIONS",
                user_id=user.id,
                user_role=user.role,
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                reply_lines = [
                    "🧠 **Manager Decision & Resolution Memory**\n",
                    rag_res.context_text,
                    "\n*Referenced from verified historical shift resolutions.*",
                ]
                return "\n".join(reply_lines), actions, cits

        # 7. Equipment & System Maintenance RAG
        if re.search(r"\b(maintenance|printer\s+jam|kds\s+screen|kds\s+issue|camera\s+offline|hardware\s+repair|equipment\s+failure)\b", q):
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="MAINTENANCE",
                user_id=user.id,
                user_role=user.role,
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                reply_lines = [
                    "🔧 **Equipment Maintenance & Troubleshooting Guide**\n",
                    rag_res.context_text,
                    "\n*Follow safety standards before servicing restaurant hardware.*",
                ]
                return "\n".join(reply_lines), actions, cits

        # 8. Supplier & Inventory Contextual RAG
        if re.search(r"\b(supplier|ingredient\s+source|who\s+provides|delivery\s+schedule|out\s+of\s+stock\s+policy|emergency\s+procurement)\b", q):
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="SUPPLIER_INVENTORY",
                user_id=user.id,
                user_role=user.role,
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                actions.append({"type": "NAVIGATE", "route": "/menu"})
                reply_lines = [
                    "📦 **Supplier & Inventory Knowledge**\n",
                    rag_res.context_text,
                    "\n*Navigating to Menu Management for dish availability.*",
                ]
                return "\n".join(reply_lines), actions, cits

        # 9. Compliance, Hygiene & Food Safety RAG
        if re.search(r"\b(allergen\s+procedure|food\s+safety|hygiene\s+checklist|closing\s+checklist|closing\s+hygiene|haccp|safety\s+incident|emergency\s+procedure)\b", q):
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="COMPLIANCE_SAFETY",
                user_id=user.id,
                user_role=user.role,
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                reply_lines = [
                    "🛡 **Compliance, Food Safety & Hygiene Standards**\n",
                    rag_res.context_text,
                    "\n*Strict compliance with food safety protocols is mandatory.*",
                ]
                return "\n".join(reply_lines), actions, cits

        # 10. Restaurant Layout & Floor Plan History RAG
        if re.search(r"\b(floor\s+plan|table\s+moved|table\s+\d+\s+moved|layout\s+change|camera\s+roi|repositioning|rotation\s+adjustment)\b", q):
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="RESTAURANT_LAYOUT",
                user_id=user.id,
                user_role=user.role,
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                actions.append({"type": "NAVIGATE", "route": "/floor"})
                reply_lines = [
                    "📐 **Floor Plan Architecture & Layout History**\n",
                    rag_res.context_text,
                    "\n*Navigating to Floor Canvas to view active geometry.*",
                ]
                return "\n".join(reply_lines), actions, cits

        # 11. Cross-Branch Operational Benchmark RAG
        if re.search(r"\b(cross[\s-]branch|compare\s+branches|which\s+branch|across\s+locations|best\s+turnover\s+across)\b", q):
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=None,
                domain="CROSS_BRANCH",
                user_id=user.id,
                user_role=user.role,
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                reply_lines = [
                    "🏢 **Cross-Branch Operational Benchmark & Comparison**\n",
                    rag_res.context_text,
                    "\n*Organization-level multi-outlet performance comparison.*",
                ]
                return "\n".join(reply_lines), actions, cits
            elif rag_res.context_text and "Access restricted" in rag_res.context_text:
                return rag_res.context_text, actions, []

        # 2. Table Turnover, Delays & Bottlenecks Hybrid Analytics
        if re.search(r"\b(turnover|turnaround|why\s+is\s+table|delay|slow|bottleneck|kitchen\s+speed)\b", q):
            from app.services.insights_service import compute_insights
            data = compute_insights(db, user.tenant_id)
            stages = data.get("stages", [])
            occupancy = data.get("occupancy", {})
            summary = data.get("summary", [])

            actions.append({"type": "NAVIGATE", "route": "/insights"})

            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="RESTAURANT_SOP",
            )
            cits = [c.model_dump() for c in rag_res.citations]

            lines = [
                "📊 **Operational Turnover & Bottleneck Analysis**\n",
                f"**FACT (Current Operational Metrics)**:",
                f"• Dining Room Capacity: {occupancy.get('pct', 0)}% occupied ({occupancy.get('occupied', 0)} of {occupancy.get('total', 0)} tables).",
            ]
            for st in stages:
                cur = f"{st['current_min']} min" if st['current_min'] is not None else "N/A"
                base = f"{st['baseline_min']} min" if st['baseline_min'] is not None else "N/A"
                lines.append(f"• {st['stage']}: Current average {cur} (7-day baseline {base}, severity: {st['severity'].upper()}).")

            lines.append("\n**OBSERVATION**:")
            for b in summary:
                lines.append(f"• {b['text']}")

            lines.append("\n**INFERENCE & SOP TARGET**:")
            lines.append("• Target table turnaround between departure and reseating is 3–5 minutes (SOP-01).")
            lines.append("• Delayed cleanings or extended dining sessions directly constrain seatings during peak rush.")

            lines.append("\n**RECOMMENDATION**:")
            lines.append("• Inspect active cleaning tables on the Floor Canvas and prioritize bussing station 1.")
            lines.append("• Navigating to the Operational Insights dashboard for live stage breakdowns.")

            return "\n".join(lines), actions, cits

        # 3. Menu Knowledge & Dietary / Allergen RAG
        if re.search(r"\b(allergen|ingredients?|dietary|vegetarian|vegan|gluten|recipe|nut)\b", q):
            actions.append({"type": "NAVIGATE", "route": "/menu"})
            rag_res = hybrid_retrieval_service.retrieve(
                query=query,
                tenant_id=user.tenant_id,
                db=db,
                branch_id=user.branch_id,
                domain="MENU",
            )
            if not rag_res.insufficient_evidence and rag_res.citations:
                cits = [c.model_dump() for c in rag_res.citations]
                reply_lines = [
                    "🍽 **Menu & Culinary Knowledge Reference**\n",
                    rag_res.context_text,
                    "\nNavigating to Menu Management to view live item availability.",
                ]
                return "\n".join(reply_lines), actions, cits

        # 4. Menu Navigation / General Inquiry
        if re.search(r"\b(menu|dishes|food\s+items|recipes?)\b", q):
            actions.append({"type": "NAVIGATE", "route": "/menu"})
            from app.models.menu_item import MenuItem
            total_items = db.query(MenuItem).filter(MenuItem.is_active == True).count()
            return (
                f"Opening Menu Management. You have {total_items} active menu items on file. "
                "Navigating to the Menu page to browse items, categories, and availability.",
                actions,
                citations,
            )

        # 5. Kitchen / KDS Navigation
        if re.search(r"\b(kitchen|kds|cooks?|chef|tickets?)\b", q):
            actions.append({"type": "NAVIGATE", "route": "/kds"})
            return "Opening Kitchen Display System (KDS) for active orders and station flow.", actions, citations

        # 6. Vision mismatches / Camera Setup
        if re.search(r"\b(vision|cctv|mismatch|cameras?)\b", q):
            actions.append({"type": "NAVIGATE", "route": "/camera-setup"})
            from app.models.vision import VisionMismatch
            mismatches = db.query(VisionMismatch).limit(5).all()
            if mismatches:
                return (
                    f"There are {len(mismatches)} active vision mismatches flagged between CCTV and FOH state. "
                    "Navigating to the Camera Setup and AI Model Hub for review.",
                    actions,
                    citations,
                )
            return "No vision mismatches detected. Computer vision observations align with FOH table state.", actions, citations

        # 7. Reservations
        if re.search(r"\b(reservations?|bookings?)\b", q):
            actions.append({"type": "NAVIGATE", "route": "/reservations"})
            from app.services.ai_agent.adapters.sanitized_adapters import get_sanitized_reservations
            res = get_sanitized_reservations(db, user)
            if not res:
                return "There are no upcoming reservations scheduled on file.", actions, citations
            return f"I found {len(res)} upcoming reservations. Opening Reservations management.", actions, citations

        # 8. Busy / Occupied tables
        if re.search(r"\b(busy|occupied|seated|active\s+tables?)\b", q):
            occupied = [t for t in table_snapshots if t.status in ("SEATED", "ACTIVE", "BILLING")]
            actions.append({"type": "NAVIGATE", "route": "/floor"})
            actions.append({"type": "SET_FILTER", "filter": {"status": "occupied"}})
            if not occupied:
                return "All dining tables are currently free. The floor has zero active sessions.", actions, citations
            tables_str = ", ".join(f"T{t.table_number} ({t.occupied_minutes or 0}m)" for t in occupied)
            return (
                f"I found {len(occupied)} occupied tables: {tables_str}. "
                "I have opened Table Operations and filtered occupied tables for you.",
                actions,
                citations,
            )

        # 9. Free / Available tables
        if re.search(r"\b(available|free|vacant|unoccupied)\b", q) or re.search(r"\bopen\s+tables?\b", q):
            available = [t for t in table_snapshots if t.status == "AVAILABLE"]
            actions.append({"type": "NAVIGATE", "route": "/floor"})
            actions.append({"type": "SET_FILTER", "filter": {"status": "available"}})
            if not available:
                return "There are no available tables right now. The dining room is completely full.", actions, citations
            tables_str = ", ".join(f"T{t.table_number} (seats {t.capacity})" for t in available)
            return f"Currently {len(available)} tables are available: {tables_str}.", actions, citations

        # General floor summary fallback
        actions.append({"type": "NAVIGATE", "route": "/floor"})
        avail_count = sum(1 for t in table_snapshots if t.status == "AVAILABLE")
        occ_count = sum(1 for t in table_snapshots if t.status in ("SEATED", "ACTIVE", "BILLING"))
        return (
            f"Front-of-House Overview: {len(table_snapshots)} total tables ({occ_count} occupied, {avail_count} available). "
            "How can I assist with floor, kitchen, reservations, or vision operations?",
            actions,
            citations,
        )


ai_orchestrator = AIOrchestrator()
