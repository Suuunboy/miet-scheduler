import datetime
from typing import Any

from miet_scheduler.models import Lesson, Schedule

from .sample import GROUP, OPTIONAL_ENTRIES, SEMESTER_TITLE, make_entry


def test_lesson_from_api() -> None:
    lesson = Lesson.from_api(
        make_entry(2, 0, 3, "Физика [Лаб]", "Петров Пётр Петрович", "3112 ")
    )

    assert (lesson.day, lesson.week) == (2, 0)
    assert lesson.slot.code == 3
    assert lesson.slot.name == "3 пара"
    assert lesson.slot.start == datetime.time(12, 0)
    assert lesson.slot.end == datetime.time(13, 20)
    assert lesson.name == "Физика [Лаб]"
    assert lesson.teacher == "Петров П.П."
    assert lesson.teacher_full == "Петров Пётр Петрович"
    assert lesson.room == "3112"
    assert lesson.group == GROUP
    assert lesson.distance is False


def test_lesson_kind_and_subject() -> None:
    entry = make_entry(6, 3, 7, "[ДСТ] История России [Конс]", "А Б В", "1")
    lesson = Lesson.from_api(entry)
    assert lesson.kind == "Конс"
    assert lesson.subject == "[ДСТ] История России"


def test_base_subject_drops_tags_and_kind() -> None:
    lesson = Lesson.from_api(
        make_entry(5, 1, 3, "[ФТД] [ДСТ] Основы права [Лек]", "А Б В", "1")
    )
    assert lesson.base_subject == "Основы права"


def test_lesson_without_kind() -> None:
    lesson = Lesson.from_api(make_entry(1, 0, 1, "Кураторский час", "А Б В", "1"))
    assert lesson.kind is None
    assert lesson.subject == "Кураторский час"


def test_lesson_tolerates_missing_room_and_teacher() -> None:
    entry = make_entry(1, 0, 1, "Предмет [Лек]", "А Б В", "1")
    entry["Room"] = None
    entry["Class"]["Teacher"] = None
    entry["Class"]["TeacherFull"] = None

    lesson = Lesson.from_api(entry)

    assert lesson.room == ""
    assert lesson.room_code is None
    assert lesson.teacher == lesson.teacher_full == ""


def test_schedule_sorts_lessons(payload: dict[str, Any]) -> None:
    payload["Data"] = list(reversed(payload["Data"]))
    schedule = Schedule.from_api(payload)

    keys = [(x.week, x.day, x.slot.code) for x in schedule.lessons]
    assert keys == sorted(keys)
    assert schedule.semester == SEMESTER_TITLE


def test_without_subjects(payload: dict[str, Any]) -> None:
    payload["Data"] = payload["Data"] + OPTIONAL_ENTRIES
    schedule = Schedule.from_api(payload)

    filtered = schedule.without_subjects(
        ["военная подготовка", "Практическая подготовка"]
    )

    names = {x.name for x in filtered.lessons}
    assert "Военная подготовка [Пр]" not in names
    assert "Практическая подготовка" not in names
    assert "[ФТД] Основы военной подготовки [Лек]" in names
    assert len(filtered.lessons) == len(schedule.lessons) - 2
    assert filtered.semester == schedule.semester


def test_schedule_with_empty_data() -> None:
    schedule = Schedule.from_api({"Times": [], "Data": [], "Semestr": SEMESTER_TITLE})
    assert schedule.lessons == []
