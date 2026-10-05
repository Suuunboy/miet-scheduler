"""Командная строка: miet-scheduler -g П-11."""

import argparse
import asyncio
import datetime
import re
import sys
from pathlib import Path

from .api import MietApiError, MietClient, create_http_client
from .holidays import parse_dates, public_holidays, read_dates_file, within
from .ics import DEFAULT_COLOR, build_calendar, write_ics
from .models import Schedule
from .semester import Semester

_COLOR_RE = re.compile(r"^[A-Za-z]+$")

# Занятия, которые по умолчанию не попадают в календарь: предмет → флаг включения.
OPTIONAL_SUBJECTS = {
    "Практическая подготовка": "--include-practice",
    "Военная подготовка": "--include-military",
}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except (MietApiError, ValueError) as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1


async def _run(args: argparse.Namespace) -> int:
    # Файлы с исключениями читаем до запросов к сайту,
    # чтобы ошибка в них была видна сразу.
    extra_skip: set[datetime.date] = set().union(*args.skip_dates)
    for path in args.skip_file:
        extra_skip |= read_dates_file(path)

    async with create_http_client() as http:
        client = MietClient(http)

        if args.list_groups:
            for name in await client.groups():
                print(name)
            return 0

        group = await client.resolve_group(args.group)
        full_schedule = Schedule.from_api(await client.schedule(group))

    if not full_schedule.lessons:
        print(f"Ошибка: у группы {group} нет занятий в расписании", file=sys.stderr)
        return 1

    excluded = [
        subject
        for subject, flag in OPTIONAL_SUBJECTS.items()
        if not getattr(args, _dest(flag))
    ]
    schedule = full_schedule.without_subjects(excluded)
    present = {x.base_subject.casefold() for x in full_schedule.lessons}
    hidden = [subject for subject in excluded if subject.casefold() in present]

    if not schedule.lessons:
        flags = " ".join(OPTIONAL_SUBJECTS[subject] for subject in hidden)
        print(
            f"Ошибка: у группы {group} в расписании только {_join(hidden)}. "
            f"Чтобы выгрузить их, добавьте {flags}",
            file=sys.stderr,
        )
        return 1

    semester = Semester.from_title(schedule.semester).with_bounds(args.start, args.end)
    skip_dates = set(extra_skip)
    if not args.no_holidays:
        skip_dates |= public_holidays(semester.start, semester.end)

    calendar = build_calendar(
        schedule, semester, args.color, dict(args.color_map), skip_dates
    )

    output = args.output or Path(f"{_safe_filename(group)}.ics")
    write_ics(calendar, output)

    print(
        f"{group}, {schedule.semester} "
        f"({semester.start:%d.%m.%Y}–{semester.end:%d.%m.%Y}): "
        f"{len(calendar.events)} занятий сохранено в {output}"
    )
    if skipped := within(skip_dates, semester.start, semester.end):
        print("Без занятий: " + ", ".join(f"{d:%d.%m.%Y}" for d in skipped))
    for subject in hidden:
        print(f"Не выгружено: {subject} (добавьте {OPTIONAL_SUBJECTS[subject]})")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="miet-scheduler",
        description="Выгрузка расписания МИЭТ в календарь iCalendar (.ics).",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("-g", "--group", help="название группы, например П-11")
    target.add_argument(
        "--list-groups", action="store_true", help="вывести список всех групп и выйти"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="путь к .ics-файлу (по умолчанию <группа>.ics)",
    )
    parser.add_argument(
        "--color",
        type=_color,
        default=DEFAULT_COLOR,
        help=f"цвет событий, имя цвета CSS3 (по умолчанию {DEFAULT_COLOR})",
    )
    parser.add_argument(
        "--color-map",
        type=_color_mapping,
        action="append",
        default=[],
        metavar="КЛЮЧ=ЦВЕТ",
        help=(
            "цвет для предмета или типа занятия, например "
            '"Информатика=blue" или "Лаб=green"; можно указать несколько раз'
        ),
    )
    parser.add_argument(
        "--start",
        type=_date,
        help="дата начала семестра ГГГГ-ММ-ДД (по умолчанию 1 сентября / 1 февраля)",
    )
    parser.add_argument(
        "--end",
        type=_date,
        help="дата конца семестра ГГГГ-ММ-ДД (по умолчанию 31 декабря / 31 мая)",
    )
    parser.add_argument(
        "--skip-dates",
        type=_dates,
        action="append",
        default=[],
        metavar="ДАТЫ",
        help=(
            "даты без занятий через запятую: 2026-11-05 или интервал "
            "2026-12-29..2026-12-31; можно указать несколько раз"
        ),
    )
    parser.add_argument(
        "--skip-file",
        type=Path,
        action="append",
        default=[],
        metavar="ФАЙЛ",
        help="файл с датами без занятий: дата или интервал на строке, # — комментарий",
    )
    for subject, flag in OPTIONAL_SUBJECTS.items():
        parser.add_argument(
            flag,
            action="store_true",
            help=f"выгрузить занятия «{subject}» (по умолчанию пропускаются)",
        )
    parser.add_argument(
        "--no-holidays",
        action="store_true",
        help="не пропускать государственные праздники (ст. 112 ТК РФ)",
    )
    return parser


def _date(value: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"ожидается дата ГГГГ-ММ-ДД: {value!r}"
        ) from None


def _dates(value: str) -> set[datetime.date]:
    try:
        return parse_dates(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def _color(value: str) -> str:
    if not _COLOR_RE.match(value):
        raise argparse.ArgumentTypeError(
            f"ожидается имя цвета CSS3 (например, gray, blue): {value!r}"
        )
    return value.lower()


def _color_mapping(value: str) -> tuple[str, str]:
    key, sep, color = value.rpartition("=")
    if not sep or not key.strip():
        raise argparse.ArgumentTypeError(f"ожидается КЛЮЧ=ЦВЕТ: {value!r}")
    return key.strip(), _color(color.strip())


def _dest(flag: str) -> str:
    return flag.lstrip("-").replace("-", "_")


def _join(subjects: list[str]) -> str:
    return " и ".join(f"«{subject}»" for subject in subjects)


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name)
