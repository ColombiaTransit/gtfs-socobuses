#!/usr/bin/env python3
"""Inspect publicly served Socobuses route-page JS for map markers and API calls."""
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://socobuses.co/routes"
OUT = Path("output/map-research")
OUT.mkdir(parents=True, exist_ok=True)
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; Socobuses-GTFS-Research/1.0)"})
page = session.get(BASE, timeout=30)
page.raise_for_status()
soup = BeautifulSoup(page.text, "html.parser")
assets = []
for script in soup.select("script[src]"):
    url = urljoin(BASE, script["src"])
    if urlparse(url).netloc != urlparse(BASE).netloc:
        continue
    if url not in assets:
        assets.append(url)
patterns = [
    r"google\.maps\.[A-Za-z]+", r"new\s+(?:google\.maps\.)?Marker",
    r"referencePointId", r"getPointsReference\w*", r"getRouteById",
    r"latitude", r"longitude", r"latLng", r"markers?",
    r"/site/routes/[A-Za-z0-9_/]+", r"Ver Puntos cercanos",
]
report = {"page": BASE, "assets": [], "observations": [],
          "warning": "JS string matches are not proof of true stop coordinates"}
for url, body in [(BASE, page.text)] + [
    (url, None) for url in assets
]:
    try:
        if body is None:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            if len(response.content) > 5_000_000:
                report["assets"].append({"url": url, "skipped": "larger than 5 MB"})
                continue
            body = response.text
        matches = []
        for pattern in patterns:
            for match in list(re.finditer(pattern, body, re.I))[:20]:
                matches.append({"pattern": pattern, "excerpt": body[max(0, match.start()-150):match.end()+180]})
        report["assets"].append({"url": url, "bytes": len(body.encode()), "matches": len(matches)})
        if matches:
            report["observations"].append({"url": url, "matches": matches})
    except requests.RequestException as exc:
        report["assets"].append({"url": url, "error": str(exc)})
(OUT / "map-javascript-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps({"scripts": len(assets), "files_with_matches": len(report["observations"])}, indent=2))
