import datetime
from itertools import pairwise

import pytest

from miet_scheduler.semester import WEEK_NAMES, Semester

from .sample import expected_dates

D = datetime.date


@pytest.mark.parametrize(
    ("title", "start", "end"),
    [
        ("Осенний семестр 2026/2027", D(2026, 9, 1), D(2026, 12, 31)),
        ("Весенний семестр 2026/2027", D(2027, 2, 1), D(2027, 5, 31)),
        ("ОСЕННИЙ СЕМЕСТР 2024/2025", D(2024, 9, 1), D(2024, 12, 31)),
    ],
)
def test_from_title(title: str, start: D, end: D) -> None:
    semester = Semester.from_title(title)
    assert (semester.start, semester.end) == (start, end)
    assert semester.title == title


@pytest.mark.parametrize("title", ["Летний семестр 2026/2027", "Осенний семестр"])
def test_from_title_rejects_unknown_format(title: str) -> None:
    with pytest.raises(ValueError):
        Semester.from_title(title)


@pytest.mark.parametrize(
    ("start", "anchor"),
    [
        (D(2026, 9, 1), D(2026, 8, 31)),  # вторник → понедельник той же недели
        (D(2025, 9, 1), D(2025, 9, 1)),  # понедельник
        (D(2025, 2, 1), D(2025, 1, 27)),  # суббота — рабочий день
        (D(2024, 9, 1), D(2024, 9, 2)),  # воскресенье → следующий понедельник
        (D(2026, 2, 1), D(2026, 2, 2)),  # воскресенье → следующий понедельник
    ],
)
def test_anchor_is_week_of_first_workday(start: D, anchor: D) -> None:
    semester = Semester("", start, start + datetime.timedelta(days=120))
    assert semester.anchor == anchor
    assert semester.anchor.isoweekday() == 1


@pytest.mark.parametrize(
    "start", [D(2026, 9, 1), D(2025, 9, 1), D(2025, 2, 1), D(2024, 9, 1), D(2026, 2, 1)]
)
def test_first_workday_is_first_numerator(start: D) -> None:
    semester = Semester("", start, start + datetime.timedelta(days=120))
    first_workday = start if start.isoweekday() != 7 else start + datetime.timedelta(1)
    assert semester.week_of(first_workday) == 0
    assert WEEK_NAMES[semester.week_of(first_workday)] == "1 числитель"


@pytest.mark.parametrize(
    "semester",
    [
        Semester.from_title("Осенний семестр 2026/2027"),
        Semester.from_title("Весенний семестр 2026/2027"),
        Semester.from_title("Осенний семестр 2024/2025"),
        Semester.from_title("Весенний семестр 2025/2026"),
    ],
    ids=lambda s: f"{s.start}",
)
@pytest.mark.parametrize("week", range(4))
@pytest.mark.parametrize("day", range(1, 7))
def test_dates_for_matches_brute_force(semester: Semester, day: int, week: int) -> None:
    dates = list(semester.dates_for(day, week))

    assert dates == expected_dates(semester, day, week, semester.anchor)
    assert dates, "каждое сочетание дня и недели встречается в семестре"
    assert all(semester.start <= d <= semester.end for d in dates)
    assert all(d.isoweekday() == day for d in dates)
    assert all(semester.week_of(d) == week for d in dates)
    assert all((b - a).days == 28 for a, b in pairwise(dates))


def test_dates_for_skips_days_before_start() -> None:
    # 31.08.2026 — понедельник 1-го числителя, но семестр начинается 01.09.
    semester = Semester.from_title("Осенний семестр 2026/2027")
    assert next(semester.dates_for(1, 0)) == D(2026, 9, 28)
    assert next(semester.dates_for(2, 0)) == D(2026, 9, 1)


@pytest.mark.parametrize(("day", "week"), [(0, 0), (8, 0), (1, -1), (1, 4)])
def test_dates_for_rejects_invalid_arguments(day: int, week: int) -> None:
    semester = Semester.from_title("Осенний семестр 2026/2027")
    with pytest.raises(ValueError):
        list(semester.dates_for(day, week))


def test_with_bounds_overrides_dates_and_keeps_title() -> None:
    semester = Semester.from_title("Весенний семестр 2026/2027")
    changed = semester.with_bounds(start=D(2027, 2, 8))
    assert changed.start == D(2027, 2, 8)
    assert changed.end == semester.end
    assert changed.title == semester.title
    assert changed.anchor == D(2027, 2, 8)


def test_start_after_end_is_rejected() -> None:
    semester = Semester.from_title("Осенний семестр 2026/2027")
    with pytest.raises(ValueError):
        semester.with_bounds(start=D(2026, 12, 1), end=D(2026, 11, 1))
