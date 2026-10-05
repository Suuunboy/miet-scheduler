"""Синтетическое расписание в формате API miet.ru.

Имена преподавателей и группа вымышленные. Семестр — осенний 2026/2027:
неделя "1 числитель" начинается в понедельник 31.08.2026.
"""

import datetime
from typing import Any

from miet_scheduler.semester import Semester

GROUP = "ТСТ-11"
SEMESTER_TITLE = "Осенний семестр 2026/2027"

TIMES = [
    {
        "Time": f"{code} пара",
        "Code": code,
        "TimeFrom": f"0001-01-01T{start}:00",
        "TimeTo": f"0001-01-01T{end}:00",
    }
    for code, start, end in [
        (1, "09:00", "10:20"),
        (2, "10:30", "11:50"),
        (3, "12:00", "13:20"),
        (4, "14:00", "15:20"),
        (5, "15:30", "16:50"),
        (6, "17:00", "18:20"),
        (7, "18:30", "19:50"),
        (8, "20:00", "21:20"),
    ]
]


def make_entry(
    day: int,
    week: int,
    time_code: int,
    name: str,
    teacher_full: str,
    room: str,
    *,
    room_code: int = 1,
    distance: bool = False,
    class_code: str = "class-code",
) -> dict[str, Any]:
    parts = teacher_full.split()
    if len(parts) == 3:
        surname, first, middle = parts
        teacher = f"{surname} {first[0]}.{middle[0]}."
    else:
        # Заглушки вроде "Преподаватель УВЦ" сайт отдаёт без сокращения.
        teacher = teacher_full
    return {
        "Day": day,
        "DayNumber": week,
        "Time": TIMES[time_code - 1],
        "Class": {
            "Code": class_code,
            "Name": name,
            "TeacherFull": teacher_full,
            "Teacher": teacher,
            "Form": distance,
        },
        "Group": {"Code": "000000000000001", "Name": GROUP},
        "Room": {"Code": room_code, "Name": room},
    }


ENTRIES = [
    # Понедельник, 1-й числитель и 1-й знаменатель.
    make_entry(1, 0, 1, "Математический анализ [Лек]", "Иванов Иван Иванович", "1201 м",
               class_code="matan", room_code=120),
    make_entry(1, 1, 1, "Математический анализ [Лек]", "Иванов Иван Иванович", "1201 м",
               class_code="matan", room_code=120),
    # Вторник, 1-й числитель. В названии аудитории хвостовой пробел, как на сайте.
    make_entry(2, 0, 3, "Физика [Лаб]", "Петров Пётр Петрович", "3112 ",
               class_code="phys", room_code=311),
    # Среда, 2-й числитель: занятие по подгруппам.
    make_entry(3, 2, 2, "Иностранный язык [Пр]", "Смирнова Анна Сергеевна", "3242",
               class_code="lang", room_code=324),
    make_entry(3, 2, 2, "Иностранный язык [Пр]", "Кузнецова Мария Олеговна", "3303 а",
               class_code="lang", room_code=330),
    # Среда, 1-й знаменатель: попадает на праздник 04.11.2026.
    make_entry(3, 1, 4, "Программирование [Лек]", "Соколов Олег Андреевич", "4303",
               class_code="prog", room_code=430),
    # Суббота, 2-й знаменатель: дистанционная консультация.
    make_entry(6, 3, 7, "[ДСТ] История России [Конс]", "Попова Елена Викторовна",
               "Виртуальная аудитория 1", class_code="hist", room_code=1,
               distance=True),
]  # fmt: skip

# Занятия, которые по умолчанию не выгружаются, и похожий факультатив,
# который фильтр трогать не должен. Названия и заглушки — как на сайте.
OPTIONAL_ENTRIES = [
    make_entry(4, 0, 1, "Практическая подготовка",
               "Преподаватель практической подготовки 1",
               "Аудитория практической подготовки 1", class_code="practice"),
    make_entry(5, 1, 2, "Военная подготовка [Пр]", "Преподаватель УВЦ", "УВЦ 1",
               class_code="military"),
    make_entry(5, 1, 3, "[ФТД] Основы военной подготовки [Лек]",
               "Морозов Андрей Николаевич", "1204 м", class_code="military-basics"),
]  # fmt: skip


def expected_dates(
    semester: Semester, day: int, week: int, anchor: datetime.date
) -> list[datetime.date]:
    """Перебором по всем дням: даты, где день недели и неделя цикла совпадают."""
    result = []
    date = semester.start
    while date <= semester.end:
        if date.isoweekday() == day and (date - anchor).days // 7 % 4 == week:
            result.append(date)
        date += datetime.timedelta(days=1)
    return result
