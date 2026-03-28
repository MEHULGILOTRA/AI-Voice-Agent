"""
Telegram Bot API client.

TELEGRAM_MOCK_MODE=true  → logs the message, no real send.
TELEGRAM_MOCK_MODE=false → sends via Bot API (requires TELEGRAM_BOT_TOKEN).
"""
import logging
from typing import Any, Dict

from app.config import Settings
from app.core.retry import with_retry

logger = logging.getLogger(__name__)


class TelegramClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    @with_retry(max_attempts=3, backoff_base=2)
    def send_message(self, chat_id: str, text: str) -> Dict[str, Any]:
        if self._settings.telegram_mock_mode:
            logger.info("[MOCK] Telegram → chat_id=%s: %s", chat_id, text[:120])
            return {"ok": True, "chat_id": chat_id, "text": text}
        return self._real_send(chat_id, text)

    @with_retry(max_attempts=3, backoff_base=2)
    def _real_send(self, chat_id: str, text: str) -> Dict[str, Any]:
        import httpx
        url = f"https://api.telegram.org/bot{self._settings.telegram_bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
