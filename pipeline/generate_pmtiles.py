#!/usr/bin/env python3
"""
Génère les PMTiles du cadastre par région à partir des GeoJSON traités.

Prérequis : tippecanoe installé (brew install tippecanoe)

Usage:
    python generate_pmtiles.py --region all
    python generate_pmtiles.py --region 04
    python generate_pmtiles.py --list
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from tqdm import tqdm

PROC_DIR  = Path(__file__).parent.parent / "data" / "processed"
TILES_DIR = Path(__file__).parent.parent / "data" / "pmtiles"

DEFAULT_MIN_ZOOM = 10
DEFAULT_MAX_ZOOM = 16

REGIONS = {
    "01": "Bas-Saint-Laurent",
    "02": "Saguenay-Lac-Saint-Jean",
    "03": "Capitale-Nationale",
    "04": "Mauricie",
    "05": "Estrie",
    "06": "Montreal",
    "07": "Outaouais",
    "08": "Abitibi-Temiscamingue",
    "09": "Cote-Nord",
    "10": "Nord-du-Quebec",
    "11": "Gaspesie-Iles-de-la-Madeleine",
    "12": "Chaudiere-Appalaches",
    "13": "Laval",
    "14": "Lanaudiere",
    "15": "Laurentides",
    "16": "Monteregie",
    "17": "Centre-du-Quebec",
}


def check_tippecanoe() -> str:
    path = shutil.which("tippecanoe")
    if not path:
        print("✗ Tippecanoe introuvable.", file=sys.stderr)
        print("  macOS  : brew install tippecanoe")
        print("  Linux  : https://github.com/felt/tippecanoe#installation")
        sys.exit(1)
    result = subprocess.run([path, "--version"], capture_output=True, text=True)
    version = result.stderr.strip() or result.stdout.strip()
    print(f"✓ {version}")
    return path


def find_geojson(region_code: str) -> Path | None:
    path = PROC_DIR / f"cadastre_{region_code}.geojson"
    if not path.exists():
        return None
    return path


def run_tippecanoe(geojson: Path, output: Path, min_zoom: int, max_zoom: int) -> bool:
    cmd = [
        "tippecanoe",
        f"--output={output}",
        "--layer=cadastre",
        f"--minimum-zoom={min_zoom}",
        f"--maximum-zoom={max_zoom}",
        "--simplification=4",
        "--drop-densest-as-needed",
        "--include=NO_LOT",
        "--include=NO_CADASTRE",
        "--include=SUPERFICIE",
        "--force",
        "--quiet",
        str(geojson),
    ]
    result = subprocess.run(cmd)
    return result.returncode == 0


def process_region(region_code: str, min_zoom: int, max_zoom: int) -> bool:
    nom = REGIONS.get(region_code, f"Region-{region_code}")
    geojson = find_geojson(region_code)

    if not geojson:
        print(f"  ⚠ GeoJSON introuvable pour {region_code} ({nom}) — ignoré.")
        print(f"    Exécutez : python process_cadastre.py --region {region_code}")
        return False

    size_mb = geojson.stat().st_size / 1_048_576
    output = TILES_DIR / f"cadastre_{region_code}.pmtiles"

    if output.exists():
        print(f"  → {region_code} ({nom}) — {size_mb:.1f} Mo GeoJSON …")
    else:
        print(f"  → {region_code} ({nom}) — {size_mb:.1f} Mo GeoJSON …")

    TILES_DIR.mkdir(parents=True, exist_ok=True)
    ok = run_tippecanoe(geojson, output, min_zoom, max_zoom)

    if ok and output.exists():
        out_mb = output.stat().st_size / 1_048_576
        print(f"  ✓ cadastre_{region_code}.pmtiles — {out_mb:.1f} Mo")
        return True
    else:
        print(f"  ✗ Tippecanoe a échoué pour {region_code}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Génère les PMTiles du cadastre par région")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--region", metavar="CODE_OU_ALL",
                       help="Code région (ex: 04) ou 'all' pour les 17 régions")
    group.add_argument("--list", action="store_true", help="Liste les régions et leur statut")
    parser.add_argument("--min-zoom", type=int, default=DEFAULT_MIN_ZOOM)
    parser.add_argument("--max-zoom", type=int, default=DEFAULT_MAX_ZOOM)
    args = parser.parse_args()

    if args.list:
        print("\nStatut PMTiles :\n")
        for code, nom in REGIONS.items():
            geojson = find_geojson(code)
            pmtiles = TILES_DIR / f"cadastre_{code}.pmtiles"
            g = "✓ GeoJSON" if geojson else "  -      "
            p = "✓ PMTiles" if pmtiles.exists() else "  -      "
            print(f"  {code}  {g}  {p}  {nom}")
        print()
        return

    check_tippecanoe()

    targets = list(REGIONS.keys()) if args.region == "all" else [args.region.zfill(2)]
    success, failed = [], []

    print(f"\n→ Génération PMTiles (zoom {args.min_zoom}–{args.max_zoom})\n")
    for code in targets:
        ok = process_region(code, args.min_zoom, args.max_zoom)
        (success if ok else failed).append(code)

    print(f"\n✓ {len(success)}/{len(targets)} régions générées")
    if failed:
        print(f"  ✗ Échecs : {', '.join(failed)}")

    print(f"\n  Fichiers dans : {TILES_DIR}")
    print("  Prochaine étape : python upload_r2.py")


if __name__ == "__main__":
    main()
