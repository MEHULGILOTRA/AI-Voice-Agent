from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel


class ReviewPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class HumanReviewItem(BaseModel):
    review_id: str
    session_id: str
    agent_type: str           # "outreach" | "telegram"
    entity_id: str
    reason: str
    context_snapshot: Dict[str, Any]
    priority: ReviewPriority = ReviewPriority.MEDIUM
    created_at: datetime
    resolved: bool = False
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None


class ReviewDecision(BaseModel):
    review_id: str
    decision: str             # "approve" | "reject" | "edit"
    edited_data: Optional[Dict[str, Any]] = None
    reviewer_notes: Optional[str] = None
