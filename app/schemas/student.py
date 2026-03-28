from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel


class MessageUseCase(str, Enum):
    HOMEWORK_FOLLOWUP = "homework_followup"
    MISSED_CLASS = "missed_class"
    SATISFACTION_SURVEY = "satisfaction_survey"
    UPCOMING_REMINDER = "upcoming_reminder"


class StudentRecord(BaseModel):
    student_id: str
    name: str
    telegram_chat_id: Optional[str] = None
    parent_id: Optional[str] = None
    school_name: str
    grade: Optional[str] = None
    last_class_date: Optional[str] = None   # ISO date string
    homework_status: Optional[str] = None   # "pending" | "submitted" | "overdue"
    attendance_streak: int = 0
    opt_out: bool = False
    idempotency_key: str = ""
    # Extra context fields used for template rendering
    course_name: Optional[str] = None
    upcoming_task: Optional[str] = None
    upcoming_deadline: Optional[str] = None # ISO date string
    teacher_note: Optional[str] = None


class TelegramMessageRequest(BaseModel):
    student_id: str
    use_case: MessageUseCase
    session_id: Optional[str] = None


class TelegramMessageResult(BaseModel):
    session_id: str
    student_id: str
    use_case: MessageUseCase
    message_sent: Optional[str] = None
    delivery_status: str
    requires_human_review: bool = False
    escalation_reason: Optional[str] = None
