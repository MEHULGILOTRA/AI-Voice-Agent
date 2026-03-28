"""
U03 — 22:00 local time → is_quiet_time() returns True
U04 — 10:00 local time → is_quiet_time() returns False
"""
from unittest.mock import patch
from datetime import datetime

import pytz
import pytest

from app.core.quiet_hours import QuietHoursChecker


def _mock_now(hour: int, tz_name: str = "UTC"):
    tz = pytz.timezone(tz_name)
    return datetime(2026, 3, 26, hour, 0, 0, tzinfo=tz)


def test_quiet_during_night():
    """U03: 22:00 falls in quiet window (21–8)."""
    checker = QuietHoursChecker(start_hour=21, end_hour=8)
    with patch("app.core.quiet_hours.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(22)
        assert checker.is_quiet_time() is True


def test_active_during_day():
    """U04: 10:00 is outside quiet window (21–8)."""
    checker = QuietHoursChecker(start_hour=21, end_hour=8)
    with patch("app.core.quiet_hours.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(10)
        assert checker.is_quiet_time() is False


def test_boundary_start():
    """21:00 exactly is still quiet."""
    checker = QuietHoursChecker(start_hour=21, end_hour=8)
    with patch("app.core.quiet_hours.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(21)
        assert checker.is_quiet_time() is True


def test_boundary_end():
    """08:00 exactly is no longer quiet."""
    checker = QuietHoursChecker(start_hour=21, end_hour=8)
    with patch("app.core.quiet_hours.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(8)
        assert checker.is_quiet_time() is False


def test_midnight_in_window():
    """00:00 should be quiet (window spans midnight)."""
    checker = QuietHoursChecker(start_hour=21, end_hour=8)
    with patch("app.core.quiet_hours.datetime") as mock_dt:
        mock_dt.now.return_value = _mock_now(0)
        assert checker.is_quiet_time() is True
