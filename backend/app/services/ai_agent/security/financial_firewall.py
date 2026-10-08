"""L1 Financial Intent & Request Firewall.

Architectural Principles:
1. AI can READ approved financial REPORTS (ONLY for authorized Owner).
2. AI cannot OPERATE financial TRANSACTIONS (BLOCKED for all roles, including Owner).
3. Financial reporting is restricted to authorized Owner accounts.
"""

from __future__ import annotations

import re
from typing import NamedTuple

SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE = (
    "Financial transactions and modifications cannot be performed through the AI assistant. "
    "For security and compliance, actions such as billing changes, refunds, taxes, and settlements "
    "must be handled directly through the authorized Billing and Cashier workflows."
)

SAFE_FINANCIAL_RESTRICTED_MESSAGE = (
    "Financial reporting is restricted to authorized Owner accounts. "
    "Please refer to the Billing and Analytics modules directly with your authorized account."
)

# Kept for backward compatibility with general refusal
SAFE_FINANCIAL_REFUSAL_MESSAGE = SAFE_FINANCIAL_RESTRICTED_MESSAGE


class FirewallDecision(NamedTuple):
    blocked: bool
    is_transaction_mutation: bool
    is_reporting_query: bool
    reason: str | None
    refusal_message: str | None


# ── 1. Financial Mutation & Transaction Action Patterns (STRICTLY FORBIDDEN) ──
_TRANSACTION_MUTATION_PATTERNS = [
    # Refunds and reversals
    r"\b(?:refunds?|refunded|refunding|chargebacks?|reversals?|credit\s+note|reverse\s+payment)\b",
    # Bill creation, cancellation, modification, deletion
    r"\b(?:create\s+bill|new\s+bill|delete\s+bill|delete\s+today'?s\s+bills|cancel\s+bill|void\s+bill|edit\s+bill|modify\s+bill|split\s+bill|change\s+bill)\b",
    # Payment processing, card charging, payment cancellation
    r"\b(?:process\s+payment|initiate\s+payment|make\s+payment|charge\s+card|pay\s+bill|mark\s+as\s+paid|modify\s+payment(?:\s+status)?|cancel\s+payment|void\s+payment|delete\s+payment)\b",
    # Tax, discount, service charge mutations
    r"\b(?:change\s+tax|set\s+tax|update\s+tax|change\s+service\s+charge|update\s+service\s+charge|(?:apply|give|add|grant|set|modify|change)(?:\s+[\w%]+)?\s+discount|discounts?|waive\s+charge|comp\s+\w+)\b",
    # Invoices and cashier shift transactions
    r"\b(?:create\s+invoice|modify\s+invoice|delete\s+invoice|alter\s+cashier|reconcile|reconciliation|settle\s+shift|close\s+shift)\b",
    # Direct database or SQL injections
    r"\b(?:drop\s+table|update\s+bills?|delete\s+from|insert\s+into\s+bills?)\b",
]

# ── 2. Financial Reporting & Analytics Patterns (READ-ONLY FOR OWNER) ──
_REPORTING_PATTERNS = [
    # Revenue queries (excluding operational table turnover)
    r"\b(?:revenue|earnings?|profits?|losses?|income|financial\s+turnover|business\s+turnover|financial\s+summary|financial\s+report|financial\s+performance)\b",
    r"\b(?:what\s+(?:was|is)\s+(?:the\s+)?revenue)\b",
    r"\b(?:how\s+much\s+(?:revenue|money)\s+(?:did\s+we\s+generate|did\s+we\s+make|we\s+made))\b",
    # Sales totals
    r"\b(?:sales(?:\s+amount|\s+figure|\s+total)?|gross\s+sales|net\s+sales|total\s+sales)\b",
    r"\b(?:what\s+was\s+the\s+total\s+sales\s+amount)\b",
    # Payment method breakdown & bill payment totals
    r"\b(?:payment[- ]method\s+summary|payment[- ]method\s+breakdown|payment\s+breakdown|cash\s+vs\s+card|payment\s+methods|bill\s+payments?|total\s+(?:bill\s+)?payments?)\b",
    # Tax, service charge & discount reporting
    r"\b(?:tax(?:es)?\s+(?:and\s+service\s+charge\s+)?collected|service\s+charges?\s+collected|total\s+tax(?:es)?)\b",
    # Comparisons
    r"\b(?:compare\s+.*(?:revenue|sales)|revenue\s+comparison|sales\s+comparison)\b",
    # Daily / Monthly reports
    r"\b(?:daily\s+(?:revenue|financial)\s+summary|monthly\s+(?:revenue|financial)\s+report)\b",
]

_COMPILED_MUTATION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _TRANSACTION_MUTATION_PATTERNS]
_COMPILED_REPORTING_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _REPORTING_PATTERNS]


def is_financial_transaction_action(query: str) -> FirewallDecision:
    """Evaluates whether the user's text attempts to mutate, create, delete, or process

    financial transactions, bills, taxes, or payments.
    Unconditionally blocked for ALL users.
    """
    if not query or not query.strip():
        return FirewallDecision(
            blocked=False,
            is_transaction_mutation=False,
            is_reporting_query=False,
            reason=None,
            refusal_message=None,
        )

    text = query.strip()
    for pattern in _COMPILED_MUTATION_PATTERNS:
        match = pattern.search(text)
        if match:
            matched_phrase = match.group(0)
            return FirewallDecision(
                blocked=True,
                is_transaction_mutation=True,
                is_reporting_query=False,
                reason=f"Attempted financial transaction action: '{matched_phrase}'",
                refusal_message=SAFE_TRANSACTION_MUTATION_REFUSAL_MESSAGE,
            )

    return FirewallDecision(
        blocked=False,
        is_transaction_mutation=False,
        is_reporting_query=False,
        reason=None,
        refusal_message=None,
    )


def is_financial_reporting_query(query: str) -> FirewallDecision:
    """Evaluates whether the user's text is requesting read-only financial reporting,

    revenue metrics, or payment method summaries.
    """
    if not query or not query.strip():
        return FirewallDecision(
            blocked=False,
            is_transaction_mutation=False,
            is_reporting_query=False,
            reason=None,
            refusal_message=None,
        )

    text = query.strip()
    for pattern in _COMPILED_REPORTING_PATTERNS:
        match = pattern.search(text)
        if match:
            matched_phrase = match.group(0)
            return FirewallDecision(
                blocked=False,
                is_transaction_mutation=False,
                is_reporting_query=True,
                reason=f"Matched financial reporting concept: '{matched_phrase}'",
                refusal_message=None,
            )

    return FirewallDecision(
        blocked=False,
        is_transaction_mutation=False,
        is_reporting_query=False,
        reason=None,
        refusal_message=None,
    )


def is_financial_query(query: str) -> FirewallDecision:
    """Evaluates user text against the L1 Financial Firewall.

    1. If transaction mutation -> BLOCKED immediately.
    2. If reporting query -> flagged as reporting.
    """
    mut_decision = is_financial_transaction_action(query)
    if mut_decision.blocked:
        return mut_decision

    rep_decision = is_financial_reporting_query(query)
    if rep_decision.is_reporting_query:
        return rep_decision

    return FirewallDecision(
        blocked=False,
        is_transaction_mutation=False,
        is_reporting_query=False,
        reason=None,
        refusal_message=None,
    )
