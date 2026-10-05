"""Общие фикстуры на основе синтетического расписания из sample.py."""

from typing import Any

import pytest

from miet_scheduler.models import Schedule
from miet_scheduler.semester import Semester

from .sample import ENTRIES, SEMESTER_TITLE, TIMES


@pytest.fixture
def payload() -> dict[str, Any]:
    return {"Times": TIMES, "Data": list(ENTRIES), "Semestr": SEMESTER_TITLE}


@pytest.fixture
def schedule(payload: dict[str, Any]) -> Schedule:
    return Schedule.from_api(payload)


@pytest.fixture
def semester() -> Semester:
    return Semester.from_title(SEMESTER_TITLE)
