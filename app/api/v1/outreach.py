"""
Parent outreach endpoints.
"""
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from app.agents.outreach.scenarios import get_all_scenarios, get_scenario
from app.core.memory import session_thread_id, register_session
from app.schemas.parent import OutreachRequest, OutreachResult

router = APIRouter()

_PARENTS_FILE = Path(__file__).parent.parent.parent.parent / "tests" / "test_data" / "parents.json"


def _load_parents_fixture() -> List[Dict]:
    if _PARENTS_FILE.exists():
        with open(_PARENTS_FILE) as f:
            return json.load(f)
    return []


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

    initial_state = {
        "session_id": session_id,
        "parent_id": scenario["parent_id"],
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

    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = graph.invoke(initial_state, config=config)
    except Exception as e:
        # Graph may have raised interrupt — check if review item was created
        review_queue = getattr(request.app.state, "review_queue", None)
        if review_queue:
            pending = review_queue.get_pending()
            for item in pending:
                if item.session_id == session_id:
                    return {
                        "session_id": session_id,
                        "status": "paused_for_review",
                        "review_id": item.review_id,
                        "reason": item.reason,
                        "message": "Graph paused. POST /api/v1/review/{review_id}/resolve to continue.",
                    }
        raise HTTPException(status_code=500, detail=str(e))

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

    initial_state = {
        "session_id": session_id,
        "parent_id": body.parent_id,
        "scenario_id": body.scenario_id or "",
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

    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = graph.invoke(initial_state, config=config)
        return {"session_id": session_id, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    return {"parents": _load_parents_fixture(), "source": "fixture"}
