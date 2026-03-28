"""
Outreach LangGraph graph.

build_outreach_graph() returns a compiled graph that can be invoked with:

    config = {"configurable": {"thread_id": session_id}}
    result = graph.invoke(initial_state, config=config)

Human-in-the-loop:
    When score_confidence detects low confidence, interrupt() pauses execution.
    Resume with:
        graph.invoke(Command(resume=corrected_data), config=config)
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.outreach import nodes
from app.agents.outreach.state import OutreachState
from app.agents.shared.utils import get_idempotency_checker

logger = logging.getLogger(__name__)

_PARENTS_FILE = Path(__file__).parent.parent.parent.parent / "tests" / "test_data" / "parents.json"


def _load_parent_record(parent_id: str) -> Dict[str, Any]:
    """Load a parent record from test data (used when Sheets is not configured)."""
    if _PARENTS_FILE.exists():
        with open(_PARENTS_FILE) as f:
            parents = json.load(f)
        for p in parents:
            if p["parent_id"] == parent_id:
                return p
    return {"parent_id": parent_id, "name": "Unknown", "mobile": ""}


def build_outreach_graph(
    memory: MemorySaver,
    sheets_service=None,
    vapi_service=None,
    whatsapp_service=None,
    audit_service=None,
    llm=None,
    opt_out_checker=None,
    quiet_checker=None,
    idempotency_checker=None,
    settings=None,
):
    """
    Returns a compiled outreach graph with all dependencies injected.
    All services are resolved at build time (not per-invocation) for efficiency.
    """
    from app.config import get_settings
    from app.core.opt_out import get_parent_opt_out_checker
    from app.core.quiet_hours import QuietHoursChecker
    from app.services.audit import AuditService
    from app.services.vapi import VapiService
    from app.services.whatsapp import WhatsAppService
    from app.agents.shared.llm import get_llm

    _settings = settings or get_settings()
    _opt_out = opt_out_checker or get_parent_opt_out_checker()
    _quiet = quiet_checker or QuietHoursChecker(
        _settings.quiet_hours_start, _settings.quiet_hours_end
    )
    _audit = audit_service or AuditService(sheets_service)
    _idempotency = get_idempotency_checker(sheets_service, idempotency_checker)

    # Resolve services once at build time
    _vapi = vapi_service or VapiService(_settings)
    _wa = whatsapp_service or WhatsAppService(_settings)
    _llm = llm or (get_llm(_settings) if _settings.openai_api_key else None)

    def _get_parent_dict(parent_id: str) -> Dict[str, Any]:
        if sheets_service:
            record = sheets_service.get_parent_by_id(parent_id)
            return record.model_dump() if record else {}
        return _load_parent_record(parent_id)

    # ── Node closures ─────────────────────────────────────────────────────────
    def _validate(state):
        return nodes.validate_request(state, _opt_out, _quiet, _idempotency, _settings)

    def _initiate_call(state):
        return nodes.initiate_call(state, _vapi, _get_parent_dict(state["parent_id"]))

    def _conduct(state):
        return nodes.conduct_conversation(state, _llm)

    def _extract(state):
        return nodes.extract_data(state)

    def _score(state):
        return nodes.score_confidence(state, _settings)

    def _write(state):
        if sheets_service is None:
            logger.warning("No SheetsService — skipping Sheets write")
            return {"sheets_written": False, "audit_trail": state.get("audit_trail", [])}
        return nodes.write_to_sheets(state, sheets_service, _settings)

    def _whatsapp(state):
        return nodes.send_whatsapp(state, _wa, _get_parent_dict(state["parent_id"]))

    def _audit_node(state):
        return nodes.finalize_audit(state, _audit)

    # ── Build graph ───────────────────────────────────────────────────────────
    builder = StateGraph(OutreachState)
    builder.add_node("validate_request", _validate)
    builder.add_node("initiate_call", _initiate_call)
    builder.add_node("conduct_conversation", _conduct)
    builder.add_node("extract_data", _extract)
    builder.add_node("score_confidence", _score)
    builder.add_node("write_to_sheets", _write)
    builder.add_node("send_whatsapp", _whatsapp)
    builder.add_node("finalize_audit", _audit_node)

    builder.add_edge(START, "validate_request")
    builder.add_conditional_edges("validate_request", nodes.route_after_validation)
    builder.add_conditional_edges("initiate_call", nodes.route_after_call)
    builder.add_edge("conduct_conversation", "extract_data")
    builder.add_conditional_edges("extract_data", nodes.route_after_extraction)
    builder.add_conditional_edges("score_confidence", nodes.route_after_scoring)
    builder.add_edge("write_to_sheets", "finalize_audit")
    builder.add_edge("send_whatsapp", "finalize_audit")
    builder.add_edge("finalize_audit", END)

    return builder.compile(checkpointer=memory)
