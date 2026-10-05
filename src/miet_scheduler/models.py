"""Модели расписания и разбор ответа API miet.ru."""

import datetime
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Any

# Тип занятия стоит в квадратных скобках в конце названия: "Информатика [Лек]".
_KIND_RE = re.compile(r"\[([^\[\]]+)\]\s*$")
# Пометки в начале названия: "[ДСТ] История России", "[ФТД] ...".
_TAGS_RE = re.compile(r"^(?:\[[^\[\]]*\]\s*)+")

KIND_NAMES = {
    "Лек": "Лекция",
    "Пр": "Практическое занятие",
    "Лаб": "Лабораторная работа",
    "Конс": "Консультация",
}


@dataclass(frozen=True)
class TimeSlot:
    """Пара: номер и время начала/окончания."""

    code: int
    name: str
    start: datetime.time
    end: datetime.time

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> TimeSlot:
        return cls(
            code=data["Code"],
            name=data["Time"],
            start=_parse_time(data["TimeFrom"]),
            end=_parse_time(data["TimeTo"]),
        )


@dataclass(frozen=True)
class Lesson:
    """Одна запись расписания.

    day — день недели (1 — понедельник, 6 — суббота).
    week — номер недели в 4-недельном цикле (0 — 1-й числитель, 1 — 1-й знаменатель,
    2 — 2-й числитель, 3 — 2-й знаменатель).
    """

    day: int
    week: int
    slot: TimeSlot
    name: str
    class_code: str
    teacher: str
    teacher_full: str
    distance: bool
    room: str
    room_code: int | None
    group: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Lesson:
        class_info = data["Class"]
        room_info = data.get("Room") or {}
        group_info = data.get("Group") or {}
        return cls(
            day=data["Day"],
            week=data["DayNumber"],
            slot=TimeSlot.from_api(data["Time"]),
            name=class_info["Name"].strip(),
            class_code=class_info.get("Code") or "",
            teacher=(class_info.get("Teacher") or "").strip(),
            teacher_full=(class_info.get("TeacherFull") or "").strip(),
            distance=bool(class_info.get("Form")),
            room=(room_info.get("Name") or "").strip(),
            room_code=room_info.get("Code"),
            group=(group_info.get("Name") or "").strip(),
        )

    @property
    def kind(self) -> str | None:
        """Тип занятия из скобок: "Лек", "Пр", "Лаб", "Конс"…"""
        match = _KIND_RE.search(self.name)
        return match.group(1).strip() if match else None

    @property
    def subject(self) -> str:
        """Название предмета без типа занятия: "Информатика"."""
        return _KIND_RE.sub("", self.name).strip()

    @property
    def base_subject(self) -> str:
        """Название предмета без типа занятия и пометок: "История России"."""
        return _TAGS_RE.sub("", self.subject).strip()


@dataclass(frozen=True)
class Schedule:
    semester: str
    lessons: list[Lesson]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Schedule:
        lessons = [Lesson.from_api(item) for item in data.get("Data") or []]
        lessons.sort(key=lambda x: (x.week, x.day, x.slot.code))
        return cls(semester=data["Semestr"], lessons=lessons)

    def without_subjects(self, subjects: Iterable[str]) -> Schedule:
        """Расписание без занятий по указанным предметам.

        Сравнивается название без типа занятия и пометок, без учёта регистра:
        "Военная подготовка" убирает и "Военная подготовка [Пр]".
        """
        names = {s.casefold() for s in subjects}
        lessons = [x for x in self.lessons if x.base_subject.casefold() not in names]
        return replace(self, lessons=lessons)


def _parse_time(value: str) -> datetime.time:
    # API отдаёт время как "0001-01-01T09:00:00".
    return datetime.time.fromisoformat(value.split("T")[1])
