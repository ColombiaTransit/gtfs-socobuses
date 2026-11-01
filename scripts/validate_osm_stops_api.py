#!/usr/bin/env python3
"""Verify deduplicated OSM bus stops with Socobuses nearest-reference API.

A nearest-reference response identifies an API reference near the query position;
it does NOT prove that the OSM feature is an official Socobuses boarding stop.
"""
import argparse
import csv
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://socobuses.co"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", type=Path, required=True)
    p.add_argument("--references", type=Path, required=True)
    p.add_argument("--coverage", type=Path)
    p.add_argument("--output", type=Path, default=Path("output/osm-api-validation"))
    p.add_argument("--max-requests", type=int, default=500)
    p.add_argument("--delay", type=float, default=1.2)
    a = p.parse_args()
    if a.delay < 1 or a.max_requests < 1:
        p.error("delay >= 1 and max-requests >= 1 required")
    raw = json.loads(a.candidates.read_text(encoding="utf-8"))
    refs = json.loads(a.references.read_text(encoding="utf-8"))
    if isinstance(refs, dict):
        refs = next((v for v in refs.values() if isinstance(v, list)), [])
    known = {str(r["referencePointId"]): r.get("name") for r in refs if isinstance(r, dict) and r.get("referencePointId") is not None}
    prior_ids = set()
    if a.coverage and a.coverage.exists():
        coverage = json.loads(a.coverage.read_text(encoding="utf-8"))
        for item in coverage.get("results", []):
            rid = ((item.get("response") or {}).get("nearestReferencePoint") or {}).get("referencePointId")
            if rid is not None:
                prior_ids.add(str(rid))
    grouped = defaultdict(list)
    for r in raw:
        key = (str(r["osm_type"]), str(r["osm_id"]))
        grouped[key].append(r)
    # Query each original OSM stop once, prioritizing close-to-shape candidates.
    ordered = sorted(grouped.items(), key=lambda x: min(float(r["distance_to_shape_m"]) for r in x[1]))
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": BASE+"/routes",
                            "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"})
    page = session.get(BASE+"/routes", timeout=30)
    page.raise_for_status()
    csrf = BeautifulSoup(page.text, "html.parser").find("meta", attrs={"name": "csrf-token"})
    if csrf:
        session.headers["X-CSRF-TOKEN"] = csrf.get("content", "")
    results = []
    a.output.mkdir(parents=True, exist_ok=True)
    try:
        for (osm_type, osm_id), rows in ordered[:a.max_requests]:
            best = min(rows, key=lambda r: float(r["distance_to_shape_m"]))
            sample = {"latitute": best["osm_lat"], "longitude": best["osm_lon"]}
            entry = {"osm_type": osm_type, "osm_id": osm_id, "osm_lat": best["osm_lat"],
                     "osm_lon": best["osm_lon"], "routes": sorted({str(r["route_id"]) for r in rows}),
                     "closest_shape_distance_m": best["distance_to_shape_m"],
                     "osm_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}"}
            time.sleep(a.delay)
            try:
                response = session.post(BASE+"/site/routes/getNearestReferencePointByPosition",
                                        json=sample, timeout=30)
                entry["http_status"] = response.status_code
                if response.status_code in (403, 429):
                    entry["error"] = "Forbidden or rate limited; stopped"
                    results.append(entry)
                    break
                try:
                    data = response.json()
                    nearest = data.get("nearestReferencePoint") or {}
                    rid = nearest.get("referencePointId")
                    if rid is not None:
                        entry["reference_id"] = str(rid)
                        entry["reference_name"] = known.get(str(rid), nearest.get("name"))
                        entry["previously_observed"] = str(rid) in prior_ids
                        entry["api_distance_raw"] = nearest.get("distance")
                        entry["status"] = "api_nearest_reference_observed_not_confirmed_stop"
                    else:
                        entry["status"] = "no_reference_returned"
                except (ValueError, AttributeError):
                    entry["error"] = "Non-JSON response"
                results.append(entry)
            except requests.RequestException as exc:
                entry["error"] = str(exc)
                results.append(entry)
            if len(results) % 100 == 0:
                print(f"Checked {len(results)} unique OSM stops", flush=True)
    finally:
        (a.output/"api_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        fields = ["osm_type", "osm_id", "osm_lat", "osm_lon", "routes", "closest_shape_distance_m",
                  "reference_id", "reference_name", "previously_observed", "api_distance_raw",
                  "http_status", "status", "error", "osm_url"]
        with (a.output/"osm_reference_validation.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for item in results:
                writer.writerow({**item, "routes": ";".join(item["routes"])})
        observed = {r["reference_id"] for r in results if r.get("reference_id")}
        newly_observed = observed - prior_ids
        summary = {"unique_osm_candidates": len(grouped), "requests_attempted": len(results),
                   "api_reference_ids_observed": len(observed),
                   "new_reference_ids_vs_coverage": len(newly_observed),
                   "new_reference_ids": [{"id": rid, "name": known.get(rid)} for rid in sorted(newly_observed, key=int)],
                   "still_missing_from_combined_observations": [{"id": rid, "name": name} for rid, name in known.items()
                                                                 if rid not in (observed | prior_ids)],
                   "http_statuses": dict(Counter(str(r.get("http_status")) for r in results)),
                   "warning": "Nearest-reference API observations are not verified bus stop coordinates."}
        (a.output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: summary[k] for k in ("unique_osm_candidates", "requests_attempted", "api_reference_ids_observed", "new_reference_ids_vs_coverage", "http_statuses")}, indent=2))


if __name__ == "__main__":
    main()
