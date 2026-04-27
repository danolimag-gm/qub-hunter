#!/usr/bin/env python3
"""
Convertit les shapefiles du cadastre rénové (EPSG:32198) en GeoJSON WGS84 simplifié.

Opérations :
  1. Reprojection EPSG:32198 → EPSG:4326
  2. Sélection des champs utiles (NO_LOT, NO_CADASTRE, SUPERFICIE)
  3. Suppression des géométries invalides
  4. Simplification légère (tolérance adaptée au zoom cible)
  5. Export GeoJSON par tuile de 0.5° (préparation Tippecanoe)

Usage:
    python process_cadastre.py --region mauricie
    python process_cadastre.py --region mauricie --simplify 5 --zoom-min 12
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import geopandas as gpd
    from shapely.validation import make_valid
    from tqdm import tqdm
except ImportError:
    print("Dépendances manquantes. Exécutez :\n  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

RAW_DIR     = Path(__file__).parent.parent / "data" / "raw"
PROC_DIR    = Path(__file__).parent.parent / "data" / "processed"

# Projection source du cadastre québécois
SRC_CRS  = "EPSG:32198"   # NAD83 / Québec Lambert
DEST_CRS = "EPSG:4326"

# Champs à conserver (les noms peuvent varier légèrement entre régions)
KEEP_FIELDS_CANDIDATES = [
    ["NO_LOT", "NO_CADASTRE", "SUPERFICIE"],
    ["NOLOT", "NOCADASTRE", "SUPERF"],
    ["no_lot", "no_cadastre", "superficie"],
]

# Simplification en mètres (dans la projection source avant reprojection)
DEFAULT_SIMPLIFY_M = 3.0


def find_shp(region: str) -> Path:
    shp_dir = RAW_DIR / region / "shp"
    shps = list(shp_dir.rglob("*.shp"))
    if not shps:
        print(f"✗ Aucun shapefile trouvé dans {shp_dir}", file=sys.stderr)
        print("  Exécutez d'abord : python download_cadastre.py --region " + region, file=sys.stderr)
        sys.exit(1)
    # Préférer le fichier le plus volumineux (polygones principaux)
    return max(shps, key=lambda p: p.stat().st_size)


def detect_fields(gdf):
    """Retourne les noms réels des champs NO_LOT, NO_CADASTRE, SUPERFICIE."""
    cols = set(gdf.columns)
    for candidate in KEEP_FIELDS_CANDIDATES:
        if all(c in cols for c in candidate):
            return candidate
    # Recherche partielle insensible à la casse
    result = []
    targets = ["no_lot", "no_cadastre", "superficie"]
    for t in targets:
        match = next((c for c in gdf.columns if c.lower().replace(" ", "_") == t), None)
        result.append(match)
    return result


def process_region(region: str, simplify_m: float, zoom_min: int):
    shp_path = find_shp(region)
    print(f"\n→ Lecture {shp_path.name} …")

    gdf = gpd.read_file(shp_path)
    print(f"  {len(gdf):,} lots, CRS = {gdf.crs}")

    # Reprojection si nécessaire
    if str(gdf.crs).upper() != DEST_CRS:
        print(f"  → reprojection {gdf.crs} → {DEST_CRS} …")
        gdf = gdf.to_crs(DEST_CRS)

    # Détection des champs
    fields = detect_fields(gdf)
    real_fields = [f for f in fields if f and f in gdf.columns]
    if real_fields:
        print(f"  Champs retenus : {real_fields}")
        gdf = gdf[real_fields + ["geometry"]]
    else:
        print("  ⚠ Champs NO_LOT/SUPERFICIE introuvables, tous les champs conservés")

    # Nettoyage des géométries invalides
    print("  → validation des géométries …")
    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        print(f"  ⚠ {invalid.sum():,} géométries invalides → réparation automatique")
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].apply(make_valid)

    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    print(f"  ✓ {len(gdf):,} géométries valides")

    # Simplification (en degrés, ~0.00003° ≈ 3m à cette latitude)
    tol_deg = simplify_m / 111_000
    print(f"  → simplification {simplify_m} m (tol={tol_deg:.6f}°) …")
    gdf["geometry"] = gdf.geometry.simplify(tol_deg, preserve_topology=True)

    # Export GeoJSON complet
    out_dir = PROC_DIR / region
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"cadastre_{region}.geojson"

    print(f"  → export GeoJSON → {out_path.relative_to(out_path.parent.parent.parent)} …")
    gdf.to_file(out_path, driver="GeoJSON")
    size_mb = out_path.stat().st_size / 1_048_576
    print(f"  ✓ {size_mb:.1f} Mo — {len(gdf):,} lots")

    # Export tuiles 0.5° × 0.5° pour Tippecanoe (optionnel, zoom ≥ zoom_min)
    if zoom_min >= 12:
        _export_tiles(gdf, out_dir, region)

    return out_path


def _export_tiles(gdf, out_dir: Path, region: str):
    """Découpe en tuiles de 0.5° pour accélérer Tippecanoe."""
    import math
    tiles_dir = out_dir / "tiles"
    tiles_dir.mkdir(exist_ok=True)

    bounds = gdf.total_bounds  # minx, miny, maxx, maxy
    step = 0.5
    xs = [bounds[0] + i * step for i in range(math.ceil((bounds[2] - bounds[0]) / step) + 1)]
    ys = [bounds[1] + i * step for i in range(math.ceil((bounds[3] - bounds[1]) / step) + 1)]

    count = 0
    print(f"  → découpage en tuiles 0.5° ({len(xs)*len(ys)} cellules max) …")
    for x0 in xs:
        for y0 in ys:
            x1, y1 = x0 + step, y0 + step
            tile = gdf.cx[x0:x1, y0:y1]
            if len(tile) == 0:
                continue
            name = f"tile_{x0:.1f}_{y0:.1f}.geojson".replace("-", "m")
            tile.to_file(tiles_dir / name, driver="GeoJSON")
            count += 1
    print(f"  ✓ {count} tuiles exportées dans {tiles_dir.relative_to(out_dir.parent.parent)}")


def main():
    parser = argparse.ArgumentParser(description="Prépare les shapefiles du cadastre pour Tippecanoe")
    parser.add_argument("--region", required=True, metavar="NOM",
                        help="Région à traiter (ex: mauricie)")
    parser.add_argument("--simplify", type=float, default=DEFAULT_SIMPLIFY_M, metavar="M",
                        help=f"Tolérance de simplification en mètres (défaut: {DEFAULT_SIMPLIFY_M})")
    parser.add_argument("--zoom-min", type=int, default=12, metavar="Z",
                        help="Zoom minimum visé (influence le découpage en tuiles, défaut: 12)")
    args = parser.parse_args()

    out = process_region(args.region, args.simplify, args.zoom_min)
    print(f"\n✓ Traitement terminé → {out}")
    print("  Prochaine étape : python generate_pmtiles.py --region " + args.region)


if __name__ == "__main__":
    main()
