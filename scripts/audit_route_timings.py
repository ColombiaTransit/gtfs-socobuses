#!/usr/bin/env python3
"""Audit Socobuses route interval and reference-point time fields without inventing GTFS trips."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

FIELDS = {"weekday": "mondayToFridayTimeRoute", "saturday": "saturdayTimeRoute",
          "sunday_holiday": "sundayAndHolidaysTimeRoute"}

def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def number(v):
    try:
        return float(v) if v is not None and str(v).strip() else None
    except (ValueError, TypeError):
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--details", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path("output/timing-audit"))
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    data = json.loads(a.details.read_text(encoding="utf-8"))
    routes, timing, anomalies = [], [], []
    intervals = {k: Counter() for k in FIELDS}
    types = Counter()
    nonzero_types = Counter()
    for key, record in sorted(data.items(), key=lambda x: int(x[0])):
        route = (record or {}).get("getRouteById") or {}
        if not route:
            anomalies.append({"route_id": key, "kind": "missing_route", "detail": "No getRouteById payload"})
            continue
        rid = str(route.get("routeId", key))
        points = sorted(route.get("referencePoints") or [], key=lambda p: number(p.get("sequence")) or 0)
        item = {"route_id": rid, "route_number": route.get("routeNumber"),
                "start_control": route.get("startControl"), "end_control": route.get("endControl"),
                "point_count": len(points), "geometry_points": len(route.get("locations") or [])}
        for label, field in FIELDS.items():
            raw = route.get(field)
            val = number(raw)
            item[label+"_raw"] = raw
            item[label+"_minutes_candidate"] = val
            intervals[label][str(raw)] += 1
            if val is None or val < 0:
                anomalies.append({"route_id": rid, "kind": "invalid_interval", "detail": field+"="+str(raw)})
        positive = []
        for p in points:
            t = number(p.get("timeDifference"))
            typ = str(p.get("type"))
            types[typ] += 1
            if t is not None and t > 0:
                nonzero_types[typ] += 1
                positive.append((p.get("sequence"), t, p.get("name")))
            timing.append({"route_id": rid, "route_number": route.get("routeNumber"),
                           "sequence": p.get("sequence"), "reference_point_id": p.get("referencePointId"),
                           "reference_name": p.get("name"), "type_raw": p.get("type"),
                           "time_difference_raw": p.get("timeDifference"),
                           "elapsed_minutes_candidate": t if t is not None and t > 0 else "",
                           "note": "nonzero cumulative candidate" if t is not None and t > 0 else "unknown, NOT zero travel time"})
        for before, after in zip(positive, positive[1:]):
            if after[1] < before[1]:
                anomalies.append({"route_id": rid, "kind": "nonmonotonic_elapsed",
                                  "detail": f"seq {before[0]}={before[1]} -> {after[0]}={after[1]}"})
        item["timed_control_points"] = len(positive)
        item["last_positive_time_minutes"] = positive[-1][1] if positive else ""
        if not positive:
            anomalies.append({"route_id": rid, "kind": "no_positive_control_times", "detail": ""})
        routes.append(item)
    write_csv(a.output/"route_intervals.csv", routes,
              ["route_id","route_number","start_control","end_control","point_count","geometry_points",
               *[f"{k}_{suffix}" for k in FIELDS for suffix in ("raw","minutes_candidate")],
               "timed_control_points","last_positive_time_minutes"])
    write_csv(a.output/"reference_timing.csv", timing,
              ["route_id","route_number","sequence","reference_point_id","reference_name",
               "type_raw","time_difference_raw","elapsed_minutes_candidate","note"])
    write_csv(a.output/"anomalies.csv", anomalies, ["route_id","kind","detail"])
    summary = {"routes_with_details": len(routes), "reference_point_occurrences": len(timing),
               "positive_time_difference_occurrences": sum(nonzero_types.values()),
               "type_counts": dict(types), "positive_time_difference_by_type": dict(nonzero_types),
               "interval_value_distributions": {k: dict(v) for k,v in intervals.items()},
               "anomalies": Counter(x["kind"] for x in anomalies),
               "interpretation": {"route_interval_fields": "Candidate headways in minutes; requires source verification",
                                  "timeDifference": "Candidate cumulative elapsed minutes for timed control points (type 1)",
                                  "zero": "Unknown/non-timed reference point; never infer zero travel time",
                                  "schedule": "No first/last departures or operating windows confirmed; do not generate GTFS trips or frequencies from this audit"}}
    summary["anomalies"] = dict(summary["anomalies"])
    (a.output/"summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
