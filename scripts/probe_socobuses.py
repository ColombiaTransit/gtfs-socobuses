#!/usr/bin/env python3
"""Bounded Socobuses route discovery with resumable cached API responses."""
import argparse
import json
import logging
from pathlib import Path
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://socobuses.co"
OUT = Path("output")
CACHE = Path("cache")
LOG = logging.getLogger("socobuses")


def read(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def sample(seq, count):
    if len(seq) <= count:
        return seq
    if count == 1:
        return seq[:1]
    return [seq[round(i * (len(seq) - 1) / (count - 1))] for i in range(count)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true", help="Try all reference points and valid destinations, with safety budget")
    p.add_argument("--max-requests", type=int, default=500)
    p.add_argument("--origin-offset", type=int, default=0)
    p.add_argument("--max-origins", type=int, default=12)
    p.add_argument("--max-destinations", type=int, default=12)
    p.add_argument("--max-routes", type=int, default=50)
    p.add_argument("--delay", type=float, default=1.5)
    a = p.parse_args()
    if not (0 <= a.origin_offset <= 500 and 1 <= a.max_origins <= 20
            and 1 <= a.max_destinations <= 20 and 1 <= a.max_routes <= 100
            and a.delay >= 1 and 1 <= a.max_requests <= 1000):
        p.error("Limits: offset 0-500, origins 1-20, destinations 1-20, routes 1-100, delay >= 1")
    s = requests.Session()
    s.headers.update({"User-Agent": "ColombiaTransit-Socobuses-Research/0.2 (manual, limited)",
                      "Accept": "application/json, text/plain, */*"})
    page = s.get(BASE + "/routes", timeout=30)
    page.raise_for_status()
    csrf = BeautifulSoup(page.text, "html.parser").select_one('meta[name="csrf-token"]')
    if not csrf or not csrf.get("content"):
        raise RuntimeError("No CSRF meta tag found")
    s.headers.update({"X-CSRF-TOKEN": csrf["content"], "Referer": BASE + "/routes"})

    def get(path):
        r = s.get(BASE + path, timeout=30)
        r.raise_for_status()
        return r.json()

    def post(path, data):
        time.sleep(a.delay)
        r = s.post(BASE + path, json=data, timeout=30)
        r.raise_for_status()
        return r.json()

    refs = get("/site/routes/getPointsReference")
    write(OUT / "reference_points.json", refs)
    if not refs.get("status"):
        raise RuntimeError("Reference endpoint returned status=false")
    ids = [x["referencePointId"] for x in refs.get("getPointReference", [])
           if isinstance(x, dict) and "referencePointId" in x]
    origins = ids if a.all else ids[a.origin_offset:a.origin_offset + a.max_origins]
    started = time.monotonic()
    requests_made = 0
    stopped_reason = None

    def budget():
        nonlocal requests_made, stopped_reason
        if requests_made >= a.max_requests or time.monotonic() - started > 1200:
            stopped_reason = "request_limit" if requests_made >= a.max_requests else "time_limit"
            return False
        requests_made += 1
        return True
    index = read(CACHE / "route_index.json", {})
    details = read(CACHE / "route_details.json", {})
    filters = read(CACHE / "filtered_routes.json", {})
    destinations_cache = read(CACHE / "destinations.json", {})
    errors = []
    new_filters = 0
    for origin in origins:
        key = str(origin)
        if key not in destinations_cache:
            if not budget():
                break
            try:
                destinations_cache[key] = post("/site/routes/getPointsReferenceDestination",
                                               {"referencePointIdOrigin": origin})
                write(CACHE / "destinations.json", destinations_cache)
            except (requests.RequestException, ValueError, TypeError) as exc:
                if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code in (403, 429):
                    stopped_reason = f"HTTP {exc.response.status_code}"
                    break
                errors.append({"stage": "destinations", "origin": origin, "error": str(exc)})
                continue
        response = destinations_cache[key]
        if not isinstance(response, dict):
            errors.append({"stage": "destinations", "origin": origin, "error": "Unexpected response"})
            continue
        allowed = [x["referencePointId"] for x in response.get("getPointReference", [])
                   if isinstance(x, dict) and "referencePointId" in x
                   and x["referencePointId"] != origin]
        for dest in (allowed if a.all else sample(allowed, a.max_destinations)):
            pair = f"{origin}:{dest}"
            if pair in filters:
                continue
            if not budget():
                break
            try:
                result = post("/site/routes/getFilteredRoutes", {
                    "idReferencePointOrigin": origin,
                    "idReferencePointDestination": dest,
                    "wheelchair": False,
                })
                filters[pair] = result
                new_filters += 1
                for item in result.get("getRouteWithFilter", []):
                    if isinstance(item, dict) and item.get("routeId") is not None:
                        index[str(item["routeId"])] = item
                write(CACHE / "filtered_routes.json", filters)
                write(CACHE / "route_index.json", index)
            except (requests.RequestException, ValueError, TypeError) as exc:
                if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code in (403, 429):
                    stopped_reason = f"HTTP {exc.response.status_code}"
                    break
                errors.append({"stage": "filtered", "origin": origin, "destination": dest,
                               "error": str(exc)})
        if stopped_reason:
            break
    for route_id in list(index):
        if (not a.all and len(details) >= a.max_routes) or not budget():
            break
        if route_id in details:
            continue
        try:
            result = post("/site/routes/getRouteById", {"routeId": int(route_id)})
            if isinstance(result, dict) and result.get("status") and result.get("getRouteById"):
                details[route_id] = result
                write(CACHE / "route_details.json", details)
            else:
                errors.append({"stage": "detail", "routeId": route_id,
                               "error": "Unexpected response"})
        except (requests.RequestException, ValueError, TypeError) as exc:
            if isinstance(exc, requests.HTTPError) and exc.response is not None and exc.response.status_code in (403, 429):
                stopped_reason = f"HTTP {exc.response.status_code}"
                break
            errors.append({"stage": "detail", "routeId": route_id, "error": str(exc)})

    # Include all accumulated data in the downloadable artifact.
    write(OUT / "destinations.json", destinations_cache)
    write(OUT / "filtered_routes.json", filters)
    write(OUT / "route_index.json", index)
    write(OUT / "route_details.json", details)
    summary = {
        "reference_points": len(ids), "origin_offset": a.origin_offset,
        "origins_this_run": origins, "new_filter_queries": new_filters,
        "total_filter_queries_cached": len(filters),
        "unique_routes": len(index), "route_details": len(details),
        "requests_this_run": requests_made, "stopped_reason": stopped_reason,
        "all_mode": a.all, "errors": errors,
    }
    write(OUT / "summary.json", summary)
    LOG.info("Probe summary: %s", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
