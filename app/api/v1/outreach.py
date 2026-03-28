"""
Parent outreach endpoints.
"""
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from app.agents.outreach.scenarios import get_all_scenarios, get_scenario
from app.agents.outreach.state import build_outreach_initial_state
from app.core.fixtures import load_parents_fixture
from app.core.memory import session_thread_id, register_session
from app.schemas.parent import OutreachRequest, OutreachResult

router = APIRouter()


def _invoke_with_interrupt_handling(
    graph, initial_state: dict, config: dict, session_id: str, request: Request
) -> dict:
    """Invoke the outreach graph, handling LangGraph interrupt() pauses gracefully."""
    try:
        return graph.invoke(initial_state, config=config)
    except Exception as e:
        review_queue = getattr(request.app.state, "review_queue", None)
        if review_queue:
            for item in review_queue.get_pending():
                if item.session_id == session_id:
                    return {
                        "session_id": session_id,
                        "status": "paused_for_review",
                        "review_id": item.review_id,
                        "reason": item.reason,
                        "outreach_status": "human_review",
                        "requires_human_review": True,
                        "human_review_id": item.review_id,
                        "message": "Graph paused. POST /api/v1/review/{review_id}/resolve to continue.",
                    }
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios")
def list_scenarios():
    """List all 5 demo scenarios."""
    return {"scenarios": get_all_scenarios()}


@router.post("/scenario/{scenario_id}/run")
def run_scenario(scenario_id: str, request: Request) -> Dict[str, Any]:
    """
    Run one of the 5 demo scenarios end-to-end.
    Uses test data — no real API calls unless mock modes are disabled.
    """
    scenario = get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    graph = request.app.state.outreach_graph
    session_id = str(uuid.uuid4())
    thread_id = session_thread_id("outreach", session_id)
    register_session(thread_id)

    initial_state = build_outreach_initial_state(scenario["parent_id"], scenario_id, session_id)
    config = {"configurable": {"thread_id": thread_id}}

    result = _invoke_with_interrupt_handling(graph, initial_state, config, session_id, request)

    return {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "parent_id": scenario["parent_id"],
        "outreach_status": result.get("outreach_status"),
        "confidence_score": result.get("confidence_score"),
        "requires_human_review": result.get("requires_human_review"),
        "human_review_id": result.get("human_review_id"),
        "captured_data": {
            "email": result.get("captured_email"),
            "mobile": result.get("captured_mobile"),
            "school_name": result.get("captured_school_name"),
            "preferred_weekday": result.get("captured_preferred_weekday"),
            "preferred_time": result.get("captured_preferred_time"),
        },
        "call_answered": result.get("call_answered"),
        "whatsapp_sent": result.get("whatsapp_sent"),
        "sheets_written": result.get("sheets_written"),
        "audit_trail": result.get("audit_trail", []),
    }


@router.post("/start")
def start_outreach(body: OutreachRequest, request: Request) -> Dict[str, Any]:
    """Start an outreach session for a given parent_id."""
    graph = request.app.state.outreach_graph
    session_id = body.session_id or str(uuid.uuid4())
    thread_id = session_thread_id("outreach", session_id)
    register_session(thread_id)

    initial_state = build_outreach_initial_state(body.parent_id, body.scenario_id or "", session_id)
    config = {"configurable": {"thread_id": thread_id}}

    result = _invoke_with_interrupt_handling(graph, initial_state, config, session_id, request)
    return {"session_id": session_id, **result}


@router.get("/session/{session_id}")
def get_session(session_id: str, request: Request) -> Dict[str, Any]:
    """Get the current state of an outreach session."""
    graph = request.app.state.outreach_graph
    thread_id = session_thread_id("outreach", session_id)
    config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshot = graph.get_state(config)
        return {"session_id": session_id, "state": snapshot.values}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/parents")
def list_parents(request: Request) -> Dict[str, Any]:
    """List all parent records (from Sheets if available, else from test fixture)."""
    sheets = getattr(request.app.state, "sheets", None)
    if sheets and sheets.is_available():
        parents = sheets.get_all_parents()
        return {"parents": [p.model_dump() for p in parents], "source": "sheets"}
    # Fallback to fixture
    return {"parents": load_parents_fixture(), "source": "fixture"}
