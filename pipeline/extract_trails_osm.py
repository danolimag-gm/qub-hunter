#!/usr/bin/env python3
"""
Extract trail data from OpenStreetMap for Quebec hunting regions.

Coverage: 14 active hunting administrative regions (excludes Montréal,
Laval, Montérégie metro). Tiles are chunked at ~2°×1.5° to avoid
Overpass timeouts.

Trail types: pedestrian (path/footway/hiking), snowmobile, ATV/quad.

Usage: python3 pipeline/extract_trails_osm.py
Output: data/trails_quebec.geojson
"""
import json
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "data" / "trails_quebec.geojson"

# 2°×1.5° tiles covering active hunting regions (excludes Montréal/Laval/Montérégie metro).
# Tile = (west, south, east, north).
TILES = [
    # Outaouais / Laurentides / Lanaudière (south-west / south-central)
    (-78.0, 45.5, -76.0, 47.0),
    (-76.0, 45.5, -74.0, 47.0),
    (-78.0, 47.0, -76.0, 48.5),
    (-76.0, 47.0, -74.0, 48.5),
    # Mauricie / Capitale-Nationale / Chaudière-Appalaches
    (-74.0, 45.5, -72.0, 47.0),
    (-72.0, 45.5, -70.0, 47.0),
    (-74.0, 47.0, -72.0, 48.5),
    (-72.0, 47.0, -70.0, 48.5),
    # Bas-Saint-Laurent / Estrie / Centre-du-Québec
    (-70.0, 45.5, -68.0, 47.0),
    (-68.0, 47.0, -66.0, 48.5),
    (-70.0, 47.0, -68.0, 48.5),
    # Saguenay-Lac-Saint-Jean
    (-72.5, 48.5, -70.5, 50.0),
    (-70.5, 48.5, -68.5, 50.0),
    # Abitibi-Témiscamingue
    (-80.0, 46.5, -78.0, 48.0),
    (-80.0, 48.0, -78.0, 49.5),
    (-78.0, 48.0, -76.0, 49.5),
    # Gaspésie / Côte-Nord (south part — most accessible hunting)
    (-66.0, 47.5, -64.0, 49.0),
    (-68.0, 48.5, -66.0, 50.0),
    (-66.0, 49.0, -64.0, 50.5),
]

# All trail types in one union query per tile.
QUERY_TEMPLATE = """
[out:json][timeout:180];
(
  way["highway"="path"]({s},{w},{n},{e});
  way["highway"="footway"]({s},{w},{n},{e});
  way["route"="hiking"]({s},{w},{n},{e});
  way["route"="snowmobile"]({s},{w},{n},{e});
  way["snowmobile"="yes"]({s},{w},{n},{e});
  way["atv"="yes"]({s},{w},{n},{e});
  way["highway"="track"]["motor_vehicle"="yes"]({s},{w},{n},{e});
);
out body;
>;
out skel qt;
""".strip()

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
]


def classify(tags):
    h = tags.get("highway", "")
    r = tags.get("route", "")
    if r == "snowmobile" or tags.get("snowmobile") == "yes":
        return "snowmobile"
    if tags.get("atv") == "yes":
        return "atv"
    if h == "track" and tags.get("motor_vehicle") == "yes":
        return "atv"
    if h in ("path", "footway") or r == "hiking":
        return "pedestrian"
    return "other"


def fetch_tile(bbox, attempt=1):
    w, s, e, n = bbox
    query = QUERY_TEMPLATE.format(s=s, w=w, n=n, e=e)
    last_err = None
    for url in ENDPOINTS:
        try:
            r = requests.get(url, params={"data": query}, timeout=240,
                             headers={"User-Agent": "qub-hunter/0.1"})
            if r.status_code == 200:
                return r.json()
            last_err = f"HTTP {r.status_code} ({r.text[:200]})"
        except Exception as ex:
            last_err = str(ex)
        time.sleep(2)
    if attempt < 3:
        print(f"  retry {attempt+1}/3 after error: {last_err}")
        time.sleep(15)
        return fetch_tile(bbox, attempt + 1)
    raise RuntimeError(f"All endpoints failed: {last_err}")


def to_features(data, seen_ids):
    features = []
    nodes = {n["id"]: (n["lon"], n["lat"]) for n in data["elements"] if n["type"] == "node"}
    for el in data["elements"]:
        if el["type"] != "way":
            continue
        if el["id"] in seen_ids:
            continue
        seen_ids.add(el["id"])
        coords = [nodes[nid] for nid in el.get("nodes", []) if nid in nodes]
        if len(coords) < 2:
            continue
        tags = el.get("tags", {})
        ttype = classify(tags)
        if ttype == "other":
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [list(c) for c in coords]},
            "properties": {
                "type": ttype,
                "name": tags.get("name", ""),
                "osm_id": el["id"],
            },
        })
    return features


def main():
    all_features = []
    seen = set()
    for i, bbox in enumerate(TILES, 1):
        print(f"[{i}/{len(TILES)}] tile {bbox}")
        t0 = time.time()
        data = fetch_tile(bbox)
        feats = to_features(data, seen)
        all_features.extend(feats)
        print(f"  +{len(feats)} ways  ({len(data['elements'])} OSM elements, {time.time()-t0:.1f}s)")
        time.sleep(1)  # be nice to Overpass

    fc = {"type": "FeatureCollection", "features": all_features}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(fc))
    size_mb = OUTPUT.stat().st_size / 1_048_576
    print(f"\nWrote {OUTPUT.name}  ({len(all_features):,} features, {size_mb:.1f} MB)")

    # breakdown
    by_type = {}
    for f in all_features:
        t = f["properties"]["type"]
        by_type[t] = by_type.get(t, 0) + 1
    for t, c in sorted(by_type.items()):
        print(f"  {t}: {c:,}")


if __name__ == "__main__":
    main()
