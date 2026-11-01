#!/usr/bin/env python3
"""EXPERIMENTAL GTFS schedule: synthetic stop positions and service windows.

Never publish this feed as an observed timetable. Route reference points are
landmarks, not confirmed boarding stops. Geometry-based positions are estimates.
"""
import argparse
import csv
import json
from datetime import date
from pathlib import Path

from build_calendar import generate as generate_calendar
from build_gtfs import route_identity


def save(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


def as_interval(value):
    try:
        number = int(value)
        return number if 1 <= number <= 240 else None
    except (TypeError, ValueError):
        return None


def build(source, output, start, end, first, last):
    details = json.loads(source.read_text(encoding="utf-8"))
    stops, trips, times, frequencies, routes, shapes, audit = [], [], [], [], [], [], []
    seen_lines = set()
    services = [("WEEKDAY", "mondayToFridayTimeRoute"),
                ("SATURDAY", "saturdayTimeRoute"),
                ("SUNDAY_HOLIDAY", "sundayAndHolidaysTimeRoute")]
    for key, response in sorted(details.items(), key=lambda item: int(item[0])):
        route = response.get("getRouteById") or {}
        if not route:
            continue
        rid = str(route.get("routeId", key))
        number = str(route.get("routeNumber") or rid)
        geom = sorted(route.get("locations") or [], key=lambda x: x.get("sequence", 0))
        coords = []
        for point in geom:
            try:
                lat, lon = float(point["latitude"]), float(point["longitude"])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    coords.append((lat, lon))
            except (KeyError, ValueError, TypeError):
                pass
        if len(coords) < 2:
            audit.append({"route_id": rid, "issue": "skipped: insufficient geometry"})
            continue
        refs = sorted(route.get("referencePoints") or [], key=lambda x: x.get("sequence", 0))
        if len(refs) < 2:
            audit.append({"route_id": rid, "issue": "skipped: insufficient reference points"})
            continue
        route_name = f'{route.get("startControl") or ""} - {route.get("endControl") or ""}'.strip(" -")
        line_id, direction_id = route_identity(number)
        if line_id not in seen_lines:
            routes.append({"route_id": line_id, "agency_id": "socobuses",
                           "route_short_name": line_id, "route_long_name": "",
                           "route_type": 3})
            seen_lines.add(line_id)
        for i, (lat, lon) in enumerate(coords):
            shapes.append({"shape_id": f"shape_{rid}", "shape_pt_lat": lat,
                           "shape_pt_lon": lon, "shape_pt_sequence": i + 1})
        checkpoints = [(i, int(p["timeDifference"])) for i, p in enumerate(refs)
                       if as_interval(p.get("timeDifference")) is not None or p.get("timeDifference") == 0]
        # Zero values in the source generally mean no timing checkpoint.
        checkpoints = [(0, 0)] + [(i, value) for i, value in checkpoints
                                   if value > 0 and i > 0]
        checkpoints = sorted(set(checkpoints))
        if checkpoints[-1][0] != len(refs) - 1:
            audit.append({"route_id": rid, "issue": f"last reference point has no timing checkpoint; last timed index={checkpoints[-1][0]+1}/{len(refs)}, last timed minute={checkpoints[-1][1]}; excluded pending source verification"})
            continue
        if any(b[1] < a[1] for a, b in zip(checkpoints, checkpoints[1:])):
            audit.append({"route_id": rid, "issue": "nonmonotonic timing checkpoints"})
            continue
        offsets = []
        for i in range(len(refs)):
            left = max((p for p in checkpoints if p[0] <= i), key=lambda p: p[0])
            right = min((p for p in checkpoints if p[0] >= i), key=lambda p: p[0])
            offset = left[1] if left[0] == right[0] else round(
                left[1] + (right[1] - left[1]) * (i - left[0]) / (right[0] - left[0]))
            offsets.append(offset)
            # Proportional placement along geometry is only a placeholder.
            geom_idx = round(i * (len(coords) - 1) / (len(refs) - 1))
            lat, lon = coords[geom_idx]
            stops.append({"stop_id": f"{rid}_{i+1}", "stop_name": str(refs[i].get("name") or f"Reference {i+1}"),
                          "stop_lat": lat, "stop_lon": lon})
        for service_id, field in services:
            interval = as_interval(route.get(field))
            if interval is None:
                audit.append({"route_id": rid, "issue": f"no valid interval: {field}"})
                continue
            trip_id = f"{rid}_{service_id}_template"
            trips.append({"route_id": line_id, "service_id": service_id,
                          "trip_id": trip_id, "shape_id": f"shape_{rid}",
                          "direction_id": direction_id if direction_id is not None else "",
                          "trip_headsign": route.get("endControl") or ""})
            for i, offset in enumerate(offsets):
                t = hhmm(first + offset)
                times.append({"trip_id": trip_id, "arrival_time": t, "departure_time": t,
                              "stop_id": f"{rid}_{i+1}", "stop_sequence": i + 1})
            frequencies.append({"trip_id": trip_id, "start_time": hhmm(first),
                                "end_time": hhmm(last), "headway_secs": interval * 60,
                                "exact_times": 0})
    save(output / "agency.txt", ["agency_id", "agency_name", "agency_url", "agency_timezone"],
         [{"agency_id": "socobuses", "agency_name": "Socobuses",
           "agency_url": "https://socobuses.co", "agency_timezone": "America/Bogota"}])
    save(output / "routes.txt", ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type"], routes)
    save(output / "shapes.txt", ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"], shapes)
    save(output / "stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon"], stops)
    save(output / "trips.txt", ["route_id", "service_id", "trip_id", "shape_id", "direction_id", "trip_headsign"], trips)
    save(output / "stop_times.txt", ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"], times)
    save(output / "frequencies.txt", ["trip_id", "start_time", "end_time", "headway_secs", "exact_times"], frequencies)
    generate_calendar(start, end, output)
    save(output.parent / "research" / "estimated_schedule_issues.csv", ["route_id", "issue"], audit)
    (output.parent / "research" / "ESTIMATES_README.txt").write_text(
        "EXPERIMENTAL ONLY - DO NOT PUBLISH. All stop coordinates are estimated from route geometry "
        "by relative sequence position, not actual stop locations. Reference points may not be stops. "
        "Time differences are interpreted as cumulative minutes and interpolated between checkpoints. "
        f"Operating window {hhmm(first)} to {hhmm(last)} is an experimental departure assumption, not a route-specific published timetable. Socobuses publishes general hours at https://socobuses.com/tourist?language=EN. "
        "Intervals are interpreted as minutes but are not verified. Calendar holiday operation is assumed. "
        "Routes with missing geometry or invalid timing checkpoints are excluded.\n",
        encoding="utf-8")
    print(json.dumps({"routes": len(routes), "estimated_stops": len(stops),
                      "template_trips": len(trips), "frequency_entries": len(frequencies),
                      "issues": len(audit)}, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("output/experimental_gtfs"))
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--assumed-first-departure", type=int, default=360)
    p.add_argument("--assumed-last-departure", type=int, default=1200)
    args = p.parse_args()
    if not (0 <= args.assumed_first_departure < args.assumed_last_departure <= 1440):
        p.error("Invalid assumed operating window")
    build(args.source, args.output, date.fromisoformat(args.start_date),
          date.fromisoformat(args.end_date), args.assumed_first_departure,
          args.assumed_last_departure)


if __name__ == "__main__":
    main()
