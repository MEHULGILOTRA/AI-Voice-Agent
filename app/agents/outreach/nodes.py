"""
Outreach graph nodes.

Node responsibilities:
  validate_request     — opt-out / quiet hours / idempotency (rule-based, no LLM)
  initiate_call        — Vapi call (mock or real)
  conduct_conversation — THE ONLY LLM NODE: simulates/processes call transcript
  extract_data         — parse transcript with regex (no LLM)
  score_confidence     — field-weight scoring; interrupt() if score < threshold
  write_to_sheets      — upsert parent record
  send_whatsapp        — send missed-call WhatsApp template
  finalize_audit       — write audit entry; always runs

Edge condition functions (used in add_conditional_edges) are at the bottom.
"""
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import interrupt

from app.agents.outreach.state import OutreachState
from app.agents.shared.utils import append_trail, extract_transcript
from app.core import confidence as conf_module
from app.core.idempotency import make_idempotency_key
from app.schemas.parent import OutreachStatus

logger = logging.getLogger(__name__)

# Compiled regex patterns — evaluated once at import time
_OPT_OUT_RE = re.compile(
    r"remove me from|don't call.*?again|not interested|please (?:stop|don't)|do not contact",
    re.IGNORECASE,
)
_CALLBACK_RE = re.compile(
    r"call (?:me )?back|try (?:again )?later|callback|\bThursday\b|\bFriday\b",
    re.IGNORECASE,
)


# ── Nodes ─────────────────────────────────────────────────────────────────────

def validate_request(state: OutreachState, opt_out_checker, quiet_checker, idempotency_checker, settings) -> Dict:
    """
    RULE-BASED. Three checks before any outreach begins:
    1. Opt-out suppression
    2. Quiet hours
    3. Idempotency (already contacted today)
    """
    parent_id = state["parent_id"]

    # 1. Opt-out
    if opt_out_checker.is_opted_out(parent_id):
        logger.info("Parent %s is opted out — skipping", parent_id)
        return {
            "outreach_status": OutreachStatus.OPT_OUT.value,
            "is_complete": True,
            "audit_trail": append_trail(state, "validate_request: BLOCKED — opted out"),
        }

    # 2. Quiet hours
    if quiet_checker.is_quiet_time():
        logger.info("Quiet hours active — skipping outreach for %s", parent_id)
        return {
            "outreach_status": OutreachStatus.PARTIAL.value,
            "is_complete": True,
            "audit_trail": append_trail(state, "validate_request: BLOCKED — quiet hours"),
        }

    # 3. Idempotency
    tab = settings.google_sheets_parent_tab
    if idempotency_checker.is_duplicate(parent_id, "outreach", tab):
        logger.info("Parent %s already contacted today — skipping", parent_id)
        return {
            "outreach_status": OutreachStatus.COMPLETED.value,
            "is_complete": True,
            "audit_trail": append_trail(state, "validate_request: BLOCKED — already contacted today"),
        }

    return {
        "is_complete": False,
        "audit_trail": append_trail(state, "validate_request: PASSED all checks"),
    }


def initiate_call(state: OutreachState, vapi_service, parent_record: Dict) -> Dict:
    """
    Calls VapiService. Sets call_answered and stores raw transcript in messages.
    Uses retry decorator inside VapiService.
    """
    try:
        result = vapi_service.initiate_call(parent_record, state.get("scenario_id", ""))
    except Exception as e:
        logger.error("Vapi call failed for %s: %s", state["parent_id"], e)
        return {
            "call_answered": False,
            "error_message": str(e),
            "audit_trail": append_trail(state, f"initiate_call: FAILED — {e}"),
        }

    transcript = result.get("transcript", "")
    messages = [HumanMessage(content=transcript)] if transcript else []

    return {
        "call_answered": result.get("call_answered", False),
        "messages": messages,
        "audit_trail": _trail(
            state,
            f"initiate_call: answered={result.get('call_answered')}, "
            f"duration={result.get('duration_seconds')}s"
        ),
    }


def conduct_conversation(state: OutreachState, llm) -> Dict:
    """
    THE ONLY LLM NODE in the outreach graph.

    For demo: the transcript is already in state["messages"] from initiate_call
    (loaded from fixture). In production this node would receive live Vapi
    webhook events. The LLM is invoked to produce a structured extraction
    prompt — if a real transcript isn't available yet.

    If the transcript is already present (mock mode), skip the LLM call.
    """
    transcript = extract_transcript(state.get("messages", []))

    if transcript and "CALL_UNANSWERED" not in transcript:
        # Transcript already loaded — no LLM call needed
        logger.info("conduct_conversation: transcript present, skipping LLM call")
        return {
            "audit_trail": append_trail(state, "conduct_conversation: transcript used from fixture/Vapi"),
        }

    # LLM fallback — only if no transcript available
    if llm is not None:
        from app.agents.shared.prompts import OUTREACH_EXTRACTION_PROMPT
        parent_name = state.get("parent_id", "the parent")
        prompt = OUTREACH_EXTRACTION_PROMPT.format(parent_name=parent_name)
        response = llm.invoke([HumanMessage(content=prompt)])
        return {
            "messages": [AIMessage(content=response.content)],
            "audit_trail": append_trail(state, "conduct_conversation: LLM called for transcript"),
        }

    return {
        "audit_trail": append_trail(state, "conduct_conversation: no transcript, no LLM — partial"),
    }


def extract_data(state: OutreachState) -> Dict:
    """
    RULE-BASED. Parses the transcript in state["messages"] using regex.
    Detects opt-out language, callback requests, and specific field patterns.
    No LLM call.
    """
    transcript = extract_transcript(state.get("messages", []))

    updates: Dict[str, Any] = {
        "audit_trail": append_trail(state, "extract_data: parsing transcript"),
    }

    # Detect opt-out (compiled regex, single pass)
    if _OPT_OUT_RE.search(transcript):
        updates["outreach_status"] = OutreachStatus.OPT_OUT.value
        updates["audit_trail"] = append_trail(state, "extract_data: OPT-OUT detected")
        return updates

    # Detect callback request (compiled regex, single pass)
    if _CALLBACK_RE.search(transcript):
        updates["outreach_status"] = OutreachStatus.CALLBACK_REQUESTED.value

    # Extract email
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.[a-z]{2,}", transcript, re.IGNORECASE)
    if email_match:
        updates["captured_email"] = email_match.group(0)

    # Extract mobile (look for phone patterns near keywords)
    mobile_match = re.search(
        r"(?:mobile|phone|number)[^\d+]*(\+?[\d\s\-\(\)]{7,20})",
        transcript, re.IGNORECASE
    )
    if not mobile_match:
        # Fallback: look for standalone E.164-style numbers
        mobile_match = re.search(r"\+1[\-\s]?\d{3}[\-\s]?\d{4}", transcript)
    if mobile_match:
        group = mobile_match.group(1) if mobile_match.lastindex else mobile_match.group(0)
        updates["captured_mobile"] = group.strip()

    # Extract school name (simple: anything after "school" keyword)
    school_match = re.search(
        r"(?:school|attends?|enrolled at)[^\n.]{0,10}?([A-Z][a-zA-Z\s]{3,30}(?:Elementary|Middle|Academy|School|Primary))",
        transcript, re.IGNORECASE
    )
    if school_match:
        updates["captured_school_name"] = school_match.group(1).strip()

    # Extract weekday
    WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for day in WEEKDAYS:
        if re.search(rf"\b{day}\b", transcript, re.IGNORECASE):
            updates["captured_preferred_weekday"] = day
            break

    # Extract time
    time_match = re.search(r"\b(\d{1,2}:\d{2})\s*(AM|PM)?\b", transcript, re.IGNORECASE)
    if time_match:
        raw_time = time_match.group(1)
        ampm = time_match.group(2) or ""
        # Normalise to 24h if PM
        if "pm" in ampm.lower():
            h, m = map(int, raw_time.split(":"))
            if h < 12:
                raw_time = f"{h+12:02d}:{m:02d}"
        updates["captured_preferred_time"] = raw_time

    # Set default status if not already set
    if "outreach_status" not in updates:
        updates["outreach_status"] = OutreachStatus.PARTIAL.value

    updates["audit_trail"] = append_trail(state, f"extract_data: extracted {list(updates.keys())}")
    return updates


def score_confidence(state: OutreachState, settings) -> Dict:
    """
    RULE-BASED. Scores completeness of captured fields.
    Calls interrupt() if score < CONFIDENCE_THRESHOLD — pauses the graph
    until a human reviewer provides corrected data via the review API.
    """
    captured = {
        "email": state.get("captured_email"),
        "mobile": state.get("captured_mobile"),
        "school_name": state.get("captured_school_name"),
        "preferred_weekday": state.get("captured_preferred_weekday"),
        "preferred_time": state.get("captured_preferred_time"),
    }
    score = conf_module.score_outreach(captured)

    updates: Dict[str, Any] = {
        "confidence_score": score,
        "audit_trail": append_trail(state, f"score_confidence: score={score}"),
    }

    threshold = settings.confidence_threshold
    if score < threshold:
        review_id = str(uuid.uuid4())[:8]
        updates["requires_human_review"] = True
        updates["human_review_id"] = review_id
        updates["human_review_reason"] = f"Confidence {score:.2f} below threshold {threshold}"
        updates["outreach_status"] = OutreachStatus.HUMAN_REVIEW.value
        updates["audit_trail"] = _trail(
            state,
            f"score_confidence: INTERRUPT — review_id={review_id}, score={score}"
        )

        # Pause graph — execution resumes when reviewer calls POST /review/{id}/resolve
        human_correction = interrupt({
            "review_id": review_id,
            "reason": updates["human_review_reason"],
            "score": score,
            "captured_data": captured,
        })

        # Apply any corrections the reviewer provided
        if isinstance(human_correction, dict):
            for field, value in human_correction.items():
                if field.startswith("captured_"):
                    updates[field] = value

        updates["requires_human_review"] = False  # resolved
        updates["outreach_status"] = OutreachStatus.PARTIAL.value

    return updates


def write_to_sheets(state: OutreachState, sheets_service, settings) -> Dict:
    """
    Upserts the parent record in Google Sheets with idempotency enforcement.
    """
    parent_id = state["parent_id"]
    idempotency_key = make_idempotency_key(parent_id, "outreach")

    # Build updated parent record from state
    from app.schemas.parent import ParentRecord
    record = ParentRecord(
        parent_id=parent_id,
        name="",  # will be preserved on upsert (existing row)
        email=state.get("captured_email"),
        mobile=state.get("captured_mobile"),
        school_name=state.get("captured_school_name"),
        preferred_weekday=state.get("captured_preferred_weekday"),
        preferred_time=state.get("captured_preferred_time"),
        notes=state.get("captured_notes"),
        outreach_status=OutreachStatus(state.get("outreach_status") or OutreachStatus.PARTIAL.value),
        confidence_score=state.get("confidence_score", 0.0),
        last_contacted=datetime.now(timezone.utc).date().isoformat(),
        idempotency_key=idempotency_key,
    )

    try:
        sheets_service.upsert_parent(record)
        logger.info("Sheets updated for parent %s", parent_id)
        return {
            "sheets_written": True,
            "audit_trail": append_trail(state, f"write_to_sheets: SUCCESS, key={idempotency_key}"),
        }
    except Exception as e:
        logger.error("Sheets write failed for %s: %s", parent_id, e)
        return {
            "sheets_written": False,
            "error_message": str(e),
            "audit_trail": append_trail(state, f"write_to_sheets: FAILED — {e}"),
        }


def send_whatsapp(state: OutreachState, whatsapp_service, parent_record: Dict) -> Dict:
    """
    Sends a WhatsApp template message when the call wasn't answered.
    Uses a pre-written template — no LLM involved.
    """
    try:
        result = whatsapp_service.send_followup(parent_record)
        return {
            "whatsapp_sent": True,
            "outreach_status": OutreachStatus.UNREACHABLE.value,
            "audit_trail": append_trail(state, f"send_whatsapp: sent to {parent_record.get('mobile')}"),
        }
    except Exception as e:
        logger.error("WhatsApp send failed for %s: %s", state["parent_id"], e)
        return {
            "whatsapp_sent": False,
            "error_message": str(e),
            "audit_trail": append_trail(state, f"send_whatsapp: FAILED — {e}"),
        }


def finalize_audit(state: OutreachState, audit_service) -> Dict:
    """
    Writes the final audit entry. Always runs regardless of path taken.
    """
    audit_service.log(
        session_id=state["session_id"],
        agent_type="outreach",
        entity_id=state["parent_id"],
        action="session_complete",
        details=" | ".join(state.get("audit_trail", [])),
        status="success" if not state.get("error_message") else "failure",
    )
    return {
        "is_complete": True,
        "audit_trail": append_trail(state, "finalize_audit: DONE"),
    }


# ── Edge condition functions ───────────────────────────────────────────────────

def route_after_validation(state: OutreachState) -> str:
    if state.get("is_complete"):
        return "finalize_audit"
    return "initiate_call"


def route_after_call(state: OutreachState) -> str:
    if not state.get("call_answered"):
        return "send_whatsapp"
    return "conduct_conversation"


def route_after_extraction(state: OutreachState) -> str:
    status = state.get("outreach_status")
    if status == OutreachStatus.OPT_OUT.value:
        return "write_to_sheets"
    return "score_confidence"


def route_after_scoring(state: OutreachState) -> str:
    # Even after interrupt/resume, we always write to sheets
    return "write_to_sheets"
