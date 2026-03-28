"""
Telegram agent nodes. ZERO LLM calls by default.

Node flow:
  load_student_context  → check_preconditions → select_template
  → render_message → validate_output → send_telegram
  → record_delivery → finalize_audit
"""
import logging
import uuid
from typing import Any, Dict, Optional

from langgraph.types import interrupt

from app.agents.shared.utils import append_trail
from app.agents.telegram import templates as tmpl
from app.agents.telegram.state import TelegramState
from app.schemas.review import ReviewPriority

logger = logging.getLogger(__name__)


# ── Nodes ─────────────────────────────────────────────────────────────────────

def load_student_context(state: TelegramState, sheets_service, students_fixture: list) -> Dict:
    """
    Loads the student record from Google Sheets (or test fixture if Sheets unavailable).
    ALL template variables come exclusively from this record — no hallucination possible.
    """
    student_id = state["student_id"]
    record = None

    if sheets_service:
        try:
            r = sheets_service.get_student_by_id(student_id)
            if r:
                record = r.model_dump()
        except Exception as e:
            logger.warning("Sheets unavailable, falling back to fixture: %s", e)

    if record is None:
        for s in students_fixture:
            if s["student_id"] == student_id:
                record = s
                break

    if record is None:
        return {
            "student_record": None,
            "requires_human_review": True,
            "escalation_reason": f"Student {student_id} not found",
            "is_complete": True,
            "audit_trail": append_trail(state, f"load_student_context: NOT FOUND — {student_id}"),
        }

    return {
        "student_record": record,
        "audit_trail": append_trail(state, f"load_student_context: loaded {student_id}"),
    }


def check_preconditions(state: TelegramState, opt_out_checker, quiet_checker, idempotency_checker, settings) -> Dict:
    """
    RULE-BASED. Checks opt-out, quiet hours, idempotency, and chat_id presence.
    """
    record = state.get("student_record") or {}
    student_id = state["student_id"]

    # 1. Opt-out
    if opt_out_checker.is_opted_out(student_id) or record.get("opt_out"):
        return {
            "delivery_status": "skipped",
            "is_complete": True,
            "audit_trail": append_trail(state, "check_preconditions: BLOCKED — opted out"),
        }

    # 2. Quiet hours
    if quiet_checker.is_quiet_time():
        return {
            "delivery_status": "skipped",
            "is_complete": True,
            "audit_trail": append_trail(state, "check_preconditions: BLOCKED — quiet hours"),
        }

    # 3. Idempotency
    tab = settings.google_sheets_student_tab
    use_case = state.get("use_case", "")
    if idempotency_checker.is_duplicate(student_id, use_case, tab):
        return {
            "delivery_status": "skipped",
            "is_complete": True,
            "audit_trail": append_trail(state, "check_preconditions: BLOCKED — already sent today"),
        }

    # 4. Missing chat_id
    if not record.get("telegram_chat_id"):
        return {
            "delivery_status": "skipped",
            "requires_human_review": True,
            "escalation_reason": "telegram_chat_id missing",
            "is_complete": True,
            "audit_trail": append_trail(state, "check_preconditions: BLOCKED — no chat_id"),
        }

    return {
        "audit_trail": append_trail(state, "check_preconditions: PASSED"),
    }


def select_template(state: TelegramState) -> Dict:
    """
    RULE-BASED. Maps use_case → template key (simple dict lookup, no LLM).
    """
    use_case = state.get("use_case", "")
    if use_case not in tmpl.TEMPLATES:
        return {
            "requires_human_review": True,
            "escalation_reason": f"Unknown use_case: {use_case}",
            "is_complete": True,
            "audit_trail": append_trail(state, f"select_template: UNKNOWN use_case {use_case}"),
        }
    return {
        "template_key": use_case,
        "audit_trail": append_trail(state, f"select_template: selected {use_case}"),
    }


def render_message(state: TelegramState) -> Dict:
    """
    RULE-BASED. Fills template with ONLY data from student_record.
    If required variables are missing, triggers human review interrupt().
    """
    record = state.get("student_record") or {}
    template_key = state.get("template_key", "")

    # Build template variables from student record ONLY
    variables = {
        "student_name": record.get("name", ""),
        "course_name": record.get("course_name", ""),
        "last_class_date": record.get("last_class_date", ""),
        "homework_status": record.get("homework_status", ""),
        "upcoming_task": record.get("upcoming_task", ""),
        "upcoming_deadline": record.get("upcoming_deadline", ""),
        "teacher_note": record.get("teacher_note", ""),
    }

    missing = tmpl.get_missing_vars(template_key, variables)
    if missing:
        review_id = str(uuid.uuid4())[:8]
        context = {
            "template_key": template_key,
            "missing_vars": missing,
            "available_vars": {k: v for k, v in variables.items() if v},
        }

        # Pause for human to provide missing data
        correction = interrupt({
            "review_id": review_id,
            "reason": f"Missing template variables: {missing}",
            "context": context,
        })

        # Apply corrections
        if isinstance(correction, dict):
            variables.update(correction)

    try:
        rendered = tmpl.render(template_key, variables)
    except KeyError as e:
        return {
            "delivery_status": "failed",
            "requires_human_review": True,
            "escalation_reason": f"Template render error: {e}",
            "is_complete": True,
            "audit_trail": append_trail(state, f"render_message: FAILED — {e}"),
        }

    return {
        "rendered_message": rendered,
        "template_variables": variables,
        "audit_trail": append_trail(state, "render_message: rendered successfully"),
    }


def validate_output(state: TelegramState) -> Dict:
    """
    RULE-BASED. Checks for unfilled placeholders in the rendered message.
    Guards against template bugs — no hallucination check needed since
    all data comes from Sheets.
    """
    message = state.get("rendered_message", "")
    import re
    unfilled = re.findall(r"\{[a-z_]+\}", message)
    if unfilled:
        return {
            "requires_human_review": True,
            "escalation_reason": f"Unfilled placeholders: {unfilled}",
            "is_complete": True,
            "audit_trail": append_trail(state, f"validate_output: FAILED — {unfilled}"),
        }
    return {
        "audit_trail": append_trail(state, "validate_output: PASSED"),
    }


def send_telegram(state: TelegramState, telegram_client) -> Dict:
    """Sends the rendered message via Telegram Bot API (or mock)."""
    record = state.get("student_record") or {}
    chat_id = record.get("telegram_chat_id", "")
    message = state.get("rendered_message", "")

    try:
        result = telegram_client.send_message(chat_id, message)
        return {
            "delivery_status": "sent",
            "delivery_attempts": state.get("delivery_attempts", 0) + 1,
            "audit_trail": append_trail(state, f"send_telegram: sent to chat_id={chat_id}"),
        }
    except Exception as e:
        logger.error("Telegram send failed for %s: %s", state["student_id"], e)
        return {
            "delivery_status": "failed",
            "delivery_attempts": state.get("delivery_attempts", 0) + 1,
            "audit_trail": append_trail(state, f"send_telegram: FAILED — {e}"),
        }


def record_delivery(state: TelegramState, sheets_service, settings) -> Dict:
    """Writes delivery status back to the student record in Sheets."""
    if not sheets_service:
        return {"audit_trail": append_trail(state, "record_delivery: skipped — no Sheets")}

    student_id = state["student_id"]
    try:
        record = sheets_service.get_student_by_id(student_id)
        if record:
            from app.core.idempotency import make_idempotency_key
            record.idempotency_key = make_idempotency_key(student_id, state.get("use_case", ""))
            sheets_service.upsert_student(record)
    except Exception as e:
        logger.warning("record_delivery Sheets write failed: %s", e)

    return {
        "audit_trail": append_trail(state, "record_delivery: updated Sheets"),
    }


def finalize_audit(state: TelegramState, audit_service) -> Dict:
    """Always runs. Writes final audit entry."""
    audit_service.log(
        session_id=state["session_id"],
        agent_type="telegram",
        entity_id=state["student_id"],
        action="session_complete",
        details=" | ".join(state.get("audit_trail", [])),
        status="success" if state.get("delivery_status") == "sent" else "skipped_or_failed",
    )
    return {
        "is_complete": True,
        "audit_trail": append_trail(state, "finalize_audit: DONE"),
    }


# ── Edge conditions ────────────────────────────────────────────────────────────

def route_after_load(state: TelegramState) -> str:
    """Route after load_student_context — always go to check_preconditions unless student not found."""
    if state.get("requires_human_review") or state.get("escalation_reason"):
        return "finalize_audit"
    return "check_preconditions"


def route_after_preconditions(state: TelegramState) -> str:
    if state.get("is_complete") or state.get("delivery_status") in ("skipped", "failed"):
        return "finalize_audit"
    return "select_template"


def route_after_template_select(state: TelegramState) -> str:
    if state.get("is_complete"):
        return "finalize_audit"
    return "render_message"


def route_after_render(state: TelegramState) -> str:
    if state.get("is_complete") or state.get("delivery_status") == "failed":
        return "finalize_audit"
    return "validate_output"


def route_after_validation(state: TelegramState) -> str:
    if state.get("is_complete"):
        return "finalize_audit"
    return "send_telegram"
