#!/usr/bin/env python3
"""Probe one geometry-derived candidate per known reference point; report actual matches."""
import argparse
import json
import time
from collections import Counter
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE = "https://socobuses.co"

def unwrap(item):
    return item.get("getRouteById") or item

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--references", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("output/nearest-reference-probe.json"))
    p.add_argument("--delay", type=float, default=1.5)
    a = p.parse_args()
    if a.delay < 1.0:
        p.error("delay must be >= 1 second")
    details = json.loads(a.source.read_text(encoding="utf-8"))
    reference_data = json.loads(a.references.read_text(encoding="utf-8"))
    if isinstance(reference_data, dict):
        reference_data = next((v for v in reference_data.values() if isinstance(v, list)), [])
    known = {str(x.get("referencePointId")): x.get("name") for x in reference_data
             if isinstance(x, dict) and x.get("referencePointId") is not None}
    candidates = {}
    for rid, item in sorted(details.items(), key=lambda x: int(x[0])):
        route = unwrap(item)
        coords = []
        for loc in sorted(route.get("locations") or [], key=lambda x: x.get("sequence", 0)):
            try:
                lat, lon = float(loc["latitude"]), float(loc["longitude"])
                if 4.5 < lat < 6 and -76 < lon < -74:
                    coords.append((lat, lon))
            except (KeyError, ValueError, TypeError):
                pass
        refs = sorted(route.get("referencePoints") or [], key=lambda x: x.get("sequence", 0))
        if len(coords) < 2 or len(refs) < 2:
            continue
        for i, ref in enumerate(refs):
            refid = ref.get("referencePointId")
            if refid is None:
                continue
            refid = str(refid)
            if refid not in known or refid in candidates:
                continue
            lat, lon = coords[round(i * (len(coords)-1)/(len(refs)-1))]
            candidates[refid] = {"target_reference_id": refid, "route_id": rid,
                                 "reference_sequence": i+1, "latitute": lat, "longitude": lon}
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": BASE+"/routes",
                            "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"})
    page = session.get(BASE+"/routes", timeout=30)
    page.raise_for_status()
    csrf = BeautifulSoup(page.text, "html.parser").find("meta", attrs={"name": "csrf-token"})
    if csrf:
        session.headers["X-CSRF-TOKEN"] = csrf.get("content", "")
    results = []
    for sample in candidates.values():
        time.sleep(a.delay)
        try:
            response = session.post(BASE+"/site/routes/getNearestReferencePointByPosition",
                                    json={"latitute": sample["latitute"], "longitude": sample["longitude"]},
                                    timeout=30)
            entry = {"sample": sample, "http_status": response.status_code}
            if response.status_code in (403, 429):
                entry["error"] = "Rate limited or forbidden; stopped"
                results.append(entry)
                break
            try:
                entry["response"] = response.json()
            except ValueError:
                entry["response_excerpt"] = response.text[:300]
            results.append(entry)
        except requests.RequestException as exc:
            results.append({"sample": sample, "error": str(exc)})
    output = {"known_reference_count": len(known), "candidate_count": len(candidates),
              "without_geometry_candidate": [{"id": k, "name": v} for k,v in known.items() if k not in candidates],
              "request_count": len(results), "statuses": dict(Counter(str(x.get("http_status")) for x in results)),
              "results": results, "warning": "Candidate coordinates are estimates, not verified reference point locations or bus stops."}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: output[k] for k in ("known_reference_count", "candidate_count", "request_count", "statuses")}))
if __name__ == "__main__":
    main()
