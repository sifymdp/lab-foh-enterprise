"""Controlled Tool Registry for the AI Agent.

Enforces tool allowlisting, strict schema definitions, RBAC checks,
policy classifications, and explicit confirmation flags.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.ai_agent.policy.policy_engine import (
    PolicyClassification,
    policy_engine,
)
from app.services.ai_agent.security.egress_scanner import (
    scan_payload_for_financial_leak,
)
from app.services.ai_agent.security.financial_firewall import is_financial_query

logger = logging.getLogger(__name__)


@dataclass
class RegisteredTool:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    permission_required: str
    risk_level: str  # LOW | MEDIUM | HIGH
    policy_class: PolicyClassification
    handler: Callable[[Session, User, dict[str, Any]], dict[str, Any]]


class ToolRegistry:
    """Registry maintaining approved operational tools."""

    def __init__(self):
        self._tools: dict[str, RegisteredTool] = {}

    def register_tool(self, tool: RegisteredTool) -> None:
        # 1. Financial check on tool metadata
        fin_check = is_financial_query(f"{tool.name} {tool.description}")
        if fin_check.blocked or fin_check.is_reporting_query or fin_check.is_transaction_mutation:
            raise ValueError(
                f"SECURITY VIOLATION: Tool '{tool.name}' matches financial concepts "
                f"and cannot be registered in the AI agent tool catalogue."
            )

        self._tools[tool.name] = tool
        logger.debug("Registered operational AI tool: %s", tool.name)

    def get_tool(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[RegisteredTool]:
        return list(self._tools.values())

    def get_openai_tool_specs(self) -> list[dict[str, Any]]:
        """Exports tools in OpenAI-compatible JSON schema."""
        specs = []
        for t in self._tools.values():
            specs.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters_schema,
                },
            })
        return specs

    def execute_tool(
        self,
        db: Session,
        user: User,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[dict[str, Any], bool, str | None]:
        """Validates policy and permissions, then executes tool safely.

        Returns: (result_dict, is_success, error_message)
        """
        tool = self._tools.get(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' is not registered."}, False, "Unknown tool"

        # Policy & RBAC validation
        eval_res = policy_engine.evaluate_tool_policy(
            db=db,
            user=user,
            tool_name=tool.name,
            required_permission=tool.permission_required,
            policy_class=tool.policy_class,
        )

        if not eval_res.allowed:
            return {"error": eval_res.reason}, False, eval_res.reason

        try:
            result = tool.handler(db, user, arguments)
            # Scan result to guarantee no financial leakage
            scan_payload_for_financial_leak(result)
            return result, True, None
        except Exception as exc:
            logger.error("Tool execution failed for '%s': %s", tool_name, exc)
            return {"error": str(exc)}, False, str(exc)


tool_registry = ToolRegistry()
