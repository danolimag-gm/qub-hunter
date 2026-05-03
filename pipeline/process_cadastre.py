#!/usr/bin/env python3
"""
Convertit le shapefile province-entière en 17 GeoJSON par région administrative.

Opérations :
  1. Lecture du shapefile (EPSG:32198)
  2. Reprojection → EPSG:4326
  3. Détection du champ de code municipal (CO_MUNI, MUN_CODE, etc.)
  4. Dérivation du code de région (2 premiers chiffres du code municipal)
  5. Nettoyage et simplification des géométries
  6. Export un GeoJSON par région : data/processed/cadastre_{id}.geojson

Usage:
    python process_cadastre.py --region all
    python process_cadastre.py --region 04
    python process_cadastre.py --list
"""
import argparse
import sys
from pathlib import Path

try:
    import geopandas as gpd
    from shapely.validation import make_valid
    from tqdm import tqdm
except ImportError:
    print("Dépendances manquantes. Exécutez :\n  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

RAW_DIR  = Path(__file__).parent.parent / "data" / "raw"
PROC_DIR = Path(__file__).parent.parent / "data" / "processed"
SHP_DIR  = RAW_DIR / "province" / "shp"

DEST_CRS = "EPSG:4326"
DEFAULT_SIMPLIFY_M = 3.0

# 17 régions administratives du Québec
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

# Noms de champs possibles pour le code municipal
MUNI_FIELD_CANDIDATES = ["CO_MUNI", "COMUN", "MUN_CODE", "CO_MUN", "MUNCODE", "CODMUNI"]
# Champs à conserver dans l'output
KEEP_CANDIDATES = [
    ["NO_LOT", "NO_CADASTRE", "SUPERFICIE"],
    ["NOLOT", "NOCADASTRE", "SUPERF"],
    ["no_lot", "no_cadastre", "superficie"],
]


def find_shp() -> Path:
    shps = list(SHP_DIR.rglob("*.shp"))
    if not shps:
        print(f"✗ Aucun shapefile trouvé dans {SHP_DIR}", file=sys.stderr)
        print("  Exécutez d'abord : python download_cadastre.py", file=sys.stderr)
        sys.exit(1)
    return max(shps, key=lambda p: p.stat().st_size)


def detect_muni_field(gdf) -> str:
    cols_upper = {c.upper(): c for c in gdf.columns}
    for candidate in MUNI_FIELD_CANDIDATES:
        if candidate.upper() in cols_upper:
            return cols_upper[candidate.upper()]
    print("✗ Champ de code municipal introuvable.", file=sys.stderr)
    print(f"  Champs disponibles : {list(gdf.columns)}", file=sys.stderr)
    sys.exit(1)


def detect_keep_fields(gdf) -> list:
    cols = set(gdf.columns)
    for candidates in KEEP_CANDIDATES:
        if all(c in cols for c in candidates):
            return candidates
    # Recherche partielle insensible à la casse
    targets = {"no_lot": None, "no_cadastre": None, "superficie": None}
    for col in gdf.columns:
        key = col.lower().replace(" ", "_")
        if key in targets:
            targets[key] = col
    return [v for v in targets.values() if v]


def load_province(shp_path: Path):
    size_mb = shp_path.stat().st_size / 1_048_576
    print(f"→ Lecture {shp_path.name} ({size_mb:.0f} Mo) …")
    gdf = gpd.read_file(shp_path)
    print(f"  {len(gdf):,} lots, CRS = {gdf.crs}")

    if str(gdf.crs) != DEST_CRS:
        print(f"  → reprojection → {DEST_CRS} …")
        gdf = gdf.to_crs(DEST_CRS)

    muni_field = detect_muni_field(gdf)
    print(f"  Champ municipal détecté : {muni_field}")

    # Code région = 2 premiers chiffres du code municipal
    gdf["_region_code"] = gdf[muni_field].astype(str).str[:2].str.zfill(2)

    keep = detect_keep_fields(gdf)
    if keep:
        print(f"  Champs conservés : {keep}")
        gdf = gdf[keep + ["_region_code", "geometry"]]
    else:
        print("  ⚠ Champs NO_LOT/SUPERFICIE introuvables, tous les champs conservés")

    return gdf


def process_region(gdf, region_code: str, simplify_m: float) -> Path:
    nom = REGIONS.get(region_code, f"Region-{region_code}")
    subset = gdf[gdf["_region_code"] == region_code].copy()

    if len(subset) == 0:
        print(f"  ⚠ Aucun lot pour la région {region_code} ({nom}), ignorée.")
        return None

    print(f"\n→ Région {region_code} — {nom} : {len(subset):,} lots")

    # Réparation des géométries invalides
    invalid = ~subset.geometry.is_valid
    if invalid.any():
        print(f"  ⚠ {invalid.sum():,} géométries invalides → réparation …")
        subset.loc[invalid, "geometry"] = subset.loc[invalid, "geometry"].apply(make_valid)

    subset = subset[~subset.geometry.is_empty & subset.geometry.notna()]

    # Simplification
    tol_deg = simplify_m / 111_000
    subset["geometry"] = subset.geometry.simplify(tol_deg, preserve_topology=True)

    # Supprimer la colonne temporaire
    subset = subset.drop(columns=["_region_code"])

    out_dir = PROC_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"cadastre_{region_code}.geojson"

    subset.to_file(out_path, driver="GeoJSON")
    size_mb = out_path.stat().st_size / 1_048_576
    print(f"  ✓ cadastre_{region_code}.geojson — {size_mb:.1f} Mo")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Prépare les GeoJSON du cadastre par région")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--region", metavar="CODE_OU_ALL",
                       help="Code région (ex: 04) ou 'all' pour les 17 régions")
    group.add_argument("--list", action="store_true", help="Liste les 17 régions")
    parser.add_argument("--simplify", type=float, default=DEFAULT_SIMPLIFY_M, metavar="M",
                        help=f"Tolérance simplification en mètres (défaut: {DEFAULT_SIMPLIFY_M})")
    args = parser.parse_args()

    if args.list:
        print("\nRégions administratives du Québec :\n")
        for code, nom in REGIONS.items():
            out = PROC_DIR / f"cadastre_{code}.geojson"
            status = "✓" if out.exists() else " "
            print(f"  [{status}] {code}  {nom}")
        print()
        return

    shp = find_shp()
    gdf = load_province(shp)

    targets = list(REGIONS.keys()) if args.region == "all" else [args.region.zfill(2)]

    for code in tqdm(targets, desc="Régions", unit="région"):
        process_region(gdf, code, args.simplify)

    print(f"\n✓ Terminé. GeoJSON dans : {PROC_DIR}")
    print("  Prochaine étape : python generate_pmtiles.py --region all")


if __name__ == "__main__":
    main()
