"""
Audit log service.

Every node transition is recorded here.
Writes go to an in-memory buffer (always available) and optionally to the
Google Sheets AuditLog tab (best-effort, failures are logged but not raised).
"""
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from app.schemas.common import AuditLogEntry

if TYPE_CHECKING:
    from app.services.sheets import SheetsService

logger = logging.getLogger(__name__)

MAX_BUFFER_SIZE = 10_000

# In-memory buffer (lost on restart, Sheets is the durable store)
_audit_buffer: deque = deque(maxlen=MAX_BUFFER_SIZE)


class AuditService:
    def __init__(self, sheets_service: Optional["SheetsService"] = None):
        self._sheets = sheets_service

    def log(
        self,
        session_id: str,
        agent_type: str,
        entity_id: str,
        action: str,
        details: str,
        status: str = "success",
    ) -> AuditLogEntry:
        entry = AuditLogEntry(
            log_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc),
            session_id=session_id,
            agent_type=agent_type,
            entity_id=entity_id,
            action=action,
            details=details,
            status=status,
        )
        _audit_buffer.append(entry)

        if self._sheets:
            try:
                self._sheets.append_audit_log(entry)
            except Exception as e:
                logger.warning("Audit Sheets write failed (non-fatal): %s", e)

        logger.info("[AUDIT] %s | %s | %s | %s", agent_type, entity_id, action, status)
        return entry

    def get_logs(self, session_id: Optional[str] = None) -> List[AuditLogEntry]:
        if session_id:
            return [e for e in _audit_buffer if e.session_id == session_id]
        return list(_audit_buffer)
