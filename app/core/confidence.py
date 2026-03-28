"""
Confidence scoring for parent outreach records.

Purely rule-based: weighted sum of field completeness + format validity.
No LLM call. The threshold for triggering human review is configurable
via the CONFIDENCE_THRESHOLD env var.
"""
import re
from typing import Any, Dict


# Weights must sum to 1.0
FIELD_WEIGHTS: Dict[str, float] = {
    "email": 0.25,
    "mobile": 0.25,
    "school_name": 0.20,
    "preferred_weekday": 0.15,
    "preferred_time": 0.15,
}

VALID_WEEKDAYS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
}


def _is_valid_email(value: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value.strip()))


def _is_valid_mobile(value: str) -> bool:
    # Accepts international and local formats: +1-555-0101, 5550101, +44 7911 123456
    return bool(re.match(r"^\+?[\d\s\-\(\)]{7,20}$", value.strip()))


def _is_valid_weekday(value: str) -> bool:
    return value.strip().lower() in VALID_WEEKDAYS


def _is_valid_time(value: str) -> bool:
    # HH:MM 24h format
    return bool(re.match(r"^([01]\d|2[0-3]):[0-5]\d$", value.strip()))


VALIDATORS = {
    "email": _is_valid_email,
    "mobile": _is_valid_mobile,
    "preferred_weekday": _is_valid_weekday,
    "preferred_time": _is_valid_time,
    "school_name": lambda v: bool(v and len(v.strip()) >= 2),
}


def score_outreach(captured: Dict[str, Any]) -> float:
    """
    Score a dict of captured outreach fields.

    ``captured`` keys: email, mobile, school_name, preferred_weekday, preferred_time.
    Returns a float in [0.0, 1.0].
    """
    total = 0.0
    for field, weight in FIELD_WEIGHTS.items():
        value = captured.get(field)
        if value and isinstance(value, str):
            validator = VALIDATORS.get(field, lambda v: bool(v))
            if validator(value):
                total += weight
    return round(total, 2)
