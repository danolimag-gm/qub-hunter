#!/usr/bin/env python3
"""
Split types_forestiers GeoJSONL by Quebec administrative region using bounding boxes,
then generate one PMTiles per region with Tippecanoe.

Usage:
    python split_forest_by_region.py
    python split_forest_by_region.py --regions 04 11   # only specific regions
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
PROC_DIR = DATA_DIR / "processed"
PMTILE_DIR = DATA_DIR / "pmtiles" / "types"
INPUT = PROC_DIR / "types_forestiers_clean.geojsonl"

# Approximate bounding boxes [west, south, east, north] for each QC admin region
# Based on MRNF administrative boundaries
REGIONS = {
    "01": {"name": "Bas-Saint-Laurent",              "bbox": [-69.5, 47.3, -66.5, 49.0]},
    "02": {"name": "Saguenay-Lac-Saint-Jean",        "bbox": [-74.0, 47.3, -69.5, 52.0]},
    "03": {"name": "Capitale-Nationale",             "bbox": [-72.0, 46.6, -69.5, 47.8]},
    "04": {"name": "Mauricie",                       "bbox": [-74.0, 46.2, -72.0, 47.7]},
    "05": {"name": "Estrie",                         "bbox": [-72.5, 45.0, -71.0, 45.7]},
    "06": {"name": "Montreal",                       "bbox": [-74.0, 45.4, -73.4, 45.7]},
    "07": {"name": "Outaouais",                      "bbox": [-78.5, 45.5, -74.5, 48.0]},
    "08": {"name": "Abitibi-Temiscamingue",          "bbox": [-80.0, 46.8, -76.5, 49.5]},
    "09": {"name": "Cote-Nord",                      "bbox": [-69.5, 48.5, -58.0, 52.5]},
    "10": {"name": "Nord-du-Quebec",                 "bbox": [-80.0, 49.0, -63.0, 55.5]},
    "11": {"name": "Gaspesie-Iles-de-la-Madeleine",  "bbox": [-67.5, 47.8, -61.0, 49.3]},
    "12": {"name": "Chaudiere-Appalaches",           "bbox": [-72.0, 45.8, -69.5, 47.0]},
    "14": {"name": "Lanaudiere",                     "bbox": [-74.2, 45.8, -73.2, 47.0]},
    "15": {"name": "Laurentides",                    "bbox": [-75.5, 45.5, -73.5, 47.5]},
    "16": {"name": "Monteregie",                     "bbox": [-74.5, 45.0, -72.5, 45.7]},
    "17": {"name": "Centre-du-Quebec",               "bbox": [-72.8, 45.7, -71.5, 46.5]},
}


def point_in_bbox(lon: float, lat: float, bbox: list) -> bool:
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def get_centroid(geojson_line: str) -> tuple:
    """Fast centroid extraction from first coordinate of geometry."""
    # Find first coordinate pair quickly
    idx = geojson_line.index('"coordinates"')
    # Walk past nested brackets to first number
    i = idx + 13
    depth = 0
    while i < len(geojson_line):
        c = geojson_line[i]
        if c == '[':
            depth += 1
        elif c == ']':
            break
        elif c == '-' or c.isdigit():
            # Found start of number
            end = i + 1
            while end < len(geojson_line) and geojson_line[end] not in ',]':
                end += 1
            lon = float(geojson_line[i:end])
            # Skip comma, get lat
            start2 = end + 1
            end2 = start2
            while end2 < len(geojson_line) and geojson_line[end2] not in ',]':
                end2 += 1
            lat = float(geojson_line[start2:end2])
            return lon, lat
        i += 1
    return None, None


def split_geojsonl(regions_to_process: list):
    """Split the big GeoJSONL into per-region files."""
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    # Open output files
    handles = {}
    counts = {}
    for code in regions_to_process:
        path = PROC_DIR / f"types_forestiers_{code}.geojsonl"
        handles[code] = open(path, 'w')
        counts[code] = 0

    skipped = 0
    total = 0

    print(f"Reading {INPUT}...")
    with open(INPUT, 'r') as f:
        for line in f:
            total += 1
            if total % 500_000 == 0:
                print(f"  {total:,} lines processed...", flush=True)

            lon, lat = get_centroid(line)
            if lon is None:
                skipped += 1
                continue

            # Assign to matching region(s)
            matched = False
            for code in regions_to_process:
                bbox = REGIONS[code]["bbox"]
                if point_in_bbox(lon, lat, bbox):
                    handles[code].write(line)
                    counts[code] += 1
                    matched = True
                    # Don't break — a polygon near border may match multiple regions

            if not matched:
                skipped += 1

    for h in handles.values():
        h.close()

    print(f"\nSplit complete: {total:,} lines, {skipped:,} unmatched")
    for code in regions_to_process:
        print(f"  Region {code} ({REGIONS[code]['name']}): {counts[code]:,} polygons")

    return counts


def build_pmtiles(regions_to_process: list, counts: dict):
    """Generate PMTiles per region using Tippecanoe."""
    PMTILE_DIR.mkdir(parents=True, exist_ok=True)

    for code in regions_to_process:
        if counts.get(code, 0) == 0:
            print(f"\n⚠ Region {code}: no polygons, skipping")
            continue

        input_file = PROC_DIR / f"types_forestiers_{code}.geojsonl"
        output_file = PMTILE_DIR / f"types_forestiers_{code}.pmtiles"

        print(f"\n→ Region {code} ({REGIONS[code]['name']}): {counts[code]:,} polygons")
        cmd = [
            "tippecanoe",
            "-o", str(output_file),
            "--force",
            "--layer", "types_forestiers",
            "--minimum-zoom", "8",
            "--maximum-zoom", "15",
            "--simplification", "4",
            "--drop-densest-as-needed",
            "--extend-zooms-if-still-dropping",
            "-T", "type_couv:string",
            "-T", "gr_ess:string",
            "-T", "type_eco:string",
            "-T", "cl_age:string",
            "-T", "cl_haut:string",
            "-T", "origine:string",
            str(input_file),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ✗ Tippecanoe failed: {result.stderr[:200]}")
            continue

        size_mb = output_file.stat().st_size / 1_048_576
        print(f"  ✓ {output_file.name} ({size_mb:.0f} Mo)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--regions", nargs="+", default=list(REGIONS.keys()))
    parser.add_argument("--skip-split", action="store_true")
    args = parser.parse_args()

    if not INPUT.exists():
        print(f"✗ Input not found: {INPUT}", file=sys.stderr)
        sys.exit(1)

    regions = [r for r in args.regions if r in REGIONS]
    print(f"Processing {len(regions)} regions: {', '.join(regions)}")

    if not args.skip_split:
        counts = split_geojsonl(regions)
    else:
        counts = {}
        for code in regions:
            p = PROC_DIR / f"types_forestiers_{code}.geojsonl"
            if p.exists():
                counts[code] = sum(1 for _ in open(p))

    build_pmtiles(regions, counts)
    print("\n✓ Done. Upload with: python upload_r2.py --prefix types/")


if __name__ == "__main__":
    main()
