"""Policy Engine for the AI Agent.

Classifies incoming intents and tool requests against RBAC, organizational boundaries,
and risk categories.
"""

from __future__ import annotations

import enum
from typing import NamedTuple

from sqlalchemy.orm import Session

from app.core.permissions import has_user_permission
from app.models.user import User


class PolicyClassification(str, enum.Enum):
    READ_ONLY_OPERATIONAL = "READ_ONLY_OPERATIONAL"
    OPERATIONAL_ANALYTICS = "OPERATIONAL_ANALYTICS"
    NAVIGATION = "NAVIGATION"
    RECOMMENDATION = "RECOMMENDATION"
    VISION_ANALYSIS = "VISION_ANALYSIS"
    CONTROLLED_OPERATIONAL_ACTION = "CONTROLLED_OPERATIONAL_ACTION"
    SENSITIVE_READ = "SENSITIVE_READ"
    FINANCIAL_READ = "FINANCIAL_READ"
    FINANCIAL_ACTION = "FINANCIAL_ACTION"
    SECURITY_ACTION = "SECURITY_ACTION"
    DESTRUCTIVE_ACTION = "DESTRUCTIVE_ACTION"


class PolicyEvaluation(NamedTuple):
    allowed: bool
    requires_confirmation: bool
    reason: str | None
    classification: PolicyClassification


class PolicyEngine:
    """Evaluates requests and tool invocations against operational policies and RBAC."""

    @staticmethod
    def evaluate_tool_policy(
        db: Session,
        user: User,
        tool_name: str,
        required_permission: str,
        policy_class: PolicyClassification,
    ) -> PolicyEvaluation:
        # 1. Hard-blocked classes
        if policy_class in (
            PolicyClassification.FINANCIAL_READ,
            PolicyClassification.FINANCIAL_ACTION,
        ):
            return PolicyEvaluation(
                allowed=False,
                requires_confirmation=False,
                reason="Financial and billing operations are strictly blocked from the AI agent.",
                classification=policy_class,
            )

        if policy_class in (
            PolicyClassification.SECURITY_ACTION,
            PolicyClassification.DESTRUCTIVE_ACTION,
        ):
            return PolicyEvaluation(
                allowed=False,
                requires_confirmation=False,
                reason="Security and destructive system operations cannot be initiated via AI.",
                classification=policy_class,
            )

        # 2. RBAC Permission Check
        if required_permission:
            has_perm = has_user_permission(db, user, required_permission)
            if not has_perm:
                return PolicyEvaluation(
                    allowed=False,
                    requires_confirmation=False,
                    reason=f"User lacks required operational permission: '{required_permission}'.",
                    classification=policy_class,
                )

        # 3. Controlled operational actions require confirmation
        if policy_class == PolicyClassification.CONTROLLED_OPERATIONAL_ACTION:
            return PolicyEvaluation(
                allowed=True,
                requires_confirmation=True,
                reason="Operational mutation requires user confirmation.",
                classification=policy_class,
            )

        return PolicyEvaluation(
            allowed=True,
            requires_confirmation=False,
            reason=None,
            classification=policy_class,
        )


policy_engine = PolicyEngine()
