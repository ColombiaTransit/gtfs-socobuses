#!/usr/bin/env python3
"""Generate GTFS calendar and Colombian holiday exceptions.

Service IDs are provisional: map them to verified route-specific operating days
before publishing a complete GTFS feed.
"""
import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

import holidays


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def generate(start, end, output):
    if end < start:
        raise ValueError("end must be on or after start")
    colombia = holidays.country_holidays("CO", years=range(start.year, end.year + 1))
    service_days = {
        "WEEKDAY": [1, 1, 1, 1, 1, 0, 0],
        "SATURDAY": [0, 0, 0, 0, 0, 1, 0],
        "SUNDAY_HOLIDAY": [0, 0, 0, 0, 0, 0, 1],
    }
    calendar = []
    for service_id, days in service_days.items():
        calendar.append(dict(zip(
            ["service_id", "monday", "tuesday", "wednesday", "thursday",
             "friday", "saturday", "sunday", "start_date", "end_date"],
            [service_id, *days, start.strftime("%Y%m%d"), end.strftime("%Y%m%d")],
        )))
    exceptions = []
    current = start
    while current <= end:
        if current in colombia and current.weekday() != 6:
            normal = "SATURDAY" if current.weekday() == 5 else "WEEKDAY"
            day = current.strftime("%Y%m%d")
            exceptions.extend([
                {"service_id": normal, "date": day, "exception_type": 2},
                {"service_id": "SUNDAY_HOLIDAY", "date": day, "exception_type": 1},
            ])
        current += timedelta(days=1)
    write_csv(output / "calendar.txt", list(calendar[0]), calendar)
    write_csv(output / "calendar_dates.txt",
              ["service_id", "date", "exception_type"], exceptions)
    print(f"Created {len(calendar)} calendar services and {len(exceptions)} exceptions in {output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, default=Path("output/gtfs"))
    args = parser.parse_args()
    generate(args.start_date, args.end_date, args.output)


if __name__ == "__main__":
    main()
