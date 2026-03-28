"""
I04 — Telegram homework_followup: student record loaded, template filled, sent
"""
import uuid
import pytest
from app.agents.telegram.state import build_telegram_initial_state
from app.core.memory import session_thread_id


def _state(student_id: str, use_case: str) -> dict:
    return build_telegram_initial_state(student_id, use_case, str(uuid.uuid4()))


def test_homework_followup_sent(telegram_graph, mock_sheets):
    """I04: ST001 has overdue homework — message sent successfully."""
    state = _state("ST001", "homework_followup")
    thread_id = session_thread_id("telegram", state["session_id"])
    config = {"configurable": {"thread_id": thread_id}}

    result = telegram_graph.invoke(state, config=config)

    assert result["delivery_status"] == "sent"
    assert result["rendered_message"] is not None
    # Message should contain the student's name
    assert "Emma" in result["rendered_message"]
    # No hallucination: message should be grounded in fixture data
    assert "Math Foundations" in result["rendered_message"]
    assert result["is_complete"] is True


def test_missed_class_followup(telegram_graph):
    """ST002 missed 2 sessions → missed_class message sent."""
    state = _state("ST002", "missed_class")
    thread_id = session_thread_id("telegram", state["session_id"])
    config = {"configurable": {"thread_id": thread_id}}

    result = telegram_graph.invoke(state, config=config)

    assert result["delivery_status"] == "sent"
    assert "James" in result["rendered_message"]
    assert result["is_complete"] is True


def test_opted_out_student_skipped(telegram_graph, opt_out_checker_with_p010):
    """ST010 is opted out → delivery skipped."""
    from app.core.opt_out import OptOutChecker
    from langgraph.checkpoint.memory import MemorySaver
    from app.agents.telegram.graph import build_telegram_graph
    from app.config import Settings
    from app.core.quiet_hours import QuietHoursChecker
    from app.services.audit import AuditService

    oo = OptOutChecker()
    oo.warm({"ST010"})

    class _AlwaysActive(QuietHoursChecker):
        def is_quiet_time(self, tz=None):
            return False

    graph = build_telegram_graph(
        memory=MemorySaver(),
        opt_out_checker=oo,
        quiet_checker=_AlwaysActive(21, 8),
        settings=Settings(
            google_sheets_url="",
            telegram_mock_mode=True, vapi_mock_mode=True, whatsapp_mock_mode=True
        ),
    )

    state = _state("ST010", "satisfaction_survey")
    thread_id = session_thread_id("telegram", state["session_id"])
    config = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke(state, config=config)
    assert result["delivery_status"] == "skipped"


def test_missing_chat_id_triggers_review(telegram_graph):
    """ST008 has no telegram_chat_id → skipped AND requires human review."""
    state = _state("ST008", "upcoming_reminder")
    thread_id = session_thread_id("telegram", state["session_id"])
    config = {"configurable": {"thread_id": thread_id}}

    result = telegram_graph.invoke(state, config=config)

    assert result["delivery_status"] == "skipped"
    assert result["requires_human_review"] is True


def test_upcoming_reminder_sent(telegram_graph):
    """ST004 has an upcoming task — reminder sent."""
    state = _state("ST004", "upcoming_reminder")
    thread_id = session_thread_id("telegram", state["session_id"])
    config = {"configurable": {"thread_id": thread_id}}

    result = telegram_graph.invoke(state, config=config)

    assert result["delivery_status"] == "sent"
    assert "Sofia" in result["rendered_message"]
    assert result["is_complete"] is True
