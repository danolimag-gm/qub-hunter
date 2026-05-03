#!/usr/bin/env python3
"""
Traite les fichiers GPKG de la Carte écoforestière mise à jour (MRNF)
et génère un fichier PMTiles pour l'affichage dans Qub Hunter.

Usage:
    python process_ecoforestier.py
    python process_ecoforestier.py --gpkg ~/Downloads/CARTE_ECO_MAJ_31H.gpkg ~/Downloads/CARTE_ECO_MAJ_31I.gpkg
    python process_ecoforestier.py --skip-geojson   # si GeoJSON déjà générés
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
from tqdm import tqdm

REPO_ROOT  = Path(__file__).parent.parent
DATA_DIR   = REPO_ROOT / "data"
PROC_DIR   = DATA_DIR / "processed"
PMTILE_DIR = DATA_DIR / "pmtiles"

DEFAULT_GPKG = [
    Path.home() / "Downloads" / "CARTE_ECO_MAJ_31H.gpkg",
    Path.home() / "Downloads" / "CARTE_ECO_MAJ_31I.gpkg",
    Path.home() / "Downloads" / "CARTE_ECO_MAJ_31J.gpkg",
]

KEEP_COLS = ["type_couv", "gr_ess", "type_eco", "cl_age", "cl_haut", "origine"]

OUTPUT_PMTILES = PMTILE_DIR / "types_forestiers.pmtiles"
OUTPUT_GEOJSON = PROC_DIR / "types_forestiers_merged.geojson"


def process_gpkg(path: Path) -> gpd.GeoDataFrame:
    sheet = path.stem.split("_")[-1].upper()
    print(f"\n→ {path.name}  ({path.stat().st_size / 1_048_576:.0f} Mo)")

    layer = f"pee_maj_{sheet.lower()}"
    print(f"  Lecture couche '{layer}'...")
    gdf = gpd.read_file(path, layer=layer)
    print(f"  {len(gdf):,} polygones lus — CRS : {gdf.crs}")

    print("  Reprojection → WGS84...")
    gdf = gdf.to_crs("EPSG:4326")

    # Garder seulement les colonnes utiles + géométrie
    cols = [c for c in KEEP_COLS if c in gdf.columns] + ["geometry"]
    gdf = gdf[cols]

    # Supprimer polygones sans géométrie
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

    print(f"  {len(gdf):,} polygones valides")
    return gdf


def build_geojson(gdfs: list[gpd.GeoDataFrame]) -> None:
    print(f"\n→ Fusion de {len(gdfs)} feuillet(s) et écriture GeoJSON...")
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    merged = gpd.GeoDataFrame(
        gpd.pd.concat(gdfs, ignore_index=True),
        crs="EPSG:4326"
    )
    print(f"  Total : {len(merged):,} polygones")

    merged.to_file(OUTPUT_GEOJSON, driver="GeoJSON")
    size_mb = OUTPUT_GEOJSON.stat().st_size / 1_048_576
    print(f"  ✓ {OUTPUT_GEOJSON.name}  ({size_mb:.0f} Mo)")


def build_pmtiles() -> None:
    print("\n→ Génération PMTiles avec Tippecanoe...")
    PMTILE_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "tippecanoe",
        "-o", str(OUTPUT_PMTILES),
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
        str(OUTPUT_GEOJSON),
    ]

    print("  " + " ".join(cmd[:6]) + " ...")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("✗ Tippecanoe a échoué", file=sys.stderr)
        sys.exit(1)

    size_mb = OUTPUT_PMTILES.stat().st_size / 1_048_576
    print(f"  ✓ {OUTPUT_PMTILES.name}  ({size_mb:.0f} Mo)")
    print(f"\n  Uploader vers R2 : python upload_r2.py --prefix types/")


def main():
    parser = argparse.ArgumentParser(description="Traite la carte écoforestière → PMTiles")
    parser.add_argument("--gpkg", nargs="+", type=Path,
                        default=DEFAULT_GPKG,
                        help="Chemins vers les fichiers GPKG (défaut: ~/Downloads/CARTE_ECO_MAJ_31*.gpkg)")
    parser.add_argument("--skip-geojson", action="store_true",
                        help="Sauter la conversion GeoJSON (utiliser fichier existant)")
    args = parser.parse_args()

    if not args.skip_geojson:
        gdfs = []
        for path in args.gpkg:
            if not path.exists():
                print(f"✗ Fichier introuvable : {path}", file=sys.stderr)
                sys.exit(1)
            gdfs.append(process_gpkg(path))
        build_geojson(gdfs)
    else:
        if not OUTPUT_GEOJSON.exists():
            print(f"✗ GeoJSON introuvable : {OUTPUT_GEOJSON}", file=sys.stderr)
            sys.exit(1)
        print(f"→ GeoJSON existant : {OUTPUT_GEOJSON}")

    build_pmtiles()
    print("\n✓ Terminé.")


if __name__ == "__main__":
    main()
