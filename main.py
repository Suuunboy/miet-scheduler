import argparse
import asyncio
import pprint
from schedule_parser import ScheduleCalendar

from miet_schedule_fetcher import MietScheduleFetcher

async def main(group: str) -> None:
    fetcher = MietScheduleFetcher(group)
    schedule = await fetcher.fetch()

    schedule_calendar = ScheduleCalendar(schedule)
    pprint.pprint(schedule_calendar.make_calendar())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-g', '--group', type=str)
    group = parser.parse_args().group

    asyncio.run(main(group))
