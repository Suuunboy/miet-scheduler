import datetime
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo

from ical.calendar_stream import IcsCalendarStream
from ical.event import Event

from miet_scheduler.ics import build_calendar, calendar_to_ics, write_ics
from miet_scheduler.models import Schedule
from miet_scheduler.semester import Semester

from .sample import GROUP, SEMESTER_TITLE, expected_dates

MSK = ZoneInfo("Europe/Moscow")
NOV_4 = datetime.date(2026, 11, 4)


def _events(schedule: Schedule, semester: Semester, **kwargs) -> list[Event]:
    return build_calendar(schedule, semester, **kwargs).events


def _by_summary(events: list[Event], summary: str) -> list[Event]:
    return [e for e in events if e.summary == summary]


def test_every_lesson_becomes_event_on_each_matching_date(
    schedule: Schedule, semester: Semester
) -> None:
    events = _events(schedule, semester)

    expected = Counter()
    for lesson in schedule.lessons:
        for date in expected_dates(semester, lesson.day, lesson.week, semester.anchor):
            start = datetime.datetime.combine(date, lesson.slot.start, tzinfo=MSK)
            expected[(start, lesson.name)] += 1

    assert Counter((e.dtstart, e.summary) for e in events) == expected
    assert all(semester.start <= e.dtstart.date() <= semester.end for e in events)
    assert [e.dtstart for e in events] == sorted(e.dtstart for e in events)


def test_event_fields(schedule: Schedule, semester: Semester) -> None:
    event = _by_summary(_events(schedule, semester), "Физика [Лаб]")[0]

    assert event.dtstart == datetime.datetime(2026, 9, 1, 12, 0, tzinfo=MSK)
    assert event.dtend == datetime.datetime(2026, 9, 1, 13, 20, tzinfo=MSK)
    assert event.location == "3112"
    assert event.categories == ["Лаб"]
    assert event.color == "gray"
    assert event.description.splitlines() == [
        "Преподаватель: Петров Пётр Петрович",
        "Тип: Лабораторная работа",
        "Аудитория: 3112",
        "Пара: 3 пара (12:00–13:20)",
        "Неделя: 1 числитель",
        f"Группа: {GROUP}",
    ]


def test_distance_lesson_is_marked(schedule: Schedule, semester: Semester) -> None:
    events = _by_summary(_events(schedule, semester), "[ДСТ] История России [Конс]")
    assert events
    assert all("Формат: дистанционно" in e.description for e in events)
    assert all("Неделя: 2 знаменатель" in e.description for e in events)


def test_subgroups_are_marked(schedule: Schedule, semester: Semester) -> None:
    events = _events(schedule, semester)
    split = [e for e in events if "Занятие по подгруппам" in e.description]

    assert split
    assert {e.summary for e in split} == {"Иностранный язык [Пр]"}
    assert {e.location for e in split} == {"3242", "3303 а"}
    assert len(split) == len(_by_summary(events, "Иностранный язык [Пр]"))


def test_skip_dates(schedule: Schedule, semester: Semester) -> None:
    all_events = _events(schedule, semester)
    events = _events(schedule, semester, skip_dates={NOV_4})

    assert any(e.dtstart.date() == NOV_4 for e in all_events)
    assert not any(e.dtstart.date() == NOV_4 for e in events)
    assert len(all_events) - len(events) == sum(
        e.dtstart.date() == NOV_4 for e in all_events
    )


def test_colors(schedule: Schedule, semester: Semester) -> None:
    color_map = {
        "Иностранный язык [Пр]": "red",  # полное название
        "Иностранный язык": "blue",
        "Лек": "green",  # тип занятия
        "Физика": "orange",  # название предмета
        "Лаб": "purple",
    }
    events = _events(schedule, semester, color="silver", color_map=color_map)
    colors = {e.summary: e.color for e in events}

    assert colors == {
        "Иностранный язык [Пр]": "red",
        "Математический анализ [Лек]": "green",
        "Программирование [Лек]": "green",
        "Физика [Лаб]": "orange",
        "[ДСТ] История России [Конс]": "silver",
    }


def test_uids_are_unique_and_stable(schedule: Schedule, semester: Semester) -> None:
    first = [e.uid for e in _events(schedule, semester)]
    second = [e.uid for e in _events(schedule, semester)]

    assert first == second
    assert len(set(first)) == len(first)
    assert all(uid.endswith("@miet-scheduler") for uid in first)


def test_calendar_metadata(schedule: Schedule, semester: Semester) -> None:
    calendar = build_calendar(schedule, semester, color="navy")
    title = f"МИЭТ {GROUP} — {SEMESTER_TITLE}"

    assert calendar.name == [title]
    assert calendar.color == "navy"
    assert calendar.x_wr_timezone == "Europe/Moscow"
    assert [t.tz_id for t in calendar.timezones] == ["Europe/Moscow"]
    assert f"X-WR-CALNAME:{title}" in calendar_to_ics(calendar)


def test_write_ics_uses_utf8_and_crlf(
    tmp_path: Path, schedule: Schedule, semester: Semester
) -> None:
    calendar = build_calendar(schedule, semester)
    path = tmp_path / "out.ics"

    write_ics(calendar, path)
    raw = path.read_bytes()

    text = raw.decode("utf-8")
    assert raw.count(b"\n") == raw.count(b"\r\n")
    assert b"\r\r" not in raw
    assert "Математический анализ" in text

    parsed = IcsCalendarStream.calendar_from_ics(text)
    assert len(parsed.events) == len(calendar.events)
    assert parsed.events[0].description == calendar.events[0].description
