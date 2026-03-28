"""
Shared fixture loading for test/demo data.

Both graph builders and API endpoints need access to the same JSON test data.
Centralised here to eliminate duplication.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

_TEST_DATA_DIR = Path(__file__).parent.parent.parent / "tests" / "test_data"


@lru_cache(maxsize=1)
def load_parents_fixture() -> List[Dict]:
    path = _TEST_DATA_DIR / "parents.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


@lru_cache(maxsize=1)
def load_students_fixture() -> List[Dict]:
    path = _TEST_DATA_DIR / "students.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def get_parent_from_fixture(parent_id: str) -> Optional[Dict]:
    for p in load_parents_fixture():
        if p.get("parent_id") == parent_id:
            return p
    return None


def get_student_from_fixture(student_id: str) -> Optional[Dict]:
    for s in load_students_fixture():
        if s.get("student_id") == student_id:
            return s
    return None
