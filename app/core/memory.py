"""
LangGraph MemorySaver singleton.

Both agents share one MemorySaver instance.
Thread IDs are namespaced: "outreach:{uuid}" / "telegram:{uuid}".

A background task (started in app lifespan) prunes sessions older than
SESSION_TTL_SECONDS to prevent unbounded memory growth.
"""
import asyncio
import logging
import time
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

_memory_saver: Optional[MemorySaver] = None
# Track session creation times: {thread_id: created_at_epoch}
_session_registry: dict[str, float] = {}


def get_memory_saver() -> MemorySaver:
    global _memory_saver
    if _memory_saver is None:
        _memory_saver = MemorySaver()
        logger.info("MemorySaver initialised")
    return _memory_saver


def register_session(thread_id: str) -> None:
    _session_registry[thread_id] = time.time()


def session_thread_id(agent_type: str, session_id: str) -> str:
    """Namespaced thread ID to prevent collisions between agent types."""
    return f"{agent_type}:{session_id}"


async def prune_expired_sessions(ttl_seconds: int, interval_seconds: int = 600) -> None:
    """Background coroutine: removes stale thread IDs from the registry."""
    while True:
        await asyncio.sleep(interval_seconds)
        now = time.time()
        expired = [
            tid for tid, created in list(_session_registry.items())
            if now - created > ttl_seconds
        ]
        for tid in expired:
            _session_registry.pop(tid, None)
        if expired:
            logger.info("Pruned %d expired sessions", len(expired))
