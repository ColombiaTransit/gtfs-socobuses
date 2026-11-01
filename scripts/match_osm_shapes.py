#!/usr/bin/env python3
"""Match OSM bus stops and named landmarks to Socobuses route shapes.

OSM coordinates remain untouched. Projected coordinates are analytical only.
No match is asserted as a confirmed boarding stop without independent evidence.
"""
import argparse
import csv
import json
import math
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import requests

BBOX = (4.95, -75.65, 5.15, -75.40)
FIELDS = ["reference_id", "reference_name", "route_id", "reference_sequence",
          "osm_type", "osm_id", "osm_name", "osm_category", "osm_lat", "osm_lon",
          "projected_lat", "projected_lon", "distance_to_shape_m",
          "position_along_shape_m", "name_similarity", "status", "evidence",
          "osm_url"]


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def distance(a, b):
    lat = math.radians((a[0] + b[0]) / 2)
    return math.hypot((a[0]-b[0])*111195, (a[1]-b[1])*111195*math.cos(lat))


def project(p, shape):
    best = None
    cumulative = 0.0
    for a, b in zip(shape, shape[1:]):
        length = distance(a, b)
        if length > 2000 or length < 0.001:
            cumulative += length
            continue
        k = 111195 * math.cos(math.radians((a[0]+b[0]+p[0])/3))
        ax, ay = a[1]*k, a[0]*111195
        bx, by = b[1]*k, b[0]*111195
        px, py = p[1]*k, p[0]*111195
        t = max(0, min(1, ((px-ax)*(bx-ax)+(py-ay)*(by-ay))/((bx-ax)**2+(by-ay)**2)))
        q = (a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1]))
        d = distance(p, q)
        if best is None or d < best[0]:
            best = (d, q, cumulative+t*length)
        cumulative += length
    return best


def fetch_osm():
    bbox = ",".join(map(str, BBOX))
    query = f"""[out:json][timeout:180];
(
 nwr["highway"="bus_stop"]({bbox});
 nwr["public_transport"="platform"]["bus"="yes"]({bbox});
 nwr["amenity"="bus_station"]({bbox});
 nwr["place"~"neighbourhood|suburb|quarter|locality"]["name"]({bbox});
 nwr["amenity"~"school|hospital|clinic|university|marketplace"]["name"]({bbox});
 nwr["leisure"="park"]["name"]({bbox});
 nwr["shop"="supermarket"]["name"]({bbox});
);
out center tags;"""
    for endpoint in ("https://overpass.kumi.systems/api/interpreter",
                     "https://overpass-api.de/api/interpreter"):
        try:
            response = requests.post(endpoint, data={"data": query}, timeout=240,
                                     headers={"User-Agent": "ColombiaTransit-GTFS-research/1.0"})
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"Overpass endpoint failed: {endpoint}: {exc}", flush=True)
    raise RuntimeError("Both Overpass endpoints failed")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--details", type=Path, required=True)
    p.add_argument("--references", type=Path, required=True)
    p.add_argument("--osm", type=Path, help="Optional local Overpass JSON export")
    p.add_argument("--output", type=Path, default=Path("output/osm-shape-matches"))
    p.add_argument("--max-distance-m", type=float, default=120)
    a = p.parse_args()
    if a.max_distance_m <= 0:
        p.error("max-distance-m must be positive")
    a.output.mkdir(parents=True, exist_ok=True)
    osm = json.loads(a.osm.read_text(encoding="utf-8")) if a.osm else fetch_osm()
    (a.output/"osm_raw.json").write_text(json.dumps(osm, ensure_ascii=False, indent=2), encoding="utf-8")
    details = json.loads(a.details.read_text(encoding="utf-8"))
    references = json.loads(a.references.read_text(encoding="utf-8"))
    if isinstance(references, dict):
        references = next((v for v in references.values() if isinstance(v, list)), [])
    names = {str(x["referencePointId"]): x.get("name", "") for x in references
             if isinstance(x, dict) and x.get("referencePointId") is not None}
    features = []
    for item in osm.get("elements", []):
        tags = item.get("tags") or {}
        center = item.get("center") or item
        if "lat" not in center or "lon" not in center:
            continue
        category = ("bus_stop" if tags.get("highway") == "bus_stop" or
                    (tags.get("public_transport") == "platform" and tags.get("bus") == "yes")
                    else "bus_station" if tags.get("amenity") == "bus_station"
                    else "landmark")
        features.append({"id": item["id"], "type": item["type"], "lat": float(center["lat"]),
                         "lon": float(center["lon"]), "name": tags.get("name", ""),
                         "category": category})
    rows = []
    routes_processed = 0
    for route_id, entry in details.items():
        route = entry.get("getRouteById") or entry
        shape = []
        for loc in sorted(route.get("locations") or [], key=lambda x: x.get("sequence", 0)):
            try:
                pt = (float(loc["latitude"]), float(loc["longitude"]))
                if 4.5 < pt[0] < 6 and -76 < pt[1] < -74:
                    shape.append(pt)
            except (KeyError, ValueError, TypeError):
                pass
        if len(shape) < 2:
            continue
        routes_processed += 1
        refs = sorted(route.get("referencePoints") or [], key=lambda x: x.get("sequence", 0))
        # Reference sequence is NOT assumed to align linearly with shape distance.
        # Therefore all nearby OSM candidates are reported; no fabricated stop ordering.
        nearby = []
        for feat in features:
            projection = project((feat["lat"], feat["lon"]), shape)
            if projection and projection[0] <= a.max_distance_m:
                nearby.append((feat, projection))
        for idx, ref in enumerate(refs, 1):
            ref_id = str(ref.get("referencePointId", ""))
            ref_name = ref.get("name") or names.get(ref_id, "")
            scored = []
            for feat, (dist, projected, position) in nearby:
                similarity = SequenceMatcher(None, norm(ref_name), norm(feat["name"])).ratio() if feat["name"] else 0
                # Do not match unnamed stops to an arbitrary reference point by proximity alone.
                if similarity < 0.55:
                    continue
                scored.append((similarity, dist, feat, projected, position))
            scored.sort(key=lambda x: (-x[0], x[1]))
            for similarity, dist, feat, projected, position in scored[:5]:
                status = ("waarschijnlijk" if similarity >= 0.85 and dist <= 60
                          else "onzeker")
                rows.append({
                    "reference_id": ref_id, "reference_name": ref_name, "route_id": route_id,
                    "reference_sequence": ref.get("sequence", idx),
                    "osm_type": feat["type"], "osm_id": feat["id"],
                    "osm_name": feat["name"], "osm_category": feat["category"],
                    "osm_lat": feat["lat"], "osm_lon": feat["lon"],
                    "projected_lat": round(projected[0], 7),
                    "projected_lon": round(projected[1], 7),
                    "distance_to_shape_m": round(dist, 1),
                    "position_along_shape_m": round(position, 1),
                    "name_similarity": round(similarity, 3),
                    "status": status, "evidence": "OSM name similarity + proximity to route shape; API not checked",
                    "osm_url": f"https://www.openstreetmap.org/{feat['type']}/{feat['id']}"})
    with (a.output/"reference_matches.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    matched_ids = {r["reference_id"] for r in rows}
    with (a.output/"unmatched_references.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["reference_id", "reference_name"])
        writer.writeheader()
        writer.writerows({"reference_id": rid, "reference_name": name}
                         for rid, name in names.items() if rid not in matched_ids)
    # Separate route/OSM candidates independent of names, suitable for targeted API probes.
    candidates = []
    for route_id, entry in details.items():
        route = entry.get("getRouteById") or entry
        shape = []
        for loc in sorted(route.get("locations") or [], key=lambda x: x.get("sequence", 0)):
            try:
                shape.append((float(loc["latitude"]), float(loc["longitude"])))
            except (KeyError, ValueError, TypeError):
                pass
        if len(shape) < 2:
            continue
        for feat in features:
            if feat["category"] != "bus_stop":
                continue
            projected = project((feat["lat"], feat["lon"]), shape)
            if projected and projected[0] <= a.max_distance_m:
                candidates.append({"route_id": route_id, "osm_type": feat["type"],
                                   "osm_id": feat["id"], "osm_lat": feat["lat"],
                                   "osm_lon": feat["lon"], "distance_to_shape_m": round(projected[0], 1),
                                   "position_along_shape_m": round(projected[2], 1),
                                   "projected_lat": round(projected[1][0], 7),
                                   "projected_lon": round(projected[1][1], 7)})
    (a.output/"stop_shape_candidates.json").write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"osm_objects": len(features), "route_shapes": routes_processed,
               "named_reference_matches": len(rows), "unique_references_matched": len(matched_ids),
               "stop_shape_candidates": len(candidates),
               "unmatched_references": len(set(names)-matched_ids),
               "warning": "OSM stop coordinates are not confirmed Socobuses stops. Projection is analytical; no API verification performed."}
    (a.output/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
