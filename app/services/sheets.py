"""
Google Sheets service — the sole data layer for the entire application.

All reads and writes go through this class.
When GOOGLE_SHEETS_URL is empty the service raises ConfigurationError on
first access, but the app will still start and serve health checks.

Tab structure (headers created automatically on first use):
  Parents     — parent records + outreach outcomes
  Students    — student records
  AuditLog    — append-only event log
  HumanReview — paused sessions awaiting operator decision
"""
import json
import logging
from typing import Any, Dict, List, Optional, Set

from app.config import Settings
from app.schemas.common import AuditLogEntry
from app.schemas.parent import ParentRecord, OutreachStatus
from app.schemas.review import HumanReviewItem
from app.schemas.student import StudentRecord

logger = logging.getLogger(__name__)

# Column headers for each tab
PARENT_HEADERS = [
    "parent_id", "name", "email", "mobile", "school_name",
    "preferred_weekday", "preferred_time", "notes",
    "outreach_status", "confidence_score", "last_contacted",
    "idempotency_key", "opt_out",
]
STUDENT_HEADERS = [
    "student_id", "name", "telegram_chat_id", "parent_id", "school_name",
    "grade", "last_class_date", "homework_status", "attendance_streak",
    "opt_out", "idempotency_key", "course_name", "upcoming_task",
    "upcoming_deadline", "teacher_note",
]
AUDIT_HEADERS = [
    "log_id", "timestamp", "session_id", "agent_type",
    "entity_id", "action", "details", "status",
]
REVIEW_HEADERS = [
    "review_id", "session_id", "agent_type", "entity_id",
    "reason", "context_json", "priority",
    "created_at", "resolved", "resolution", "resolved_at",
]


class ConfigurationError(Exception):
    pass


class SheetsService:
    """
    Wraps gspread. Lazy-connects on first access so the app starts even
    when GOOGLE_SHEETS_URL is not yet set.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = None
        self._spreadsheet = None
        self._worksheets: Dict[str, Any] = {}

    # ── Connection ────────────────────────────────────────────────────────────

    def _ensure_connected(self) -> None:
        if self._client is not None:
            return
        if not self._settings.google_sheets_url:
            raise ConfigurationError(
                "GOOGLE_SHEETS_URL is not set. "
                "Add it to your .env file to enable Google Sheets integration."
            )
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError as e:
            raise ConfigurationError(f"Missing dependency: {e}") from e

        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(
            self._settings.google_sheets_credentials_json, scopes=scopes
        )
        self._client = gspread.authorize(creds)
        self._spreadsheet = self._client.open_by_url(self._settings.google_sheets_url)
        logger.info("Connected to Google Sheets: %s", self._settings.google_sheets_url)

    def is_available(self) -> bool:
        try:
            self._ensure_connected()
            return True
        except Exception:
            return False

    def _get_worksheet(self, tab_name: str, headers: List[str]) -> Any:
        if tab_name in self._worksheets:
            return self._worksheets[tab_name]
        self._ensure_connected()
        try:
            ws = self._spreadsheet.worksheet(tab_name)
        except Exception:
            ws = self._spreadsheet.add_worksheet(tab_name, rows=1000, cols=len(headers))
            ws.append_row(headers)
        self._worksheets[tab_name] = ws
        return ws

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_bool(value) -> bool:
        """Parse Sheets cell value as boolean. Shared by all record parsers."""
        return str(value).lower() in ("true", "1", "yes")

    def _row_to_dict(self, headers: List[str], row: List[Any]) -> Dict[str, Any]:
        padded = row + [""] * (len(headers) - len(row))
        return dict(zip(headers, padded))

    def _find_row_index(self, ws: Any, col_index: int, value: str) -> Optional[int]:
        """Return 1-based row index where column col_index equals value, or None."""
        col_values = ws.col_values(col_index)
        for i, cell in enumerate(col_values):
            if str(cell) == str(value):
                return i + 1  # gspread is 1-indexed
        return None

    def _extract_opt_out_ids(self, rows: List, headers: List[str], id_col_name: str) -> Set[str]:
        """Extract IDs of opted-out entities from a full sheet read. Shared by parent/student."""
        if len(rows) <= 1:
            return set()
        opt_out_col = headers.index("opt_out") if "opt_out" in headers else -1
        id_col = headers.index(id_col_name) if id_col_name in headers else 0
        result = set()
        for row in rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            if opt_out_col >= 0 and self._parse_bool(padded[opt_out_col]):
                result.add(padded[id_col])
        return result

    # ── Parents ───────────────────────────────────────────────────────────────

    def get_parent_by_id(self, parent_id: str) -> Optional[ParentRecord]:
        ws = self._get_worksheet(self._settings.google_sheets_parent_tab, PARENT_HEADERS)
        row_index = self._find_row_index(ws, 1, parent_id)
        if row_index is None:
            return None
        row = ws.row_values(row_index)
        d = self._row_to_dict(PARENT_HEADERS, row)
        d["confidence_score"] = float(d.get("confidence_score") or 0)
        d["opt_out"] = self._parse_bool(d.get("opt_out", ""))
        return ParentRecord(**d)

    def get_all_parents(self) -> List[ParentRecord]:
        ws = self._get_worksheet(self._settings.google_sheets_parent_tab, PARENT_HEADERS)
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []
        headers = rows[0]
        records = []
        for row in rows[1:]:
            d = self._row_to_dict(headers, row)
            if not d.get("parent_id"):
                continue
            d["confidence_score"] = float(d.get("confidence_score") or 0)
            d["opt_out"] = self._parse_bool(d.get("opt_out", ""))
            records.append(ParentRecord(**d))
        return records

    def upsert_parent(self, record: ParentRecord) -> None:
        ws = self._get_worksheet(self._settings.google_sheets_parent_tab, PARENT_HEADERS)
        row = [str(getattr(record, h, "") or "") for h in PARENT_HEADERS]
        row_index = self._find_row_index(ws, 1, record.parent_id)
        if row_index:
            ws.update(f"A{row_index}", [row])
        else:
            ws.append_row(row)

    def get_opt_out_parent_ids(self) -> Set[str]:
        ws = self._get_worksheet(self._settings.google_sheets_parent_tab, PARENT_HEADERS)
        rows = ws.get_all_values()
        return self._extract_opt_out_ids(rows, rows[0] if rows else [], "parent_id")

    # ── Students ──────────────────────────────────────────────────────────────

    def get_student_by_id(self, student_id: str) -> Optional[StudentRecord]:
        ws = self._get_worksheet(self._settings.google_sheets_student_tab, STUDENT_HEADERS)
        row_index = self._find_row_index(ws, 1, student_id)
        if row_index is None:
            return None
        row = ws.row_values(row_index)
        d = self._row_to_dict(STUDENT_HEADERS, row)
        d["attendance_streak"] = int(d.get("attendance_streak") or 0)
        d["opt_out"] = self._parse_bool(d.get("opt_out", ""))
        return StudentRecord(**d)

    def get_all_students(self) -> List[StudentRecord]:
        ws = self._get_worksheet(self._settings.google_sheets_student_tab, STUDENT_HEADERS)
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []
        headers = rows[0]
        records = []
        for row in rows[1:]:
            d = self._row_to_dict(headers, row)
            if not d.get("student_id"):
                continue
            d["attendance_streak"] = int(d.get("attendance_streak") or 0)
            d["opt_out"] = self._parse_bool(d.get("opt_out", ""))
            records.append(StudentRecord(**d))
        return records

    def upsert_student(self, record: StudentRecord) -> None:
        ws = self._get_worksheet(self._settings.google_sheets_student_tab, STUDENT_HEADERS)
        row = [str(getattr(record, h, "") or "") for h in STUDENT_HEADERS]
        row_index = self._find_row_index(ws, 1, record.student_id)
        if row_index:
            ws.update(f"A{row_index}", [row])
        else:
            ws.append_row(row)

    def get_opt_out_student_ids(self) -> Set[str]:
        ws = self._get_worksheet(self._settings.google_sheets_student_tab, STUDENT_HEADERS)
        rows = ws.get_all_values()
        return self._extract_opt_out_ids(rows, rows[0] if rows else [], "student_id")

    # ── Audit Log ─────────────────────────────────────────────────────────────

    def append_audit_log(self, entry: AuditLogEntry) -> None:
        ws = self._get_worksheet(self._settings.google_sheets_audit_tab, AUDIT_HEADERS)
        row = [
            entry.log_id,
            entry.timestamp.isoformat(),
            entry.session_id,
            entry.agent_type,
            entry.entity_id,
            entry.action,
            entry.details,
            entry.status,
        ]
        ws.append_row(row)

    def get_audit_logs(self, session_id: Optional[str] = None) -> List[Dict]:
        ws = self._get_worksheet(self._settings.google_sheets_audit_tab, AUDIT_HEADERS)
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []
        headers = rows[0]
        results = []
        for row in rows[1:]:
            d = self._row_to_dict(headers, row)
            if session_id and d.get("session_id") != session_id:
                continue
            results.append(d)
        return results

    # ── Human Review ──────────────────────────────────────────────────────────

    def append_review_item(self, item: HumanReviewItem) -> None:
        ws = self._get_worksheet(self._settings.google_sheets_review_tab, REVIEW_HEADERS)
        row = [
            item.review_id,
            item.session_id,
            item.agent_type,
            item.entity_id,
            item.reason,
            json.dumps(item.context_snapshot),
            item.priority.value,
            item.created_at.isoformat(),
            str(item.resolved),
            item.resolution or "",
            item.resolved_at.isoformat() if item.resolved_at else "",
        ]
        ws.append_row(row)

    def update_review_resolution(self, review_id: str, resolution: str, resolved_at: str) -> None:
        ws = self._get_worksheet(self._settings.google_sheets_review_tab, REVIEW_HEADERS)
        row_index = self._find_row_index(ws, 1, review_id)
        if row_index:
            ws.update(f"I{row_index}:K{row_index}", [["True", resolution, resolved_at]])

    def get_pending_reviews(self) -> List[Dict]:
        ws = self._get_worksheet(self._settings.google_sheets_review_tab, REVIEW_HEADERS)
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []
        headers = rows[0]
        results = []
        for row in rows[1:]:
            d = self._row_to_dict(headers, row)
            if str(d.get("resolved", "")).lower() not in ("true", "1"):
                results.append(d)
        return results

    # ── Idempotency ───────────────────────────────────────────────────────────

    def idempotency_key_exists(self, tab: str, key: str) -> bool:
        """Check whether an idempotency_key already appears in the given tab."""
        headers_map = {
            self._settings.google_sheets_parent_tab: PARENT_HEADERS,
            self._settings.google_sheets_student_tab: STUDENT_HEADERS,
        }
        headers = headers_map.get(tab, PARENT_HEADERS)
        ws = self._get_worksheet(tab, headers)
        try:
            col_index = headers.index("idempotency_key") + 1
        except ValueError:
            return False
        col_values = ws.col_values(col_index)
        return key in col_values
