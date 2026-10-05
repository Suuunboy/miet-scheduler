from dataclasses import dataclass, field
from datetime import tzinfo
from typing import Any
import datetime
from zoneinfo import ZoneInfo

from ical.calendar import Calendar
from ical.event import Event
import re

from pathlib import Path
from ical.calendar_stream import IcsCalendarStream


@dataclass
class ScheduleCalendar:
    original_data: dict[str, Any]
    calendar: Calendar = field(default_factory=Calendar)
    semester: str = field(default_factory=str)
    sorted_schedule: list[dict[str, Any]] = field(default_factory=list)

    def __parse_original_data(self) -> None:
        self.semester = self.original_data['schedule']['Semestr']

        schedule = self.original_data['schedule']['Data']
        # Day (1-6) - день недели с понедельника по субботу
        # DayNumber (0-3) - показатель числитель-знаменатель.
        sorted_schedule = sorted(schedule, key=lambda x: (x['DayNumber'], x['Day'], x['Time']['Code']))
        self.sorted_schedule = sorted_schedule

    def __resolve_semester(self) -> dict[str, Any]:
        semester_type = 'autumn' if 'осен' in self.semester.lower() else 'spring'
        schedule_years = list(map(int, re.findall(r'\b\d{4}\b', self.semester)))
        semester_year = min(schedule_years) if semester_type == 'autumn' else max(schedule_years)

        return {'semester_type': semester_type,
                'semester_year': semester_year}

    @staticmethod
    def __parse_schedule_time(time_info: dict[str, Any], day: datetime.datetime) -> dict[str, datetime.datetime]:
        time_from = datetime.datetime.strptime(time_info['TimeFrom'].split('T')[1], '%H:%M:%S').time()
        time_to = datetime.datetime.strptime(time_info['TimeTo'].split('T')[1], '%H:%M:%S').time()

        parsed_time_from = datetime.datetime.combine(day.date(), time_from, tzinfo=ZoneInfo('Europe/Moscow'))
        parsed_time_to = datetime.datetime.combine(day.date(), time_to, tzinfo=ZoneInfo('Europe/Moscow'))

        return {'time_from': parsed_time_from, 'time_to': parsed_time_to}

    def __make_events(self) -> list[Event]:
        events = []
        semester_info = self.__resolve_semester()
        semester_year = semester_info['semester_year']
        semester_type = semester_info['semester_type']

        # Первый день месяца может быть любым днем недели, не обязательно понедельник =>
        # Идея - заполнять с понедельника. Понедельник должен находиться в той же неделе, в которой находится начало сентября/февраля
        # Каждый день повторяется 4 раза с интервалом в 4 недели

        first_day = datetime.datetime(year=semester_year, month=9 if semester_type == 'autumn' else 3, day=1)
        current_day = first_day

        while current_day.isoweekday() > 1:
            current_day -= datetime.timedelta(days=1)

        for event in self.sorted_schedule:
            class_info = event['Class']
            time_info = event['Time']
            parsed_time = self.__parse_schedule_time(time_info, current_day)
            events.append(Event(
                dtstart=parsed_time['time_from'],
                dtend=parsed_time['time_to'],
                summary=f'{class_info['Name']} - {time_info['Time']}',
            ))

            # Переделать. Сейчас работает неправильно: сейчас одно событие - один день
            if current_day.isoweekday() == 6:
                current_day += datetime.timedelta(days=2)
            else:
                current_day += datetime.timedelta(days=1)

        return events

    def __write_cal_to_ics(self) -> None:
        with Path("output.ics").open("w") as f:
            f.write(IcsCalendarStream.calendar_to_ics(self.calendar))


    def make_calendar(self) -> Calendar:
        self.__parse_original_data()

        events = self.__make_events()
        self.calendar.events.extend(events)
        self.__write_cal_to_ics()

        return self.calendar