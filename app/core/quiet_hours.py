"""
Quiet hours / do-not-disturb check.

No LLM involved — pure datetime comparison.
"""
from datetime import datetime
from typing import Optional

import pytz


class QuietHoursChecker:
    """
    Returns True if the current local time falls inside the configured quiet window.

    Config is driven by QUIET_HOURS_START and QUIET_HOURS_END env vars.
    start_hour and end_hour are 24h integers (e.g. 21 = 9 PM, 8 = 8 AM).
    Handles windows that span midnight (e.g. 21 → 8).
    """

    def __init__(self, start_hour: int, end_hour: int):
        self.start_hour = start_hour
        self.end_hour = end_hour

    def is_quiet_time(self, entity_timezone: Optional[str] = None) -> bool:
        tz = pytz.timezone(entity_timezone or "UTC")
        now = datetime.now(tz)
        hour = now.hour
        if self.start_hour > self.end_hour:  # window spans midnight
            return hour >= self.start_hour or hour < self.end_hour
        return self.start_hour <= hour < self.end_hour
