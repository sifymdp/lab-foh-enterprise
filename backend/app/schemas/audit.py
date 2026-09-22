from datetime import datetime
from app.schemas.common import CamelModel


class AuditLogOut(CamelModel):
    id: str
    user_id: str | None = None
    user_name: str | None = None
    user_email: str | None = None
    user_role: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    created_at: datetime
