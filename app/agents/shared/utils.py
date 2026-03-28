"""
Shared utilities used by both outreach and telegram agent nodes.
"""
from typing import Any, Dict, List


def append_trail(state: Dict[str, Any], msg: str) -> list:
    """Append a message to the audit trail in state. Shared by both agents."""
    return state.get("audit_trail", []) + [msg]


def extract_transcript(messages: List) -> str:
    """Concatenate LangChain message content into a single transcript string."""
    return "\n".join(
        msg.content for msg in messages
        if hasattr(msg, "content") and msg.content
    )


class NoOpIdempotency:
    """
    Fallback idempotency checker used when Google Sheets is not configured.
    Always returns False (allow all operations). Safe for dev/testing.
    """
    def is_duplicate(self, *args, **kwargs) -> bool:
        return False


def get_idempotency_checker(sheets_service, provided_checker=None):
    """
    Factory: returns the right idempotency checker given available dependencies.
    Shared by both graph builders to avoid duplicated logic.
    """
    if provided_checker is not None:
        return provided_checker
    if sheets_service:
        from app.core.idempotency import IdempotencyChecker
        return IdempotencyChecker(sheets_service)
    return NoOpIdempotency()
