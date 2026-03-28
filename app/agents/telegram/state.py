"""
TelegramState — full state for the student messaging LangGraph graph.
"""
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TelegramState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────────────
    session_id: str
    student_id: str
    use_case: str           # MessageUseCase enum value

    # ── Context loaded from Sheets ─────────────────────────────────────────────
    student_record: Optional[Dict[str, Any]]

    # ── Message construction ───────────────────────────────────────────────────
    template_key: Optional[str]
    rendered_message: Optional[str]
    template_variables: Dict[str, Any]

    # ── Delivery ──────────────────────────────────────────────────────────────
    delivery_status: str    # "pending" | "sent" | "failed" | "skipped"
    delivery_attempts: int

    # ── Review ────────────────────────────────────────────────────────────────
    requires_human_review: bool
    escalation_reason: Optional[str]
    human_review_id: Optional[str]

    # ── Control ───────────────────────────────────────────────────────────────
    is_complete: bool

    # ── Error handling ────────────────────────────────────────────────────────
    error_message: Optional[str]

    # ── Audit ─────────────────────────────────────────────────────────────────
    audit_trail: List[str]
    messages: Annotated[List[BaseMessage], add_messages]
