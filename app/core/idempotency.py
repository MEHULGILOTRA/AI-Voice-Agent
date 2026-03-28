"""
Idempotency key generation and duplicate-check.

A key is SHA256(entity_id + ":" + action + ":" + date_str).
Before any write, call IdempotencyChecker.is_duplicate().
If True, skip the write — the operation already happened today.
"""
import hashlib
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.sheets import SheetsService


def make_idempotency_key(entity_id: str, action: str, for_date: date | None = None) -> str:
    """Return a short deterministic key for the given entity + action + date."""
    day = (for_date or date.today()).isoformat()
    raw = f"{entity_id}:{action}:{day}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class IdempotencyChecker:
    """
    Checks whether an (entity_id, action, date) triple has already been processed.

    Backed by Google Sheets: looks up the idempotency_key column in the given tab.
    Falls back to False (allow the operation) if Sheets is unavailable.
    """

    def __init__(self, sheets_service: "SheetsService"):
        self._sheets = sheets_service

    def is_duplicate(self, entity_id: str, action: str, tab: str) -> bool:
        key = make_idempotency_key(entity_id, action)
        try:
            return self._sheets.idempotency_key_exists(tab, key)
        except Exception:
            return False  # safe default: allow the operation
