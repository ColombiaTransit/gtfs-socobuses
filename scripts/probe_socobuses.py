#!/usr/bin/env python3
"""Manual, bounded research probe of the public Socobuses API."""
import argparse
import json
import logging
import pathlib
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://socobuses.co"
OUTPUT = pathlib.Path("output")
LOG = logging.getLogger("socobuses")


def write_json(filename, payload):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / filename).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def sampled(values, count):
    if not values:
        return []
    if count == 1:
        return values[:1]
    return list(dict.fromkeys(
        values[round(i * (len(values) - 1) / (min(count, len(values)) - 1))]
        for i in range(min(count, len(values)))
    ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-origins", type=int, default=3)
    parser.add_argument("--max-destinations", type=int, default=8)
    parser.add_argument("--max-routes", type=int, default=15)
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()
    if not (1 <= args.max_origins <= 10
            and 1 <= args.max_destinations <= 20
            and 1 <= args.max_routes <= 50 and args.delay >= 1):
        parser.error("Limits: origins 1-10, destinations 1-20, routes 1-50, delay >= 1")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "ColombiaTransit-Socobuses-Research/0.1 (manual limited probe)",
        "Accept": "application/json, text/plain, */*",
    })
    page = session.get(BASE + "/routes", timeout=30)
    page.raise_for_status()
    csrf = BeautifulSoup(page.text, "html.parser").select_one('meta[name="csrf-token"]')
    if not csrf or not csrf.get("content"):
        raise RuntimeError("Missing CSRF token on /routes")
    session.headers.update({
        "X-CSRF-TOKEN": csrf["content"],
        "Referer": BASE + "/routes",
    })

    def get(path):
        response = session.get(BASE + path, timeout=30)
        response.raise_for_status()
        return response.json()

    def post(path, payload):
        time.sleep(args.delay)
        response = session.post(BASE + path, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    references = get("/site/routes/getPointsReference")
    write_json("reference_points.json", references)
    if not references.get("status"):
        raise RuntimeError("Reference point query returned status=false")
    ids = [p["referencePointId"] for p in references.get("getPointReference", [])
           if isinstance(p, dict) and "referencePointId" in p]
    origins = sampled(ids, args.max_origins)
    destinations = sampled(ids, args.max_destinations)
    errors, filtered, found, details = [], [], {}, {}

    for origin in origins:
        try:
            response = post("/site/routes/getPointsReferenceDestination",
                            {"referencePointIdOrigin": origin})
            write_json(f"destinations_{origin}.json", response)
            allowed = {p["referencePointId"] for p in response.get("getPointReference", [])
                       if isinstance(p, dict) and "referencePointId" in p}
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            errors.append({"stage": "destinations", "origin": origin, "error": str(exc)})
            continue
        for destination in destinations:
            if origin == destination or destination not in allowed:
                continue
            try:
                response = post("/site/routes/getFilteredRoutes", {
                    "idReferencePointOrigin": origin,
                    "idReferencePointDestination": destination,
                    "wheelchair": False,
                })
                filtered.append({"origin": origin, "destination": destination,
                                 "response": response})
                for route in response.get("getRouteWithFilter", []):
                    if isinstance(route, dict) and route.get("routeId") is not None:
                        found[str(route["routeId"])] = route
            except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
                errors.append({"stage": "filtered", "origin": origin,
                               "destination": destination, "error": str(exc)})

    write_json("filtered_routes.json", filtered)
    write_json("route_index.json", found)
    for route_id in list(found)[:args.max_routes]:
        try:
            details[route_id] = post("/site/routes/getRouteById",
                                     {"routeId": int(route_id)})
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            errors.append({"stage": "details", "routeId": route_id, "error": str(exc)})
    write_json("route_details.json", details)
    summary = {
        "reference_points": len(ids), "sampled_origins": origins,
        "sampled_destinations": destinations, "filter_responses": len(filtered),
        "unique_routes": len(found), "route_details": len(details),
        "errors": errors,
    }
    write_json("summary.json", summary)
    LOG.info("Probe summary: %s", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
