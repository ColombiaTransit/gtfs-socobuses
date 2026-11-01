#!/usr/bin/env python3
"""Audit source timing controls and classify GTFS stop-time readiness.

No interpolated or fabricated stop times are emitted. Source type=3 landmarks
are excluded from potential boarding-stop timing; type 1/2 are candidates only.
"""
import argparse
import csv
import json
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("output/research/timing_readiness.csv"))
    args = p.parse_args()
    raw = json.loads(args.source.read_text(encoding="utf-8"))
    rows = []
    for key, value in sorted(raw.items(), key=lambda kv: int(kv[0])):
        route = (value or {}).get("getRouteById") or {}
        if not route:
            continue
        refs = sorted(route.get("referencePoints") or [], key=lambda x: x.get("sequence", 0))
        controls = []
        for index, ref in enumerate(refs):
            if str(ref.get("type")) != "1":
                continue
            try:
                minute = float(ref.get("timeDifference"))
            except (ValueError, TypeError):
                continue
            if minute > 0:
                controls.append((index, minute))
        nonmonotonic = any(b[1] < a[1] for a, b in zip(controls, controls[1:]))
        status = ("no_positive_controls" if not controls else
                  "nonmonotonic_controls" if nonmonotonic else
                  "controls_usable_for_estimation")
        rows.append({
            "source_route_id": route.get("routeId", key),
            "route_code": route.get("routeNumber", ""),
            "reference_count": len(refs),
            "candidate_stop_occurrences": sum(str(x.get("type")) in ("1", "2") for x in refs),
            "positive_type1_controls": len(controls),
            "first_positive_sequence": refs[controls[0][0]].get("sequence") if controls else "",
            "first_positive_minute": controls[0][1] if controls else "",
            "last_positive_sequence": refs[controls[-1][0]].get("sequence") if controls else "",
            "last_positive_minute": controls[-1][1] if controls else "",
            "last_reference_is_timed": bool(controls and controls[-1][0] == len(refs) - 1),
            "status": status,
            "stop_times_verified": "no",
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    counts = {status: sum(x["status"] == status for x in rows) for status in
              ("controls_usable_for_estimation", "no_positive_controls", "nonmonotonic_controls")}
    print(json.dumps({"routes": len(rows), "statuses": counts}, indent=2))

if __name__ == "__main__":
    main()
