"""
WhatsApp messaging service (Twilio or compatible).

WHATSAPP_MOCK_MODE=true  → logs the message, no real send.
WHATSAPP_MOCK_MODE=false → sends via Twilio REST API.
"""
import logging
from typing import Any, Dict

from app.config import Settings
from app.core.retry import with_retry

logger = logging.getLogger(__name__)

FOLLOWUP_TEMPLATE = (
    "Hi {name}! We tried to reach you by phone to confirm some details "
    "before your child's group session. Could you please call us back or "
    "reply here with:\n"
    "• Your email\n"
    "• Preferred day & time\n"
    "• Your child's school name\n\n"
    "Thank you!"
)


class WhatsAppService:
    def __init__(self, settings: Settings):
        self._settings = settings

    @with_retry(max_attempts=3, backoff_base=2)
    def send_followup(self, parent_record: Dict[str, Any]) -> Dict[str, Any]:
        """Send a missed-call follow-up WhatsApp message."""
        message = FOLLOWUP_TEMPLATE.format(name=parent_record.get("name", "there"))
        to_number = parent_record.get("mobile", "")

        if self._settings.whatsapp_mock_mode:
            logger.info(
                "[MOCK] WhatsApp → %s (%s): %s",
                parent_record.get("name"), to_number, message[:80]
            )
            return {"status": "sent", "message": message, "to": to_number}

        return self._real_send(to_number, message)

    @with_retry(max_attempts=3, backoff_base=2)
    def _real_send(self, to_number: str, message: str) -> Dict[str, Any]:
        import httpx
        auth = (
            self._settings.whatsapp_api_key.split(":")[0],
            self._settings.whatsapp_api_key.split(":")[1]
            if ":" in self._settings.whatsapp_api_key else "",
        )
        payload = {
            "From": self._settings.whatsapp_from_number,
            "To": f"whatsapp:{to_number}",
            "Body": message,
        }
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                "https://api.twilio.com/2010-04-01/Accounts/"
                f"{auth[0]}/Messages.json",
                auth=auth,
                data=payload,
            )
            resp.raise_for_status()
        return {"status": "sent", "message": message, "to": to_number}
