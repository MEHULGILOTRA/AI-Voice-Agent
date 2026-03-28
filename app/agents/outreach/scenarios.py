"""
Loads the 5 demo scenarios from tests/test_data/scenarios.json.
This keeps scenario config as data, not hardcoded logic.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

_SCENARIOS_FILE = Path(__file__).parent.parent.parent.parent / "tests" / "test_data" / "scenarios.json"


@lru_cache(maxsize=1)
def _load() -> Dict[str, Dict]:
    with open(_SCENARIOS_FILE) as f:
        scenarios = json.load(f)
    return {s["scenario_id"]: s for s in scenarios}


def get_all_scenarios() -> List[Dict]:
    return list(_load().values())


def get_scenario(scenario_id: str) -> Optional[Dict]:
    return _load().get(scenario_id)
