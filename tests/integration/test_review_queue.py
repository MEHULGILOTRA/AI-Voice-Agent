"""
I05 — Human review queue: add item, resolve, verify state.
"""
import pytest
from datetime import datetime, timezone

from app.agents.shared.review_queue import ReviewQueue
from app.schemas.review import ReviewDecision, ReviewPriority


def test_add_and_retrieve_pending():
    queue = ReviewQueue()
    item = queue.add(
        session_id="sess-001",
        agent_type="outreach",
        entity_id="P005",
        reason="Low confidence: 0.45",
        context_snapshot={"score": 0.45},
        priority=ReviewPriority.HIGH,
    )

    pending = queue.get_pending()
    assert len(pending) == 1
    assert pending[0].review_id == item.review_id
    assert pending[0].resolved is False


def test_resolve_removes_from_pending():
    queue = ReviewQueue()
    item = queue.add(
        session_id="sess-002",
        agent_type="outreach",
        entity_id="P005",
        reason="test",
        context_snapshot={},
    )

    decision = ReviewDecision(
        review_id=item.review_id,
        decision="approve",
        reviewer_notes="Looks good",
    )
    queue.resolve(item.review_id, decision)

    pending = queue.get_pending()
    assert len(pending) == 0

    all_items = queue.get_all()
    resolved = [i for i in all_items if i.review_id == item.review_id]
    assert resolved[0].resolved is True


def test_get_by_id():
    queue = ReviewQueue()
    item = queue.add(
        session_id="sess-003",
        agent_type="telegram",
        entity_id="ST001",
        reason="missing vars",
        context_snapshot={},
    )
    found = queue.get_by_id(item.review_id)
    assert found is not None
    assert found.entity_id == "ST001"


def test_get_by_nonexistent_id():
    queue = ReviewQueue()
    assert queue.get_by_id("nonexistent") is None


def test_resolve_nonexistent_returns_none():
    queue = ReviewQueue()
    result = queue.resolve("nonexistent", ReviewDecision(
        review_id="nonexistent", decision="approve"
    ))
    assert result is None
