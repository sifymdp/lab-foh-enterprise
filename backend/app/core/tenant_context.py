"""
Tenant context - represents the current tenant/organization/branch scope.
Passed through all service functions to ensure proper data isolation.
"""

from dataclasses import dataclass


@dataclass
class TenantContext:
    """
    Encapsulates the current organization and branch context.
    Every request should populate this from the JWT token.
    """

    tenant_id: str  # Organization ID
    branch_id: str | None = None  # Branch ID (optional for org-level queries)

    def __str__(self) -> str:
        if self.branch_id:
            return f"Org[{self.tenant_id}] Branch[{self.branch_id}]"
        return f"Org[{self.tenant_id}]"
