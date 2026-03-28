from datetime import datetime
from typing import Any, Dict, List
from pydantic import BaseModel


class ConversationTurn(BaseModel):
    role: str       # "agent" | "user" | "system"
    content: str
    timestamp: datetime
    node_name: str


class SessionState(BaseModel):
    session_id: str
    agent_type: str     # "outreach" | "telegram"
    entity_id: str
    turns: List[ConversationTurn] = []
    metadata: Dict[str, Any] = {}
    created_at: datetime
    last_active: datetime
    is_complete: bool = False
