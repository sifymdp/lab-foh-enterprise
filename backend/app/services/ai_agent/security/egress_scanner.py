"""L4 Egress and Response Scanner.

Recursively validates all data packets, tool outputs, message payloads, and LLM completions
before egress to external LLMs and before returning to the frontend.
Protects sensitive transaction artifacts (payment secrets, tokens, card details)
while allowing validated read-only financial report summaries for authorized Owners.
"""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_TRANSACTION_KEYS = {
    "stripe_intent_id",
    "stripe_client_secret",
    "card_number",
    "cvv",
    "cvc",
    "pan",
    "account_number",
    "password",
    "password_hash",
    "secret_key",
    "api_key",
}

OPERATIONAL_FORBIDDEN_KEYS = {
    "bill",
    "bills",
    "bill_id",
    "billid",
    "revenue",
    "paid_revenue",
    "paidrevenuetoday",
    "payment",
    "payments",
    "payment_method",
    "payment_id",
    "refund",
    "refunds",
    "tax",
    "taxes",
    "tax_rate",
    "service_charge",
    "discount_amount",
    "subtotal",
    "total_amount",
    "bill_total",
    "grand_total",
    "price",
    "unit_price",
    "total_price",
    "stripe_intent_id",
    "cashier_shift",
}

CURRENCY_REGEX = re.compile(r"[$₹€£]\s*[0-9]+(?:\.[0-9]{2})?", re.IGNORECASE)


class EgressLeakDetected(Exception):
    """Raised when sensitive financial data is detected in an outbound payload."""
    def __init__(self, key_or_val: str, path: str = ""):
        super().__init__(f"Financial egress violation: '{key_or_val}' at '{path}'")
        self.key_or_val = key_or_val
        self.path = path


def scan_payload_for_financial_leak(data: Any, path: str = "$", is_financial_report: bool = False) -> None:
    """Recursively scans objects, dicts, lists, and strings.

    - For financial reports: strictly forbids sensitive transaction secrets/cards/credentials.
    - For operational queries: forbids any billing/financial keys or currency symbols.
    """
    if data is None:
        return

    if isinstance(data, dict):
        for k, v in data.items():
            curr_path = f"{path}.{k}"
            k_lower = str(k).lower().strip()
            # 1. Sensitive secrets are always forbidden
            if k_lower in SENSITIVE_TRANSACTION_KEYS:
                raise EgressLeakDetected(k, curr_path)

            # 2. In operational context, forbid all financial keys
            if not is_financial_report and k_lower in OPERATIONAL_FORBIDDEN_KEYS:
                raise EgressLeakDetected(k, curr_path)

            scan_payload_for_financial_leak(v, curr_path, is_financial_report=is_financial_report)

    elif isinstance(data, (list, tuple, set)):
        for idx, item in enumerate(data):
            scan_payload_for_financial_leak(item, f"{path}[{idx}]", is_financial_report=is_financial_report)

    elif isinstance(data, str):
        # In operational mode, reject raw currency patterns
        if not is_financial_report and CURRENCY_REGEX.search(data):
            raise EgressLeakDetected("currency_pattern", path)


def sanitize_response_text(text: str, is_financial_report: bool = False) -> str:
    """Validates LLM-generated output text before sending to client.

    If currency or financial claims slipped through in an operational query, substitutes disclaimer.
    """
    if not text:
        return text
    if not is_financial_report and CURRENCY_REGEX.search(text):
        return (
            "Operational summary completed. Notice: References to financial amounts "
            "have been redacted in accordance with the restaurant's security policy."
        )
    return text
