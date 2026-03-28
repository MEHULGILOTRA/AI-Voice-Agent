"""
Telegram student messaging endpoints.
"""
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from app.core.memory import session_thread_id, register_session
from app.schemas.student import TelegramMessageRequest

router = APIRouter()

_STUDENTS_FILE = Path(__file__).parent.parent.parent.parent / "tests" / "test_data" / "students.json"


def _load_students_fixture() -> List[Dict]:
    if _STUDENTS_FILE.exists():
        with open(_STUDENTS_FILE) as f:
            return json.load(f)
    return []


@router.post("/send")
def send_message(body: TelegramMessageRequest, request: Request) -> Dict[str, Any]:
    """
    Trigger a contextual Telegram message to a student.
    All message content comes from the student's Sheets record — no hallucination.
    """
    graph = request.app.state.telegram_graph
    session_id = body.session_id or str(uuid.uuid4())
    thread_id = session_thread_id("telegram", session_id)
    register_session(thread_id)

    initial_state = {
        "session_id": session_id,
        "student_id": body.student_id,
        "use_case": body.use_case.value,
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

    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = graph.invoke(initial_state, config=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "session_id": session_id,
        "student_id": body.student_id,
        "use_case": body.use_case.value,
        "delivery_status": result.get("delivery_status"),
        "message_sent": result.get("rendered_message"),
        "requires_human_review": result.get("requires_human_review"),
        "escalation_reason": result.get("escalation_reason"),
        "audit_trail": result.get("audit_trail", []),
    }


@router.get("/session/{session_id}")
def get_session(session_id: str, request: Request) -> Dict[str, Any]:
    """Get the current state of a Telegram session."""
    graph = request.app.state.telegram_graph
    thread_id = session_thread_id("telegram", session_id)
    config = {"configurable": {"thread_id": thread_id}}
    try:
        snapshot = graph.get_state(config)
        return {"session_id": session_id, "state": snapshot.values}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/students")
def list_students(request: Request) -> Dict[str, Any]:
    """List all student records (from Sheets if available, else from test fixture)."""
    sheets = getattr(request.app.state, "sheets", None)
    if sheets and sheets.is_available():
        students = sheets.get_all_students()
        return {"students": [s.model_dump() for s in students], "source": "sheets"}
    return {"students": _load_students_fixture(), "source": "fixture"}
