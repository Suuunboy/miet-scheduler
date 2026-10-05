"""Праздники и даты без занятий."""

import datetime
from collections.abc import Iterable
from pathlib import Path

# Нерабочие праздничные дни по ст. 112 ТК РФ: (месяц, день).
PUBLIC_HOLIDAYS = (
    *((1, day) for day in range(1, 9)),
    (2, 23),
    (3, 8),
    (5, 1),
    (5, 9),
    (6, 12),
    (11, 4),
)

_RANGE_SEP = ".."


def public_holidays(start: datetime.date, end: datetime.date) -> set[datetime.date]:
    """Государственные праздники в интервале [start, end]."""
    return {
        date
        for year in range(start.year, end.year + 1)
        for month, day in PUBLIC_HOLIDAYS
        if start <= (date := datetime.date(year, month, day)) <= end
    }


def parse_dates(value: str) -> set[datetime.date]:
    """Разбирает список дат через запятую.

    Каждый элемент — дата "2026-11-04" или интервал "2026-12-29..2026-12-31"
    (обе границы включаются).
    """
    dates: set[datetime.date] = set()
    for item in value.split(","):
        item = item.strip()
        if item:
            dates |= _parse_item(item)
    return dates


def read_dates_file(path: Path) -> set[datetime.date]:
    """Читает даты из файла.

    На строке — дата или интервал, как в parse_dates. "#" начинает комментарий.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Не удалось прочитать файл {path}: {e.strerror}") from e

    dates: set[datetime.date] = set()
    for number, line in enumerate(text.splitlines(), start=1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        try:
            dates |= parse_dates(line)
        except ValueError as e:
            raise ValueError(f"{path}, строка {number}: {e}") from e
    return dates


def within(
    dates: Iterable[datetime.date], start: datetime.date, end: datetime.date
) -> list[datetime.date]:
    """Отсортированные даты из интервала [start, end]."""
    return sorted(d for d in dates if start <= d <= end)


def _parse_item(item: str) -> set[datetime.date]:
    if _RANGE_SEP in item:
        first, _, last = item.partition(_RANGE_SEP)
        start, end = _parse_date(first), _parse_date(last)
        if start > end:
            raise ValueError(f"начало интервала позже конца: {item!r}")
        days = (end - start).days
        return {start + datetime.timedelta(days=i) for i in range(days + 1)}
    return {_parse_date(item)}


def _parse_date(value: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value.strip())
    except ValueError:
        raise ValueError(f"ожидается дата ГГГГ-ММ-ДД: {value.strip()!r}") from None
