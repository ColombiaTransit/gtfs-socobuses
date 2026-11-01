#!/usr/bin/env python3
"""Convert cached Socobuses API route data into a conservative GTFS draft.

No stop coordinates, trips, stop_times or frequencies are invented.
"""
import argparse
import csv
import json
import re
from pathlib import Path

from build_calendar import generate as generate_calendar


def csv_file(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def route_identity(number):
    """Return GTFS line ID and direction from Socobuses i/r suffix.

    Preserve a variant prefix (e.g. 613v). Unrecognized codes remain separate.
    """
    match = re.fullmatch(r"(.+)([ir])", number, flags=re.IGNORECASE)
    if not match:
        return number, None
    return match.group(1), 0 if match.group(2).lower() == "i" else 1


def build(source, output, start, end):
    raw = json.loads(source.read_text(encoding="utf-8"))
    routes, shapes, points, intervals, problems, directions = [], [], [], [], [], []
    seen_lines = set()
    for key, response in sorted(raw.items(), key=lambda kv: int(kv[0])):
        route = response.get("getRouteById") or {}
        if not route:
            problems.append({"route_id": key, "issue": "missing route details"})
            continue
        rid = str(route.get("routeId", key))
        number = str(route.get("routeNumber") or rid)
        start_name = route.get("startControl") or ""
        end_name = route.get("endControl") or ""
        coords = sorted(route.get("locations") or [], key=lambda p: p.get("sequence", 0))
        valid = []
        for p in coords:
            try:
                lat, lon = float(p["latitude"]), float(p["longitude"])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    valid.append((lat, lon))
            except (KeyError, TypeError, ValueError):
                pass
        shape_id = f"shape_{rid}" if len(valid) >= 2 else ""
        line_id, direction_id = route_identity(number)
        if line_id not in seen_lines:
            routes.append({
                "route_id": line_id, "agency_id": "socobuses",
                "route_short_name": line_id, "route_long_name": "",
                "route_type": 3,
            })
            seen_lines.add(line_id)
        directions.append({
            "socobuses_route_id": rid, "socobuses_route_code": number,
            "gtfs_route_id": line_id, "direction_id": direction_id if direction_id is not None else "",
            "trip_headsign_candidate": end_name,
            "shape_id": shape_id,
            "note": "direction mapping only; no observed departures or stop times",
        })
        for seq, (lat, lon) in enumerate(valid, 1):
            shapes.append({"shape_id": shape_id, "shape_pt_lat": lat,
                           "shape_pt_lon": lon, "shape_pt_sequence": seq})
        if not shape_id:
            problems.append({"route_id": rid, "issue": "no usable route geometry"})
        for p in sorted(route.get("referencePoints") or [], key=lambda x: x.get("sequence", 0)):
            points.append({
                "route_id": rid, "route_short_name": number,
                "reference_point_id": p.get("referencePointId"),
                "name": p.get("name"), "sequence": p.get("sequence"),
                "time_difference_raw": p.get("timeDifference"), "type_raw": p.get("type"),
            })
        for service_id, field in [
            ("WEEKDAY", "mondayToFridayTimeRoute"),
            ("SATURDAY", "saturdayTimeRoute"),
            ("SUNDAY_HOLIDAY", "sundayAndHolidaysTimeRoute"),
        ]:
            value = route.get(field)
            intervals.append({"route_id": rid, "service_id": service_id,
                              "source_field": field, "raw_value": value})
    csv_file(output / "agency.txt",
             ["agency_id", "agency_name", "agency_url", "agency_timezone"],
             [{"agency_id": "socobuses", "agency_name": "Socobuses",
               "agency_url": "https://socobuses.co", "agency_timezone": "America/Bogota"}])
    csv_file(output / "routes.txt",
             ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type"], routes)
    csv_file(output / "shapes.txt",
             ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"], shapes)
    generate_calendar(start, end, output)
    research = output.parent / "research"
    csv_file(research / "route_reference_points.csv",
             ["route_id", "route_short_name", "reference_point_id", "name", "sequence",
              "time_difference_raw", "type_raw"], points)
    csv_file(research / "route_service_intervals.csv",
             ["route_id", "service_id", "source_field", "raw_value"], intervals)
    csv_file(research / "route_directions.csv",
             ["socobuses_route_id", "socobuses_route_code", "gtfs_route_id",
              "direction_id", "trip_headsign_candidate", "shape_id", "note"], directions)
    csv_file(research / "issues.csv", ["route_id", "issue"], problems)
    summary = {
        "gtfs_lines": len(routes), "source_direction_routes": len(directions), "routes_with_geometry": len({x["shape_id"] for x in shapes}),
        "shape_points": len(shapes), "reference_point_occurrences": len(points),
        "issues": len(problems),
        "warning": "DRAFT ONLY: reference points are not verified stops; no stops, trips, stop_times or frequencies generated.",
    }
    (research / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, default=Path("cache/route_details.json"))
    p.add_argument("--output", type=Path, default=Path("output/gtfs"))
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    a = p.parse_args()
    from datetime import date
    build(a.source, a.output, date.fromisoformat(a.start_date), date.fromisoformat(a.end_date))


if __name__ == "__main__":
    main()
