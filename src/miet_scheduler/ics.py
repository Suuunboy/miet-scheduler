"""Сборка календаря iCalendar из расписания."""

import datetime
import hashlib
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from zoneinfo import ZoneInfo

from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.event import Event
from ical.parsing.property import ParsedProperty
from ical.timezone import Timezone

from .models import KIND_NAMES, Lesson, Schedule
from .semester import WEEK_NAMES, Semester

TIMEZONE = "Europe/Moscow"
DEFAULT_COLOR = "gray"
PRODID = "-//miet-scheduler//miet-scheduler//RU"


def build_calendar(
    schedule: Schedule,
    semester: Semester,
    color: str = DEFAULT_COLOR,
    color_map: Mapping[str, str] | None = None,
) -> Calendar:
    """Создаёт календарь, в котором каждое занятие — отдельное событие.

    color — цвет всех событий по умолчанию (имя цвета CSS3, RFC 7986).
    color_map — цвета для отдельных предметов или типов занятий. Ключом может быть
    полное название ("Информатика [Лек]"), название предмета ("Информатика")
    или тип занятия ("Лек").
    """
    color_map = color_map or {}
    tz = ZoneInfo(TIMEZONE)
    group = next((x.group for x in schedule.lessons if x.group), "")
    title = " — ".join(filter(None, [f"МИЭТ {group}".strip(), schedule.semester]))

    calendar = Calendar(
        prodid=PRODID,
        name=[title],
        color=color,
        x_wr_timezone=TIMEZONE,
    )
    calendar.extras.append(ParsedProperty(name="x-wr-calname", value=title))
    calendar.timezones.append(Timezone.from_tzif(TIMEZONE))

    # Несколько записей в одном слоте — это занятия по подгруппам.
    slot_counts = Counter((x.week, x.day, x.slot.code) for x in schedule.lessons)

    for lesson in schedule.lessons:
        split = slot_counts[(lesson.week, lesson.day, lesson.slot.code)] > 1
        lesson_color = _resolve_color(lesson, color, color_map)
        for date in semester.dates_for(lesson.day, lesson.week):
            calendar.events.append(
                _make_event(lesson, date, tz, schedule.semester, lesson_color, split)
            )

    calendar.events.sort(key=lambda e: (e.dtstart, e.summary or ""))
    return calendar


def calendar_to_ics(calendar: Calendar) -> str:
    return IcsCalendarStream.calendar_to_ics(calendar)


def write_ics(calendar: Calendar, path: Path) -> None:
    # RFC 5545 требует CRLF. Библиотека отдаёт "\n", Python заменит его при записи.
    with path.open("w", encoding="utf-8", newline="\r\n") as f:
        f.write(calendar_to_ics(calendar))


def _make_event(
    lesson: Lesson,
    date: datetime.date,
    tz: ZoneInfo,
    semester_title: str,
    color: str,
    split: bool,
) -> Event:
    return Event(
        uid=_make_uid(lesson, date, semester_title),
        dtstart=datetime.datetime.combine(date, lesson.slot.start, tzinfo=tz),
        dtend=datetime.datetime.combine(date, lesson.slot.end, tzinfo=tz),
        summary=lesson.name,
        location=lesson.room or None,
        description=_make_description(lesson, split),
        categories=[lesson.kind] if lesson.kind else [],
        color=color,
    )


def _make_description(lesson: Lesson, split: bool) -> str:
    slot = lesson.slot
    lines = []
    if teacher := lesson.teacher_full or lesson.teacher:
        lines.append(f"Преподаватель: {teacher}")
    if lesson.kind:
        lines.append(f"Тип: {KIND_NAMES.get(lesson.kind, lesson.kind)}")
    if lesson.room:
        lines.append(f"Аудитория: {lesson.room}")
    lines.append(f"Пара: {slot.name} ({slot.start:%H:%M}–{slot.end:%H:%M})")
    lines.append(f"Неделя: {WEEK_NAMES[lesson.week]}")
    if lesson.group:
        lines.append(f"Группа: {lesson.group}")
    if lesson.distance:
        lines.append("Формат: дистанционно")
    if split:
        lines.append("Занятие по подгруппам")
    return "\n".join(lines)


def _make_uid(lesson: Lesson, date: datetime.date, semester_title: str) -> str:
    # UID стабилен между запусками: при повторном импорте события обновятся,
    # а не задублируются.
    key = "|".join(
        str(x)
        for x in (
            lesson.group,
            semester_title,
            lesson.class_code,
            lesson.name,
            lesson.slot.code,
            lesson.room_code,
            lesson.teacher_full,
            date.isoformat(),
        )
    )
    return f"{hashlib.sha1(key.encode()).hexdigest()}@miet-scheduler"


def _resolve_color(lesson: Lesson, default: str, color_map: Mapping[str, str]) -> str:
    for key in (lesson.name, lesson.subject, lesson.kind):
        if key and key in color_map:
            return color_map[key]
    return default
