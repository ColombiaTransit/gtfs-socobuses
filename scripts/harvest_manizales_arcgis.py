#!/usr/bin/env python3
"""Archive publicly readable Manizales ArcGIS layers without changing GTFS."""
import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import requests

SOURCES = {
    "manizales_mobility": "https://sig.manizales.gov.co/wadmzl/rest/services/MOVILIDAD/appTuristica/MapServer",
}
ITEM_ID = "54eeb145d33a4033995bc61a0c35c436"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ColombiaTransit-Socobuses-Research/1.0"})
ALLOWED = ("www.arcgis.com", "sig.manizales.gov.co", "services.arcgis.com", "services1.arcgis.com",
           "services2.arcgis.com", "services3.arcgis.com", "services4.arcgis.com",
           "services5.arcgis.com", "services6.arcgis.com", "services7.arcgis.com",
           "services8.arcgis.com", "services9.arcgis.com", "services-eu1.arcgis.com")


def request(url, params=None):
    host = urlparse(url).hostname or ""
    if host not in ALLOWED:
        raise ValueError("Unapproved ArcGIS host: " + host)
    for attempt in range(4):
        try:
            response = SESSION.get(url, params=params, timeout=45)
            response.raise_for_status()
            obj = response.json()
            if "error" in obj:
                raise RuntimeError(str(obj["error"]))
            return obj
        except (requests.RequestException, ValueError, RuntimeError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def safe(value):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value)).strip("_")[:65]


def source_list():
    sources = dict(SOURCES)
    try:
        item = request("https://www.arcgis.com/sharing/rest/content/items/" + ITEM_ID, {"f": "json"})
        url = item.get("url", "")
        if url and urlparse(url).hostname in ALLOWED:
            sources["manizales_public_routes"] = url.rstrip("/")
    except Exception as exc:
        print("ArcGIS item resolution failed:", exc)
    return sources


def export_layer(base, layer, destination, max_features):
    lid = layer["id"]
    name = layer.get("name", str(lid))
    url = base + "/" + str(lid)
    info = request(url, {"f": "json"})
    if info.get("type") not in ("Feature Layer", "Table"):
        return {"layer": lid, "name": name, "status": "skipped_non_feature"}
    meta = {"layer_id": lid, "name": name, "url": url, "metadata": info,
            "downloaded_at": datetime.now(timezone.utc).isoformat()}
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    oid = info.get("objectIdField") or info.get("objectIdFieldName")
    if not oid:
        raise ValueError("Layer lacks object ID field")
    ids = request(url + "/query", {"f": "json", "where": "1=1", "returnIdsOnly": "true"}).get("objectIds") or []
    ids = sorted(ids)
    if len(ids) > max_features:
        raise ValueError(f"Layer has {len(ids)} features, above safety limit {max_features}; refusing partial export")
    features = []
    for i in range(0, len(ids), 100):
        batch = request(url + "/query", {"f": "geojson", "objectIds": ",".join(map(str, ids[i:i+100])),
                    "outFields": "*", "returnGeometry": "true", "outSR": "4326"})
        if batch.get("type") != "FeatureCollection":
            raise ValueError("Expected GeoJSON FeatureCollection")
        features.extend(batch.get("features", []))
    if len(features) != len(ids):
        raise ValueError(f"Incomplete layer: expected {len(ids)}, got {len(features)}")
    collection = {"type": "FeatureCollection", "features": features}
    (destination / "features.geojson").write_text(json.dumps(collection, ensure_ascii=False))
    return {"layer": lid, "name": name, "status": "complete", "count": len(features),
            "geometry_type": info.get("geometryType"), "url": url,
            "path": str(destination / "features.geojson")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("output/arcgis"))
    parser.add_argument("--max-features-per-layer", type=int, default=150000)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(),
                "item_id": ITEM_ID, "sources": {}, "errors": [],
                "note": "Source archive only; no stop or shape is automatically GTFS-approved."}
    for name, base in source_list().items():
        record = {"url": base, "layers": []}
        manifest["sources"][name] = record
        try:
            service = request(base, {"f": "json"})
            (output / name).mkdir(exist_ok=True)
            (output / name / "service.json").write_text(json.dumps(service, ensure_ascii=False, indent=2))
            for layer in (service.get("layers") or []) + (service.get("tables") or []):
                try:
                    result = export_layer(base, layer, output / name / (str(layer["id"]) + "_" + safe(layer.get("name", ""))), args.max_features_per_layer)
                    record["layers"].append(result)
                    print(name, result["layer"], result["name"], result["status"], result.get("count", ""))
                except Exception as exc:
                    error = {"source": name, "layer": layer.get("id"), "error": str(exc)}
                    manifest["errors"].append(error)
                    print("ERROR:", error)
        except Exception as exc:
            manifest["errors"].append({"source": name, "error": str(exc)})
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    completed = [layer for s in manifest["sources"].values() for layer in s["layers"] if layer["status"] == "complete"]
    print("Complete layers:", len(completed), "Errors:", len(manifest["errors"]))
    if not completed or manifest["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
