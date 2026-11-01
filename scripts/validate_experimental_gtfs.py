#!/usr/bin/env python3
"""Check structural integrity of Socobuses' NON-PUBLISHABLE experimental GTFS."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def seconds(value):
    h, m, s = map(int, value.split(":"))
    return h * 3600 + m * 60 + s


def validate(root):
    feed = root / "experimental_gtfs"
    names = ("routes", "trips", "stops", "stop_times", "shapes", "frequencies", "calendar")
    data = {name: read_csv(feed / (name + ".txt")) for name in names}
    issues = read_csv(root / "research" / "estimated_schedule_issues.csv")
    timing = read_csv(root / "research" / "timing_readiness.csv")
    errors = []
    routes = {r["route_id"] for r in data["routes"]}
    stops = {s["stop_id"] for s in data["stops"]}
    shapes = {s["shape_id"] for s in data["shapes"]}
    services = {s["service_id"] for s in data["calendar"]}
    trips = {t["trip_id"]: t for t in data["trips"]}
    if len(trips) != len(data["trips"]):
        errors.append("duplicate trip_id")
    if len(routes) != len(data["routes"]):
        errors.append("duplicate route_id")
    for t in data["trips"]:
        if t["route_id"] not in routes or t["shape_id"] not in shapes or t["service_id"] not in services:
            errors.append("trip has invalid route/shape/service reference: " + t["trip_id"])
        if t["direction_id"] not in ("0", "1"):
            errors.append("missing/invalid direction_id: " + t["trip_id"])
    by_trip = {}
    for st in data["stop_times"]:
        if st["trip_id"] not in trips or st["stop_id"] not in stops:
            errors.append("invalid stop_time reference: " + st["trip_id"])
        by_trip.setdefault(st["trip_id"], []).append(st)
    for tid, entries in by_trip.items():
        entries.sort(key=lambda x: int(x["stop_sequence"]))
        if any(seconds(b["arrival_time"]) < seconds(a["departure_time"]) for a, b in zip(entries, entries[1:])):
            errors.append("decreasing times: " + tid)
        if any(seconds(e["departure_time"]) < seconds(e["arrival_time"]) for e in entries):
            errors.append("departure before arrival: " + tid)
    expected_windows = {"WEEKDAY": ("04:30:00", "22:30:00"),
                        "SATURDAY": ("06:00:00", "21:00:00"),
                        "SUNDAY_HOLIDAY": ("06:00:00", "21:00:00")}
    frequency_counts = Counter()
    for f in data["frequencies"]:
        t = trips.get(f["trip_id"])
        if not t:
            errors.append("frequency references unknown trip: " + f["trip_id"])
            continue
        sid = t["service_id"]
        frequency_counts[sid] += 1
        if (f["start_time"], f["end_time"]) != expected_windows[sid]:
            errors.append("unexpected daytype window: " + f["trip_id"])
        if f["exact_times"] != "0" or int(f["headway_secs"]) <= 0:
            errors.append("invalid frequency settings: " + f["trip_id"])
        if f["trip_id"] not in by_trip or len(by_trip[f["trip_id"]]) < 2:
            errors.append("frequency template missing stop_times: " + f["trip_id"])
    if len(data["frequencies"]) != len(trips):
        errors.append("frequency and template-trip counts differ")
    blocked = {str(x["source_route_id"]) for x in timing
               if x["status"] != "controls_usable_for_estimation"}
    for rid in blocked:
        if any(tid.startswith(rid + "_") for tid in trips):
            errors.append("blocked timing route emitted trips: " + rid)
    zero_sunday = {x["route_id"] for x in issues
                   if x["issue"] == "no valid interval: sundayAndHolidaysTimeRoute"}
    for rid in zero_sunday:
        if rid + "_SUNDAY_HOLIDAY_template" in trips:
            errors.append("zero Sunday interval emitted trip: " + rid)
    report = {
        "status": "pass" if not errors else "fail",
        "publication_status": "EXPERIMENTAL_ONLY_DO_NOT_PUBLISH",
        "counts": {name: len(rows) for name, rows in data.items()},
        "templates_by_daytype": dict(Counter(t["service_id"] for t in data["trips"])),
        "frequency_rows_by_daytype": dict(frequency_counts),
        "source_routes": len(timing),
        "timing_blocked_routes": sorted(blocked, key=int),
        "zero_sunday_route_ids_reported": sorted(zero_sunday, key=int),
        "issues": [dict(x) for x in issues],
        "errors": errors,
        "limitations": [
            "Reference points are not validated boarding stops",
            "Stop positions and intermediate passing times are synthetic",
            "General operating hours are not confirmed route-specific departures",
            "MobilityData validator findings are separate from this structural check",
        ],
    }
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    report = validate(args.root)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "issues"}, indent=2))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
