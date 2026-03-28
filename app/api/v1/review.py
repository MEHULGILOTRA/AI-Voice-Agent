"""
Human review queue endpoints.

Operators use these endpoints to:
1. See all paused sessions (GET /pending)
2. Resolve a review item and resume the graph (POST /{id}/resolve)
"""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from langgraph.types import Command

from app.core.memory import session_thread_id
from app.schemas.review import ReviewDecision

router = APIRouter()


@router.get("/pending")
def get_pending_reviews(request: Request) -> Dict[str, Any]:
    """List all sessions currently paused for human review."""
    review_queue = request.app.state.review_queue
    pending = review_queue.get_pending()
    return {
        "count": len(pending),
        "items": [item.model_dump() for item in pending],
    }


@router.get("/history")
def get_review_history(request: Request) -> Dict[str, Any]:
    """List all review items (resolved and unresolved)."""
    review_queue = request.app.state.review_queue
    return {
        "items": [item.model_dump() for item in review_queue.get_all()],
    }


@router.get("/{review_id}")
def get_review_item(review_id: str, request: Request) -> Dict[str, Any]:
    """Get a specific review item by ID."""
    review_queue = request.app.state.review_queue
    item = review_queue.get_by_id(review_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Review item {review_id} not found")
    return item.model_dump()


@router.post("/{review_id}/resolve")
def resolve_review(review_id: str, decision: ReviewDecision, request: Request) -> Dict[str, Any]:
    """
    Resolve a human review item and resume the paused LangGraph session.

    decision.edited_data — corrections to apply to the graph state before resuming.
    decision.decision    — "approve" | "reject" | "edit"
    """
    review_queue = request.app.state.review_queue
    item = review_queue.get_by_id(review_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Review item {review_id} not found")
    if item.resolved:
        raise HTTPException(status_code=400, detail="Review item already resolved")

    # Determine which graph to resume based on agent_type
    agent_type = item.agent_type
    session_id = item.session_id

    graph_attr = "outreach_graph" if agent_type == "outreach" else "telegram_graph"
    graph = getattr(request.app.state, graph_attr, None)
    if not graph:
        raise HTTPException(status_code=500, detail=f"Graph '{graph_attr}' not initialised")

    thread_id = session_thread_id(agent_type, session_id)
    config = {"configurable": {"thread_id": thread_id}}

    # Resume the graph with the reviewer's correction (or empty dict for approve)
    resume_value = decision.edited_data or {}
    try:
        result = graph.invoke(Command(resume=resume_value), config=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph resume failed: {e}")

    # Mark the review item as resolved
    review_queue.resolve(review_id, decision)

    return {
        "review_id": review_id,
        "resolved": True,
        "graph_result": {
            "outreach_status": result.get("outreach_status"),
            "confidence_score": result.get("confidence_score"),
            "sheets_written": result.get("sheets_written"),
            "delivery_status": result.get("delivery_status"),
            "is_complete": result.get("is_complete"),
        },
    }


@router.get("/audit/logs")
def get_audit_logs(session_id: str = None, request: Request = None) -> Dict[str, Any]:
    """Return audit log entries, optionally filtered by session_id."""
    audit_service = getattr(request.app.state, "audit_service", None)
    if not audit_service:
        return {"logs": []}
    logs = audit_service.get_logs(session_id)
    return {"logs": [e.model_dump() for e in logs]}
