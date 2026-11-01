#!/usr/bin/env python3
"""Small, rate-limited probe of Socobuses' nearest-reference-point endpoint."""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://socobuses.co"
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("output/nearest-reference-probe.json"))
    p.add_argument("--max-requests", type=int, default=18)
    p.add_argument("--delay", type=float, default=1.5)
    a = p.parse_args()
    if not 1 <= a.max_requests <= 40 or a.delay < 1.0:
        p.error("max-requests must be 1..40 and delay at least 1 second")
    data = json.loads(a.source.read_text(encoding="utf-8"))
    points = []
    for rid, item in sorted(data.items(), key=lambda x: int(x[0])):
        route = item.get("getRouteById") or {}
        coords = []
        for loc in sorted(route.get("locations") or [], key=lambda x: x.get("sequence", 0)):
            try:
                lat, lon = float(loc["latitude"]), float(loc["longitude"])
                if 4.5 < lat < 6 and -76 < lon < -74:
                    coords.append((lat, lon))
            except (ValueError, TypeError, KeyError):
                continue
        if len(coords) >= 2:
            for fraction in (0, 0.25, 0.5, 0.75, 1):
                lat, lon = coords[round((len(coords)-1)*fraction)]
                points.append({"route_id": rid, "fraction": fraction,
                               "latitute": lat, "longitude": lon})
    # Spread requests across routes instead of probing only one route.
    by_fraction = sorted(points, key=lambda x: (x["fraction"], int(x["route_id"])))
    samples = by_fraction[:a.max_requests]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": BASE+"/routes"})
    page = session.get(BASE+"/routes", timeout=30)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")
    csrf = soup.find("meta", attrs={"name": "csrf-token"})
    if csrf:
        session.headers["X-CSRF-TOKEN"] = csrf.get("content", "")
    session.headers["X-Requested-With"] = "XMLHttpRequest"
    session.headers["Accept"] = "application/json"
    results = []
    for sample in samples:
        time.sleep(a.delay)
        try:
            resp = session.post(BASE+"/site/routes/getNearestReferencePointByPosition",
                                json={"latitute": sample["latitute"], "longitude": sample["longitude"]},
                                timeout=30)
            entry = {"sample": sample, "http_status": resp.status_code}
            if resp.status_code in (403, 429):
                entry["error"] = "Access restricted; stopped"
                results.append(entry)
                break
            try:
                entry["response"] = resp.json()
            except ValueError:
                entry["response_excerpt"] = resp.text[:500]
            results.append(entry)
        except requests.RequestException as exc:
            results.append({"sample": sample, "error": str(exc)})
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps({"endpoint": "/site/routes/getNearestReferencePointByPosition",
                                    "request_count": len(results), "results": results,
                                    "note": "Nearest reference points are not confirmed boarding stops; no stop coordinates inferred."},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"requests": len(results), "statuses": dict(Counter(x.get("http_status") for x in results))}))
if __name__ == "__main__":
    main()
