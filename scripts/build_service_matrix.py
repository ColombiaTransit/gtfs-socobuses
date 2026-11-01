#!/usr/bin/env python3
"""Export a route-by-daytype service evidence matrix from cached Socobuses API data.

Positive frequency is evidence of an advertised headway, not proof of operating hours.
Zero frequency is unconfirmed (not automatically 'no service').
"""
import argparse
import csv
import json
from pathlib import Path

DAYTYPES = (
    ("WEEKDAY", "mondayToFridayTimeRoute", "04:30", "22:30"),
    ("SATURDAY", "saturdayTimeRoute", "06:00", "21:00"),
    ("SUNDAY_HOLIDAY", "sundayAndHolidaysTimeRoute", "06:00", "21:00"),
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("output/research/route_service_matrix.csv"))
    args = parser.parse_args()
    data = json.loads(args.source.read_text(encoding="utf-8"))
    rows = []
    for key, payload in sorted(data.items(), key=lambda item: int(item[0])):
        route = (payload or {}).get("getRouteById") or {}
        if not route:
            continue
        for daytype, field, start, end in DAYTYPES:
            raw = route.get(field)
            try:
                frequency = float(raw) if raw is not None and str(raw).strip() else None
            except (ValueError, TypeError):
                frequency = None
            status = ("positive_frequency" if frequency is not None and frequency > 0
                      else "zero_unconfirmed" if frequency == 0
                      else "missing_or_invalid")
            rows.append({
                "route_id": route.get("routeId", key),
                "route_short_name": route.get("routeNumber", ""),
                "service_id": daytype,
                "source_field": field,
                "frequency_minutes_raw": raw,
                "evidence_status": status,
                "general_start_candidate": start,
                "general_end_candidate": end,
                "hours_source": "external general Manizales tourism information; NOT verified for this route",
                "publishable_schedule": "no",
            })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "route_id", "route_short_name", "service_id", "source_field",
            "frequency_minutes_raw", "evidence_status", "general_start_candidate",
            "general_end_candidate", "hours_source", "publishable_schedule"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} route/daytype records to {args.output}")

if __name__ == "__main__":
    main()
