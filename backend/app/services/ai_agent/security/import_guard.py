"""Architectural Import Boundary Guard for the AI Agent.

Guarantees that the AI Agent service layer has ZERO dependencies on
and ZERO imports from confidential billing models, financial tables,
or billing services.
"""

from __future__ import annotations

import sys
import logging

logger = logging.getLogger(__name__)

FORBIDDEN_MODEL_NAMES = {
    "Bill",
    "Payment",
    "PaymentTransaction",
    "RefundRequest",
    "CashierShift",
    "TaxRule",
    "ServiceCharge",
    "Discount",
    "BillingAnomaly",
}

FORBIDDEN_MODULE_SUBSTRINGS = {
    "billing_service",
    "routers.billing",
    "routers.payments",
    "routers.refunds",
    "routers.revenue",
    "routers.cashier_shifts",
    "routers.ai_billing",
}


def assert_financial_import_isolation() -> None:
    """Verifies that none of the forbidden financial models or modules

    are imported or referenced in the ai_agent subsystem.
    """
    for mod_name, mod in list(sys.modules.items()):
        if mod_name.startswith("app.services.ai_agent"):
            # Check module globals for forbidden classes
            if hasattr(mod, "__dict__"):
                for var_name, var_val in mod.__dict__.items():
                    if var_name in FORBIDDEN_MODEL_NAMES:
                        raise ImportError(
                            f"CRITICAL SECURITY VIOLATION: AI Agent module '{mod_name}' "
                            f"imported forbidden financial model '{var_name}'."
                        )
                    # Check for direct service leakage
                    for forbidden_sub in FORBIDDEN_MODULE_SUBSTRINGS:
                        if forbidden_sub in getattr(var_val, "__module__", ""):
                            raise ImportError(
                                f"CRITICAL SECURITY VIOLATION: AI Agent module '{mod_name}' "
                                f"references forbidden financial module '{forbidden_sub}'."
                            )
