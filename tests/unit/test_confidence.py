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
