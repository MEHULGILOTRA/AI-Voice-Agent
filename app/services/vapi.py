"""
Vapi voice call service.

VAPI_MOCK_MODE=true  → returns a fixture transcript without any real API call.
VAPI_MOCK_MODE=false → calls real Vapi REST API (requires VAPI_API_KEY).

The mock returns a scenario-specific transcript loaded from
tests/test_data/transcripts/{scenario_id}.txt, falling back to a generic one.
"""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from app.config import Settings
from app.core.retry import with_retry

logger = logging.getLogger(__name__)

# Fixtures path (relative to project root)
TRANSCRIPTS_DIR = Path(__file__).parent.parent.parent / "tests" / "test_data" / "transcripts"


class VapiService:
    def __init__(self, settings: Settings):
        self._settings = settings

    @with_retry(max_attempts=3, backoff_base=2)
    def initiate_call(self, parent_record: Dict[str, Any], scenario_id: str = "") -> Dict[str, Any]:
        """
        Initiate a call to a parent.

        Returns a dict with:
          - call_answered (bool)
          - transcript (str) — the full conversation text
          - duration_seconds (int)
        """
        if self._settings.vapi_mock_mode:
            return self._mock_call(parent_record, scenario_id)
        return self._real_call(parent_record)

    def _mock_call(self, parent_record: Dict[str, Any], scenario_id: str) -> Dict[str, Any]:
        transcript_file = TRANSCRIPTS_DIR / f"{scenario_id}.txt"
        if not transcript_file.exists():
            transcript_file = TRANSCRIPTS_DIR / "default.txt"

        if transcript_file.exists():
            transcript = transcript_file.read_text()
        else:
            transcript = self._default_transcript(parent_record)

        # S003 scenario: no answer
        call_answered = scenario_id != "S003"

        logger.info("[MOCK] Vapi call for %s (scenario=%s, answered=%s)",
                    parent_record.get("name"), scenario_id, call_answered)
        return {
            "call_answered": call_answered,
            "transcript": transcript,
            "duration_seconds": 180 if call_answered else 30,
        }

    def _default_transcript(self, parent_record: Dict[str, Any]) -> str:
        name = parent_record.get("name", "Parent")
        return (
            f"Agent: Hello, may I speak with {name}?\n"
            f"{name}: Yes, this is {name} speaking.\n"
            "Agent: Great! I'm calling to confirm some details. "
            "Could I get your email address?\n"
            f"{name}: Sure, it's parent@example.com\n"
            "Agent: And your mobile number?\n"
            f"{name}: It's +1-555-0101\n"
            "Agent: Which school does your child attend?\n"
            f"{name}: Oakwood Elementary\n"
            "Agent: What day and time works best for group sessions?\n"
            f"{name}: Tuesday mornings, around 10:00\n"
            "Agent: Perfect. Any notes we should know?\n"
            f"{name}: No, that's all.\n"
            "Agent: Thank you so much. Have a great day!\n"
        )

    @with_retry(max_attempts=3, backoff_base=2)
    def _real_call(self, parent_record: Dict[str, Any]) -> Dict[str, Any]:
        import httpx
        headers = {
            "Authorization": f"Bearer {self._settings.vapi_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "phoneNumberId": parent_record.get("mobile"),
            "assistantId": os.environ.get("VAPI_ASSISTANT_ID", ""),
            "customer": {"name": parent_record.get("name")},
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post("https://api.vapi.ai/call/phone", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return {
            "call_answered": data.get("status") == "completed",
            "transcript": data.get("transcript", ""),
            "duration_seconds": data.get("duration", 0),
        }
