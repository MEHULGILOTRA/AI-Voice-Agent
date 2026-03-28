"""
FastAPI application factory.

Startup sequence:
1. Initialise SheetsService (lazy — won't fail if URL not set)
2. Warm opt-out caches from Sheets (best-effort)
3. Build LangGraph graphs with shared MemorySaver
4. Start session TTL pruning background task

All state is stored on app.state for easy access in endpoints and tests.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.core.memory import get_memory_saver, prune_expired_sessions
from app.core.opt_out import get_parent_opt_out_checker, get_student_opt_out_checker
from app.agents.outreach.graph import build_outreach_graph
from app.agents.telegram.graph import build_telegram_graph
from app.agents.shared.review_queue import get_review_queue
from app.api.v1 import health, outreach, telegram, review
from app.services.audit import AuditService
from app.services.sheets import SheetsService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # ── Services ──────────────────────────────────────────────────────────────
    sheets = SheetsService(settings)
    app.state.sheets = sheets

    # ── Warm opt-out caches ───────────────────────────────────────────────────
    if sheets.is_available():
        try:
            parent_ids = sheets.get_opt_out_parent_ids()
            get_parent_opt_out_checker().warm(parent_ids)
            student_ids = sheets.get_opt_out_student_ids()
            get_student_opt_out_checker().warm(student_ids)
            logger.info("Opt-out caches warmed from Sheets")
        except Exception as e:
            logger.warning("Could not warm opt-out caches: %s", e)
    else:
        logger.info("Sheets not configured — opt-out caches empty (dev mode)")

    # ── Audit service ─────────────────────────────────────────────────────────
    audit_service = AuditService(sheets if sheets.is_available() else None)
    app.state.audit_service = audit_service

    # ── Review queue ──────────────────────────────────────────────────────────
    review_queue = get_review_queue(sheets if sheets.is_available() else None)
    app.state.review_queue = review_queue

    # ── LangGraph graphs ──────────────────────────────────────────────────────
    memory = get_memory_saver()
    sheets_arg = sheets if sheets.is_available() else None

    app.state.outreach_graph = build_outreach_graph(
        memory=memory,
        sheets_service=sheets_arg,
        audit_service=audit_service,
        settings=settings,
    )
    app.state.telegram_graph = build_telegram_graph(
        memory=memory,
        sheets_service=sheets_arg,
        audit_service=audit_service,
        settings=settings,
    )
    logger.info("Graphs initialised")

    # ── Background task: prune old sessions ──────────────────────────────────
    task = asyncio.create_task(
        prune_expired_sessions(settings.session_ttl_seconds)
    )

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agentic AI Bot",
        description=(
            "Parent outreach and student messaging agent. "
            "Google Sheets as data layer. Human-in-the-loop via LangGraph interrupt()."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(outreach.router, prefix="/api/v1/outreach", tags=["outreach"])
    app.include_router(telegram.router, prefix="/api/v1/telegram", tags=["telegram"])
    app.include_router(review.router, prefix="/api/v1/review", tags=["review"])

    return app


app = create_app()
