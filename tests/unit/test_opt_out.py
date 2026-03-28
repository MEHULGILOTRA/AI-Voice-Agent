"""
U05 — Parent with opt_out=True is blocked
"""
import pytest
from app.core.opt_out import OptOutChecker


def test_opted_out_parent_blocked():
    """U05: Entity in opt-out set returns True."""
    checker = OptOutChecker()
    checker.warm({"P010", "P004"})
    assert checker.is_opted_out("P010") is True


def test_active_parent_allowed():
    checker = OptOutChecker()
    checker.warm({"P010"})
    assert checker.is_opted_out("P001") is False


def test_add_then_check():
    checker = OptOutChecker()
    checker.warm(set())
    checker.add("P999")
    assert checker.is_opted_out("P999") is True


def test_refresh_replaces_set():
    checker = OptOutChecker()
    checker.warm({"P001"})
    checker.refresh({"P002"})
    assert checker.is_opted_out("P001") is False
    assert checker.is_opted_out("P002") is True
