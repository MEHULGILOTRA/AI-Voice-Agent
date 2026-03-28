"""
In-memory human review queue.

When a LangGraph interrupt() fires, the interrupted session's context is:
  1. Added to this in-memory queue
  2. Mirrored to the Google Sheets HumanReview tab (best-effort)

The REST API reads from this queue (GET /review/pending) and posts resolutions
(POST /review/{id}/resolve) which resume the paused graph.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, TYPE_CHECKING

from app.schemas.review import HumanReviewItem, ReviewDecision, ReviewPriority

if TYPE_CHECKING:
    from app.services.sheets import SheetsService

logger = logging.getLogger(__name__)


class ReviewQueue:
    def __init__(self, sheets_service: Optional["SheetsService"] = None):
        self._queue: Dict[str, HumanReviewItem] = {}
        self._sheets = sheets_service

    def add(
        self,
        session_id: str,
        agent_type: str,
        entity_id: str,
        reason: str,
        context_snapshot: dict,
        priority: ReviewPriority = ReviewPriority.MEDIUM,
        review_id: Optional[str] = None,
    ) -> HumanReviewItem:
        rid = review_id or str(uuid.uuid4())[:8]
        item = HumanReviewItem(
            review_id=rid,
            session_id=session_id,
            agent_type=agent_type,
            entity_id=entity_id,
            reason=reason,
            context_snapshot=context_snapshot,
            priority=priority,
            created_at=datetime.now(timezone.utc),
        )
        self._queue[rid] = item

        if self._sheets:
            try:
                self._sheets.append_review_item(item)
            except Exception as e:
                logger.warning("Failed to mirror review item to Sheets: %s", e)

        logger.info("Review item added: %s (%s / %s)", rid, agent_type, entity_id)
        return item

    def resolve(self, review_id: str, decision: ReviewDecision) -> Optional[HumanReviewItem]:
        item = self._queue.get(review_id)
        if not item:
            return None
        item.resolved = True
        item.resolution = f"{decision.decision}: {decision.reviewer_notes or ''}"
        item.resolved_at = datetime.now(timezone.utc)
        self._queue[review_id] = item

        if self._sheets:
            try:
                self._sheets.update_review_resolution(
                    review_id,
                    item.resolution,
                    item.resolved_at.isoformat(),
                )
            except Exception as e:
                logger.warning("Failed to update review resolution in Sheets: %s", e)

        return item

    def get_pending(self) -> List[HumanReviewItem]:
        return [item for item in self._queue.values() if not item.resolved]

    def get_all(self) -> List[HumanReviewItem]:
        return list(self._queue.values())

    def get_by_id(self, review_id: str) -> Optional[HumanReviewItem]:
        return self._queue.get(review_id)


# Module-level singleton
_review_queue: Optional[ReviewQueue] = None


def get_review_queue(sheets_service=None) -> ReviewQueue:
    global _review_queue
    if _review_queue is None:
        _review_queue = ReviewQueue(sheets_service)
    return _review_queue
