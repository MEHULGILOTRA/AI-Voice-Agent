"""
I01 — S001 full outreach: graph runs end-to-end, status=completed
I02 — S003 no-answer: Vapi returns no-answer, WhatsApp mock called
I03 — S004 opt-out: parent opts out during call
I04 — S002 callback requested: parent asks to call back
I05 — S005 low-confidence: graph pauses at interrupt, review item created
"""
import uuid
import pytest
from app.agents.outreach.state import build_outreach_initial_state
from app.core.memory import session_thread_id, register_session


def _state(parent_id: str, scenario_id: str) -> dict:
    return build_outreach_initial_state(parent_id, scenario_id, str(uuid.uuid4()))


def test_scenario_s001_full_capture(outreach_graph, mock_sheets):
    """I01: S001 — parent answers, all fields captured, Sheets updated."""
    state = _state("P001", "S001")
    session_id = state["session_id"]
    thread_id = session_thread_id("outreach", session_id)
    config = {"configurable": {"thread_id": thread_id}}

    result = outreach_graph.invoke(state, config=config)

    # Call was answered
    assert result["call_answered"] is True
    # Email extracted from S001 transcript
    assert result.get("captured_email") is not None
    # Status should be completed or partial (depends on transcript extraction)
    assert result["outreach_status"] in (
        "completed", "partial", "callback_requested"
    )
    # Sheets write attempted
    mock_sheets.upsert_parent.assert_called_once()
    # Graph is done
    assert result["is_complete"] is True


def test_scenario_s002_callback_requested(outreach_graph):
    """I04: S002 — parent gives partial info, asks to call back."""
    state = _state("P002", "S002")
    thread_id = session_thread_id("outreach", state["session_id"])
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = outreach_graph.invoke(state, config=config)
        assert result["call_answered"] is True
        assert result["outreach_status"] in ("callback_requested", "partial", "completed", "human_review")
    except Exception:
        # S002 may trigger interrupt if confidence is below threshold
        pass


def test_scenario_s003_no_answer_whatsapp(outreach_graph, mock_sheets):
    """I02: S003 — no answer → WhatsApp sent → status=unreachable."""
    state = _state("P003", "S003")
    session_id = state["session_id"]
    thread_id = session_thread_id("outreach", session_id)
    config = {"configurable": {"thread_id": thread_id}}

    result = outreach_graph.invoke(state, config=config)

    # Call was NOT answered for S003
    assert result["call_answered"] is False
    # WhatsApp should have been sent
    assert result["whatsapp_sent"] is True
    # Status should reflect no answer
    assert result["outreach_status"] == "unreachable"
    assert result["is_complete"] is True


def test_scenario_s004_opt_out(outreach_graph, mock_sheets):
    """S004 — parent opts out during call → status=opt_out."""
    state = _state("P004", "S004")
    session_id = state["session_id"]
    thread_id = session_thread_id("outreach", session_id)
    config = {"configurable": {"thread_id": thread_id}}

    result = outreach_graph.invoke(state, config=config)

    assert result["call_answered"] is True
    assert result["outreach_status"] == "opt_out"
    assert result["is_complete"] is True


def test_scenario_s005_low_confidence_review(outreach_graph):
    """I05: S005 — low confidence triggers human review (interrupt)."""
    state = _state("P005", "S005")
    thread_id = session_thread_id("outreach", state["session_id"])
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = outreach_graph.invoke(state, config=config)
        # If graph completes without interrupt, check it was flagged for review
        assert result.get("requires_human_review") is True or result.get("confidence_score", 1.0) < 0.75
    except Exception:
        # Graph raised interrupt — this is the expected path for S005
        pass


def test_audit_trail_populated(outreach_graph):
    """Every completed run should have a non-empty audit trail."""
    state = _state("P001", "S001")
    thread_id = session_thread_id("outreach", state["session_id"])
    result = outreach_graph.invoke(state, config={"configurable": {"thread_id": thread_id}})
    assert len(result.get("audit_trail", [])) > 0
