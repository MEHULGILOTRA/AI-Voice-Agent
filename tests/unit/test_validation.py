"""
U07 — Malformed email string fails validation
Additional coverage for mobile, weekday, and time validators.
"""
import pytest
from app.core.confidence import (
    _is_valid_email,
    _is_valid_mobile,
    _is_valid_weekday,
    _is_valid_time,
)


def test_invalid_email_rejected():
    """U07: 'notanemail' fails email regex."""
    assert _is_valid_email("notanemail") is False


def test_valid_email_accepted():
    assert _is_valid_email("sarah@example.com") is True
    assert _is_valid_email("user.name+tag@domain.co.uk") is True


def test_invalid_mobile_rejected():
    assert _is_valid_mobile("abc") is False
    assert _is_valid_mobile("12") is False  # too short


def test_valid_mobile_accepted():
    assert _is_valid_mobile("+1-555-0101") is True
    assert _is_valid_mobile("+44 7911 123456") is True
    assert _is_valid_mobile("5550101") is True


def test_invalid_weekday_rejected():
    assert _is_valid_weekday("Someday") is False
    assert _is_valid_weekday("Tues") is False


def test_valid_weekday_accepted():
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
        assert _is_valid_weekday(day) is True
    assert _is_valid_weekday("monday") is True  # case-insensitive


def test_invalid_time_rejected():
    assert _is_valid_time("25:00") is False
    assert _is_valid_time("10") is False
    assert _is_valid_time("morning") is False


def test_valid_time_accepted():
    assert _is_valid_time("10:00") is True
    assert _is_valid_time("14:30") is True
    assert _is_valid_time("00:00") is True
