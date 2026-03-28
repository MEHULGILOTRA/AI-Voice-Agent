"""
Shared fixtures for all tests.

Strategy: all external services are mocked so tests run
fully offline with zero API calls or Sheets connections.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.core.memory import get_memory_saver
from app.core.opt_out import OptOutChecker
from app.core.quiet_hours import QuietHoursChecker
from app.services.audit import AuditService

# ── Load test data ────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent / "test_data"


def load_parents():
    with open(_DATA_DIR / "parents.json") as f:
        return json.load(f)


def load_students():
    with open(_DATA_DIR / "students.json") as f:
        return json.load(f)


def load_scenarios():
    with open(_DATA_DIR / "scenarios.json") as f:
        return json.load(f)


def get_parent(parent_id: str) -> dict:
    for p in load_parents():
        if p["parent_id"] == parent_id:
            return p
    return {}


def get_student(student_id: str) -> dict:
    for s in load_students():
        if s["student_id"] == student_id:
            return s
    return {}


# ── Settings fixture ──────────────────────────────────────────────────────────

@pytest.fixture
def test_settings():
    return Settings(
        google_sheets_url="",
        vapi_mock_mode=True,
        whatsapp_mock_mode=True,
        telegram_mock_mode=True,
        confidence_threshold=0.75,
        quiet_hours_start=21,
        quiet_hours_end=8,
        max_retry_attempts=1,
    )


# ── Service mocks ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_sheets():
    """SheetsService with all methods stubbed to return test data."""
    from app.schemas.parent import ParentRecord
    from app.schemas.student import StudentRecord

    sheets = MagicMock()
    sheets.is_available.return_value = True
    sheets.idempotency_key_exists.return_value = False

    def _get_parent(pid):
        data = get_parent(pid)
        if data:
            data = {k: v for k, v in data.items()}
            return ParentRecord(**data)
        return None

    def _get_student(sid):
        data = get_student(sid)
        if data:
            return StudentRecord(**data)
        return None

    sheets.get_parent_by_id.side_effect = _get_parent
    sheets.get_student_by_id.side_effect = _get_student
    sheets.get_all_parents.return_value = [
        ParentRecord(**p) for p in load_parents()
    ]
    sheets.get_all_students.return_value = [
        StudentRecord(**s) for s in load_students()
    ]
    sheets.get_opt_out_parent_ids.return_value = {"P010"}
    sheets.get_opt_out_student_ids.return_value = {"ST010"}
    sheets.upsert_parent.return_value = None
    sheets.upsert_student.return_value = None
    sheets.append_audit_log.return_value = None
    sheets.append_review_item.return_value = None
    sheets.update_review_resolution.return_value = None

    return sheets


@pytest.fixture
def mock_vapi(test_settings):
    from app.services.vapi import VapiService
    svc = VapiService(test_settings)
    return svc  # already in mock mode


@pytest.fixture
def mock_whatsapp(test_settings):
    from app.services.whatsapp import WhatsAppService
    svc = WhatsAppService(test_settings)
    return svc  # already in mock mode


@pytest.fixture
def mock_telegram(test_settings):
    from app.services.telegram_client import TelegramClient
    svc = TelegramClient(test_settings)
    return svc  # already in mock mode


@pytest.fixture
def audit_service():
    return AuditService(None)  # in-memory only


@pytest.fixture
def opt_out_checker_empty():
    checker = OptOutChecker()
    checker.warm(set())
    return checker


@pytest.fixture
def opt_out_checker_with_p010():
    checker = OptOutChecker()
    checker.warm({"P010"})
    return checker


@pytest.fixture
def quiet_checker_inactive():
    """Returns a checker that always says it is NOT quiet hours."""
    class _AlwaysActive(QuietHoursChecker):
        def is_quiet_time(self, tz=None):
            return False
    return _AlwaysActive(21, 8)


@pytest.fixture
def quiet_checker_active():
    """Returns a checker that always says it IS quiet hours."""
    class _AlwaysQuiet(QuietHoursChecker):
        def is_quiet_time(self, tz=None):
            return True
    return _AlwaysQuiet(21, 8)


@pytest.fixture
def no_op_idempotency():
    class _NoOp:
        def is_duplicate(self, *a, **kw):
            return False
    return _NoOp()


# ── Graph fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def outreach_graph(
    mock_sheets,
    mock_vapi,
    mock_whatsapp,
    audit_service,
    opt_out_checker_empty,
    quiet_checker_inactive,
    no_op_idempotency,
    test_settings,
):
    from app.agents.outreach.graph import build_outreach_graph
    memory = get_memory_saver()
    return build_outreach_graph(
        memory=memory,
        sheets_service=mock_sheets,
        vapi_service=mock_vapi,
        whatsapp_service=mock_whatsapp,
        audit_service=audit_service,
        opt_out_checker=opt_out_checker_empty,
        quiet_checker=quiet_checker_inactive,
        idempotency_checker=no_op_idempotency,
        settings=test_settings,
    )


@pytest.fixture
def telegram_graph(
    mock_sheets,
    mock_telegram,
    audit_service,
    opt_out_checker_empty,
    quiet_checker_inactive,
    no_op_idempotency,
    test_settings,
):
    from app.agents.telegram.graph import build_telegram_graph
    memory = get_memory_saver()
    return build_telegram_graph(
        memory=memory,
        sheets_service=mock_sheets,
        telegram_client=mock_telegram,
        audit_service=audit_service,
        opt_out_checker=opt_out_checker_empty,
        quiet_checker=quiet_checker_inactive,
        idempotency_checker=no_op_idempotency,
        settings=test_settings,
    )


# ── FastAPI test client ───────────────────────────────────────────────────────

@pytest.fixture
def test_app(
    outreach_graph,
    telegram_graph,
    mock_sheets,
    audit_service,
):
    from app.main import create_app
    from app.agents.shared.review_queue import ReviewQueue

    application = create_app()

    # Override app.state directly (bypass lifespan)
    application.state.sheets = mock_sheets
    application.state.outreach_graph = outreach_graph
    application.state.telegram_graph = telegram_graph
    application.state.audit_service = audit_service
    application.state.review_queue = ReviewQueue(None)

    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
