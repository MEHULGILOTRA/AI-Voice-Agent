from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr


class OutreachStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    PARTIAL = "partial"
    CALLBACK_REQUESTED = "callback_requested"
    UNREACHABLE = "unreachable"
    WRONG_NUMBER = "wrong_number"
    OPT_OUT = "opt_out"
    HUMAN_REVIEW = "human_review"


class ParentRecord(BaseModel):
    parent_id: str
    name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    school_name: Optional[str] = None
    preferred_weekday: Optional[str] = None  # e.g. "Monday"
    preferred_time: Optional[str] = None     # e.g. "10:00"
    notes: Optional[str] = None
    outreach_status: OutreachStatus = OutreachStatus.PENDING
    confidence_score: float = 0.0
    last_contacted: Optional[str] = None
    idempotency_key: str = ""
    opt_out: bool = False


class OutreachRequest(BaseModel):
    parent_id: str
    scenario_id: Optional[str] = None
    session_id: Optional[str] = None


class OutreachResult(BaseModel):
    session_id: str
    parent_id: str
    status: OutreachStatus
    captured_data: Dict[str, Any]
    confidence_score: float
    requires_human_review: bool
    audit_trail: List[str]
    whatsapp_sent: bool = False
    sheets_written: bool = False
