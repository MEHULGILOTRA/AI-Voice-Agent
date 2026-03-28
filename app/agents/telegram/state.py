"""
TelegramState — full state for the student messaging LangGraph graph.
"""
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def build_telegram_initial_state(student_id: str, use_case: str, session_id: str) -> dict:
    """Factory for the initial state dict used by both API endpoints and tests."""
    return {
        "session_id": session_id,
        "student_id": student_id,
        "use_case": use_case,
        "student_record": None,
        "template_key": None,
        "rendered_message": None,
        "template_variables": {},
        "delivery_status": "pending",
        "delivery_attempts": 0,
        "requires_human_review": False,
        "escalation_reason": None,
        "human_review_id": None,
        "is_complete": False,
        "error_message": None,
        "audit_trail": [],
        "messages": [],
    }


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
