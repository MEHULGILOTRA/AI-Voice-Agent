from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    log_id: str
    timestamp: datetime
    session_id: str
    agent_type: str
    entity_id: str
    action: str
    details: str
    status: str  # "success" | "failure" | "skipped"


class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
