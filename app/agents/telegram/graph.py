"""
Telegram student messaging LangGraph graph.

Zero LLM calls unless a student replies to a survey (optional sentiment classifier).
"""
import json
import logging
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.telegram import nodes
from app.agents.telegram.state import TelegramState
from app.agents.shared.utils import get_idempotency_checker

logger = logging.getLogger(__name__)

_STUDENTS_FILE = (
    Path(__file__).parent.parent.parent.parent / "tests" / "test_data" / "students.json"
)


def _load_students_fixture():
    if _STUDENTS_FILE.exists():
        with open(_STUDENTS_FILE) as f:
            return json.load(f)
    return []


def build_telegram_graph(
    memory: MemorySaver,
    sheets_service=None,
    telegram_client=None,
    audit_service=None,
    opt_out_checker=None,
    quiet_checker=None,
    idempotency_checker=None,
    settings=None,
):
    from app.config import get_settings
    from app.core.opt_out import get_student_opt_out_checker
    from app.core.quiet_hours import QuietHoursChecker
    from app.services.audit import AuditService
    from app.services.telegram_client import TelegramClient

    _settings = settings or get_settings()
    _opt_out = opt_out_checker or get_student_opt_out_checker()
    _quiet = quiet_checker or QuietHoursChecker(
        _settings.quiet_hours_start, _settings.quiet_hours_end
    )
    _audit = audit_service or AuditService(sheets_service)
    _students_fixture = _load_students_fixture()
    _idempotency = get_idempotency_checker(sheets_service, idempotency_checker)

    # Resolve services once at build time
    _client = telegram_client or TelegramClient(_settings)

    # ── Node closures ─────────────────────────────────────────────────────────
    def _load_context(state):
        return nodes.load_student_context(state, sheets_service, _students_fixture)

    def _check(state):
        return nodes.check_preconditions(state, _opt_out, _quiet, _idempotency, _settings)

    def _select(state):
        return nodes.select_template(state)

    def _render(state):
        return nodes.render_message(state)

    def _validate(state):
        return nodes.validate_output(state)

    def _send(state):
        return nodes.send_telegram(state, _client)

    def _record(state):
        return nodes.record_delivery(state, sheets_service, _settings)

    def _audit_node(state):
        return nodes.finalize_audit(state, _audit)

    # ── Build graph ───────────────────────────────────────────────────────────
    builder = StateGraph(TelegramState)
    builder.add_node("load_student_context", _load_context)
    builder.add_node("check_preconditions", _check)
    builder.add_node("select_template", _select)
    builder.add_node("render_message", _render)
    builder.add_node("validate_output", _validate)
    builder.add_node("send_telegram", _send)
    builder.add_node("record_delivery", _record)
    builder.add_node("finalize_audit", _audit_node)

    builder.add_edge(START, "load_student_context")
    builder.add_conditional_edges("load_student_context", nodes.route_after_load)
    builder.add_conditional_edges("check_preconditions", nodes.route_after_preconditions)
    builder.add_conditional_edges("select_template", nodes.route_after_template_select)
    builder.add_conditional_edges("render_message", nodes.route_after_render)
    builder.add_conditional_edges("validate_output", nodes.route_after_validation)
    builder.add_edge("send_telegram", "record_delivery")
    builder.add_edge("record_delivery", "finalize_audit")
    builder.add_edge("finalize_audit", END)

    return builder.compile(checkpointer=memory)
