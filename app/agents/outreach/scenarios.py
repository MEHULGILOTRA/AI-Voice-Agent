"""
Loads the 5 demo scenarios from tests/test_data/scenarios.json.
This keeps scenario config as data, not hardcoded logic.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

_SCENARIOS_FILE = Path(__file__).parent.parent.parent.parent / "tests" / "test_data" / "scenarios.json"

_scenarios: Optional[List[Dict]] = None


def _load() -> List[Dict]:
    global _scenarios
    if _scenarios is None:
        with open(_SCENARIOS_FILE) as f:
            _scenarios = json.load(f)
    return _scenarios


def get_all_scenarios() -> List[Dict]:
    return _load()


def get_scenario(scenario_id: str) -> Optional[Dict]:
    for s in _load():
        if s["scenario_id"] == scenario_id:
            return s
    return None
