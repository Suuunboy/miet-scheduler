"""Границы семестра и вычисление дат занятий по 4-недельному циклу."""

import datetime
import re
from collections.abc import Iterator
from dataclasses import dataclass, replace

WEEK_NAMES = ("1 числитель", "1 знаменатель", "2 числитель", "2 знаменатель")
CYCLE_WEEKS = len(WEEK_NAMES)


@dataclass(frozen=True)
class Semester:
    title: str
    start: datetime.date
    end: datetime.date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError(f"Начало семестра ({self.start}) позже конца ({self.end})")

    @classmethod
    def from_title(cls, title: str) -> Semester:
        """Определяет границы по строке вида "Осенний семестр 2026/2027".

        Осенний семестр: с 1 сентября по 31 декабря первого года.
        Весенний семестр: с 1 февраля по 31 мая второго года.
        """
        lowered = title.lower()
        years = [int(y) for y in re.findall(r"\b\d{4}\b", title)]
        if not years:
            raise ValueError(f"Не удалось определить год семестра: {title!r}")

        if "осен" in lowered:
            year = min(years)
            return cls(title, datetime.date(year, 9, 1), datetime.date(year, 12, 31))
        if "весен" in lowered:
            year = max(years)
            return cls(title, datetime.date(year, 2, 1), datetime.date(year, 5, 31))
        raise ValueError(f"Не удалось определить тип семестра: {title!r}")

    def with_bounds(
        self, start: datetime.date | None = None, end: datetime.date | None = None
    ) -> Semester:
        return replace(self, start=start or self.start, end=end or self.end)

    @property
    def anchor(self) -> datetime.date:
        """Понедельник недели "1 числитель".

        Первый рабочий день семестра всегда попадает в 1-й числитель. Рабочие дни —
        с понедельника по субботу, поэтому если семестр начинается в воскресенье,
        цикл начинается со следующего понедельника.
        """
        first_workday = self.start
        if first_workday.isoweekday() == 7:
            first_workday += datetime.timedelta(days=1)
        return first_workday - datetime.timedelta(days=first_workday.weekday())

    def week_of(self, date: datetime.date) -> int:
        """Номер недели в цикле (0–3) для даты."""
        return (date - self.anchor).days // 7 % CYCLE_WEEKS

    def dates_for(self, day: int, week: int) -> Iterator[datetime.date]:
        """Все даты семестра, которые приходятся на день недели day (1–6) недели week (0–3)."""
        if not 1 <= day <= 7:
            raise ValueError(f"Некорректный день недели: {day}")
        if not 0 <= week < CYCLE_WEEKS:
            raise ValueError(f"Некорректный номер недели: {week}")

        date = self.anchor + datetime.timedelta(weeks=week, days=day - 1)
        step = datetime.timedelta(weeks=CYCLE_WEEKS)
        while date <= self.end:
            if date >= self.start:
                yield date
            date += step
