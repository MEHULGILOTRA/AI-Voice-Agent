"""
OutreachState — the full state carried through the outreach LangGraph graph.

Every field is Optional so nodes can update only what they touch.
The `messages` list stores the raw call transcript turns using LangChain message types.
"""
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


def build_outreach_initial_state(parent_id: str, scenario_id: str, session_id: str) -> dict:
    """Factory for the initial state dict used by both API endpoints and tests."""
    return {
        "session_id": session_id,
        "parent_id": parent_id,
        "scenario_id": scenario_id,
        "messages": [],
        "captured_email": None,
        "captured_mobile": None,
        "captured_school_name": None,
        "captured_preferred_weekday": None,
        "captured_preferred_time": None,
        "captured_notes": None,
        "outreach_status": None,
        "confidence_score": 0.0,
        "requires_human_review": False,
        "human_review_reason": None,
        "human_review_id": None,
        "call_answered": False,
        "whatsapp_sent": False,
        "sheets_written": False,
        "is_complete": False,
        "error_message": None,
        "audit_trail": [],
    }


class OutreachState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────────────────
    session_id: str
    parent_id: str
    scenario_id: str

    # ── Transcript / conversation ─────────────────────────────────────────────
    messages: Annotated[List[BaseMessage], add_messages]

    # ── Fields captured from the call ─────────────────────────────────────────
    captured_email: Optional[str]
    captured_mobile: Optional[str]
    captured_school_name: Optional[str]
    captured_preferred_weekday: Optional[str]
    captured_preferred_time: Optional[str]
    captured_notes: Optional[str]

    # ── Outcome ───────────────────────────────────────────────────────────────
    outreach_status: Optional[str]       # OutreachStatus enum value
    confidence_score: float
    requires_human_review: bool
    human_review_reason: Optional[str]
    human_review_id: Optional[str]

    # ── Control flags ─────────────────────────────────────────────────────────
    call_answered: bool
    whatsapp_sent: bool
    sheets_written: bool
    is_complete: bool

    # ── Error handling ────────────────────────────────────────────────────────
    error_message: Optional[str]

    # ── Audit trail (node-level breadcrumbs) ──────────────────────────────────
    audit_trail: List[str]
