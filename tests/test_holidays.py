import datetime
from pathlib import Path

import pytest

from miet_scheduler.holidays import (
    parse_dates,
    public_holidays,
    read_dates_file,
    within,
)

D = datetime.date


def test_public_holidays_autumn() -> None:
    assert public_holidays(D(2026, 9, 1), D(2026, 12, 31)) == {D(2026, 11, 4)}


def test_public_holidays_spring() -> None:
    assert public_holidays(D(2027, 2, 1), D(2027, 5, 31)) == {
        D(2027, 2, 23),
        D(2027, 3, 8),
        D(2027, 5, 1),
        D(2027, 5, 9),
    }


def test_public_holidays_across_new_year() -> None:
    holidays = public_holidays(D(2026, 12, 1), D(2027, 1, 10))
    assert holidays == {D(2027, 1, day) for day in range(1, 9)}


def test_parse_single_date() -> None:
    assert parse_dates("2026-11-05") == {D(2026, 11, 5)}


def test_parse_list_and_range() -> None:
    assert parse_dates(" 2026-11-05, 2026-12-29..2026-12-31 ,") == {
        D(2026, 11, 5),
        D(2026, 12, 29),
        D(2026, 12, 30),
        D(2026, 12, 31),
    }


@pytest.mark.parametrize(
    "value", ["05.11.2026", "2026-13-01", "2026-12-31..2026-12-29"]
)
def test_parse_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_dates(value)


def test_read_dates_file(tmp_path: Path) -> None:
    path = tmp_path / "holidays.txt"
    path.write_text(
        "# каникулы\n2026-12-29..2026-12-30\n\n2026-11-05  # перенос\n",
        encoding="utf-8",
    )
    assert read_dates_file(path) == {D(2026, 12, 29), D(2026, 12, 30), D(2026, 11, 5)}


def test_read_dates_file_reports_line_number(tmp_path: Path) -> None:
    path = tmp_path / "holidays.txt"
    path.write_text("2026-11-05\nне дата\n", encoding="utf-8")
    with pytest.raises(ValueError, match="строка 2"):
        read_dates_file(path)


def test_read_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Не удалось прочитать"):
        read_dates_file(tmp_path / "missing.txt")


def test_within_filters_and_sorts() -> None:
    dates = {D(2026, 12, 31), D(2026, 9, 1), D(2027, 1, 1), D(2026, 8, 31)}
    assert within(dates, D(2026, 9, 1), D(2026, 12, 31)) == [
        D(2026, 9, 1),
        D(2026, 12, 31),
    ]
