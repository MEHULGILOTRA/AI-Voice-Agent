"""
Opt-out suppression.

Opt-out entity IDs are loaded from Google Sheets into an in-memory set at
app startup and refreshed periodically. All checks are O(1) set lookups.
"""
import logging
from typing import Set, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.sheets import SheetsService

logger = logging.getLogger(__name__)


class OptOutChecker:
    """
    Maintains an in-memory set of opted-out entity IDs (parents and students).
    Call warm() at startup and refresh() periodically to keep in sync with Sheets.
    """

    def __init__(self):
        self._opted_out: Set[str] = set()

    def warm(self, entity_ids: Set[str]) -> None:
        """Load the full opt-out set (called at startup)."""
        self._opted_out = entity_ids
        logger.info("OptOutChecker warmed with %d entries", len(entity_ids))

    def add(self, entity_id: str) -> None:
        """Mark an entity as opted out (called when they opt out during a session)."""
        self._opted_out.add(entity_id)

    def is_opted_out(self, entity_id: str) -> bool:
        return entity_id in self._opted_out

    def refresh(self, entity_ids: Set[str]) -> None:
        self._opted_out = entity_ids


# Module-level singleton shared across both agents
_parent_checker = OptOutChecker()
_student_checker = OptOutChecker()


def get_parent_opt_out_checker() -> OptOutChecker:
    return _parent_checker


def get_student_opt_out_checker() -> OptOutChecker:
    return _student_checker
