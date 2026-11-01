#!/usr/bin/env python3
"""Map nearest Socobuses reference IDs by sampling actual route geometry.

Observed GPS coordinates are probe positions, NOT confirmed stop locations.
"""
import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://socobuses.co"


def distance_m(a, b):
    lat = math.radians((a[0] + b[0]) / 2)
    return math.hypot((a[0] - b[0]) * 111195, (a[1] - b[1]) * 111195 * math.cos(lat))


def points_on_routes(details, spacing):
    candidates = {}
    for route_id, entry in sorted(details.items(), key=lambda x: int(x[0])):
        route = entry.get("getRouteById") or entry
        coordinates = []
        for loc in sorted(route.get("locations") or [], key=lambda x: x.get("sequence", 0)):
            try:
                lat, lon = float(loc["latitude"]), float(loc["longitude"])
            except (ValueError, KeyError, TypeError):
                continue
            if 4.5 < lat < 6 and -76 < lon < -74:
                coordinates.append((lat, lon))
        if not coordinates:
            continue
        previous = coordinates[0]
        sampled = [previous]
        carried = 0.0
        for point in coordinates[1:]:
            segment = distance_m(previous, point)
            if segment > 2000:  # Discontinuous or invalid geometry; do not interpolate.
                carried = 0
                previous = point
                sampled.append(point)
                continue
            while segment + carried >= spacing and segment > 0:
                ratio = (spacing - carried) / segment
                next_point = (previous[0] + (point[0] - previous[0]) * ratio,
                              previous[1] + (point[1] - previous[1]) * ratio)
                sampled.append(next_point)
                previous = next_point
                segment = distance_m(previous, point)
                carried = 0
            carried += segment
            previous = point
        sampled.append(coordinates[-1])
        for lat, lon in sampled:
            key = (round(lat, 3), round(lon, 3))
            candidates.setdefault(key, {"latitute": round(lat, 7), "longitude": round(lon, 7),
                                        "route_id": route_id})
    return list(candidates.values())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--references", type=Path, required=True)
    p.add_argument("--previous", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("output/reference-coverage.json"))
    p.add_argument("--spacing-m", type=float, default=120)
    p.add_argument("--max-requests", type=int, default=1800)
    p.add_argument("--delay", type=float, default=1.0)
    a = p.parse_args()
    if a.spacing_m < 50 or a.delay < 1 or a.max_requests < 1:
        p.error("spacing >=50m, delay >=1s and max-requests >=1 required")
    details = json.loads(a.source.read_text(encoding="utf-8"))
    refs = json.loads(a.references.read_text(encoding="utf-8"))
    if isinstance(refs, dict):
        refs = next((v for v in refs.values() if isinstance(v, list)), [])
    known = {str(x["referencePointId"]): x.get("name") for x in refs if isinstance(x, dict) and x.get("referencePointId") is not None}
    previous = json.loads(a.previous.read_text(encoding="utf-8"))
    results = []
    seen = set()
    found = set()
    for item in previous.get("results", []):
        point = item.get("sample", {})
        result = (item.get("response") or {}).get("nearestReferencePoint") or {}
        rid = result.get("referencePointId")
        if rid is not None:
            found.add(str(rid))
        if "latitute" in point and "longitude" in point:
            seen.add((round(float(point["latitute"]), 3), round(float(point["longitude"]), 3)))
    candidates = [p for p in points_on_routes(details, a.spacing_m)
                  if (round(p["latitute"], 3), round(p["longitude"], 3)) not in seen]
    # Round-robin route samples to avoid exhausting the request budget on first routes.
    buckets = {}
    for point in candidates:
        buckets.setdefault(point["route_id"], []).append(point)
    samples = []
    while any(buckets.values()) and len(samples) < a.max_requests:
        for route_id in sorted(buckets, key=int):
            if buckets[route_id] and len(samples) < a.max_requests:
                samples.append(buckets[route_id].pop(0))
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": BASE+"/routes",
                            "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"})
    page = session.get(BASE+"/routes", timeout=30)
    page.raise_for_status()
    csrf = BeautifulSoup(page.text, "html.parser").find("meta", attrs={"name": "csrf-token"})
    if csrf:
        session.headers["X-CSRF-TOKEN"] = csrf.get("content", "")
    try:
        for i, point in enumerate(samples, 1):
            time.sleep(a.delay)
            try:
                resp = session.post(BASE+"/site/routes/getNearestReferencePointByPosition",
                                    json={"latitute": point["latitute"], "longitude": point["longitude"]},
                                    timeout=30)
                entry = {"sample": point, "http_status": resp.status_code}
                if resp.status_code in (403, 429):
                    entry["error"] = "Rate limited or forbidden"
                    results.append(entry)
                    break
                try:
                    entry["response"] = resp.json()
                    nearest = entry["response"].get("nearestReferencePoint") or {}
                    if nearest.get("referencePointId") is not None:
                        found.add(str(nearest["referencePointId"]))
                except (ValueError, AttributeError):
                    entry["response_excerpt"] = resp.text[:300]
                results.append(entry)
            except requests.RequestException as exc:
                results.append({"sample": point, "error": str(exc)})
            if i % 100 == 0:
                print(f"probes={i} unique_found={len(found)} missing={len(set(known)-found)}", flush=True)
    finally:
        # Save results even on interruption when Python can handle it.
        a.output.parent.mkdir(parents=True, exist_ok=True)
        output = {"known_reference_count": len(known), "previous_probe_count": len(previous.get("results", [])),
                  "new_request_count": len(results), "candidate_total": len(candidates),
                  "unique_ids_observed": len(found), "known_ids_observed": len(found & set(known)),
                  "missing_reference_points": [{"id": k, "name": v} for k, v in known.items() if k not in found],
                  "statuses": dict(Counter(str(r.get("http_status")) for r in results)),
                  "results": results,
                  "warning": "Probe positions are along route geometry; they are NOT verified reference-point or boarding-stop coordinates."}
        a.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: output[k] for k in ("new_request_count", "candidate_total", "unique_ids_observed", "known_ids_observed")}), flush=True)


if __name__ == "__main__":
    main()
