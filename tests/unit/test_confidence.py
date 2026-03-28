"""
U01 — All 5 fields present → confidence ≥ 0.95
U02 — Missing email → score drops by 0.25
"""
import pytest
from app.core.confidence import score_outreach


def full_data():
    return {
        "email": "test@example.com",
        "mobile": "+1-555-0101",
        "school_name": "Oakwood Elementary",
        "preferred_weekday": "Tuesday",
        "preferred_time": "10:00",
    }


def test_full_data_scores_high():
    """U01: All 5 valid fields → score == 1.0"""
    score = score_outreach(full_data())
    assert score >= 0.95


def test_missing_email_reduces_score():
    """U02: Remove email (weight 0.25) → score drops by 0.25"""
    data = full_data()
    score_with = score_outreach(data)
    del data["email"]
    score_without = score_outreach(data)
    assert abs((score_with - score_without) - 0.25) < 0.01


def test_empty_dict_scores_zero():
    assert score_outreach({}) == 0.0


def test_invalid_email_not_counted():
    data = full_data()
    data["email"] = "notanemail"
    score = score_outreach(data)
    assert score < score_outreach(full_data())


def test_invalid_mobile_not_counted():
    data = full_data()
    data["mobile"] = "abc"
    score = score_outreach(data)
    assert score < score_outreach(full_data())


def test_score_is_float_in_range():
    score = score_outreach(full_data())
    assert 0.0 <= score <= 1.0


# ── Parametrized field combination tests ────────────────────────────────────

@pytest.mark.parametrize("fields,expected_score", [
    # All fields valid
    ({"email": "a@b.com", "mobile": "+1-555-0101", "school_name": "School", "preferred_weekday": "Monday", "preferred_time": "10:00"}, 1.0),
    # No fields
    ({}, 0.0),
    # Only email + mobile (0.25 + 0.25 = 0.50)
    ({"email": "a@b.com", "mobile": "+1-555-0101"}, 0.50),
    # Only school + weekday + time (0.20 + 0.15 + 0.15 = 0.50)
    ({"school_name": "School", "preferred_weekday": "Wednesday", "preferred_time": "15:00"}, 0.50),
    # All fields present but email invalid
    ({"email": "bad", "mobile": "+1-555-0101", "school_name": "School", "preferred_weekday": "Tuesday", "preferred_time": "10:00"}, 0.75),
    # Single field only — email
    ({"email": "test@example.com"}, 0.25),
    # Single field only — mobile
    ({"mobile": "+44-7700-900000"}, 0.25),
])
def test_parametrized_scoring(fields, expected_score):
    score = score_outreach(fields)
    assert abs(score - expected_score) < 0.01, f"Expected {expected_score}, got {score}"
