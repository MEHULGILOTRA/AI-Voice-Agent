"""
U06 — Same idempotency key checked twice → second returns duplicate=True
"""
import pytest
from unittest.mock import MagicMock
from app.core.idempotency import IdempotencyChecker, make_idempotency_key


def test_duplicate_key_detected():
    """U06: Sheets returns True for already-seen key."""
    sheets = MagicMock()
    sheets.idempotency_key_exists.return_value = True

    checker = IdempotencyChecker(sheets)
    result = checker.is_duplicate("P001", "outreach", "Parents")
    assert result is True


def test_new_key_allowed():
    sheets = MagicMock()
    sheets.idempotency_key_exists.return_value = False

    checker = IdempotencyChecker(sheets)
    result = checker.is_duplicate("P001", "outreach", "Parents")
    assert result is False


def test_sheets_error_defaults_to_allow():
    """If Sheets is unavailable, default to False (allow the operation)."""
    sheets = MagicMock()
    sheets.idempotency_key_exists.side_effect = Exception("connection error")

    checker = IdempotencyChecker(sheets)
    result = checker.is_duplicate("P001", "outreach", "Parents")
    assert result is False


def test_key_format_is_deterministic():
    from datetime import date
    k1 = make_idempotency_key("P001", "outreach", date(2026, 3, 26))
    k2 = make_idempotency_key("P001", "outreach", date(2026, 3, 26))
    assert k1 == k2
    assert len(k1) == 16


def test_different_entities_have_different_keys():
    from datetime import date
    k1 = make_idempotency_key("P001", "outreach", date(2026, 3, 26))
    k2 = make_idempotency_key("P002", "outreach", date(2026, 3, 26))
    assert k1 != k2
