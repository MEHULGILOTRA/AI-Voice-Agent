"""
OutreachState — the full state carried through the outreach LangGraph graph.

Every field is Optional so nodes can update only what they touch.
The `messages` list stores the raw call transcript turns using LangChain message types.
"""
from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


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
