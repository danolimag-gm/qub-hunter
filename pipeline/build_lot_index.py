#!/usr/bin/env python3
"""
Génère lot_index.json : NO_LOT → [lat, lng] pour lookup instantané dans la PWA.

Le fichier est placé dans le dossier qub_hunter/ (servi comme asset statique).
La PWA le charge une seule fois et fait la localisation cadastrale hors ligne.

Usage :
    # Traiter tous les shapefiles déjà téléchargés
    python build_lot_index.py

    # Télécharger le cadastre provincial complet puis indexer (long ~500 MB)
    python build_lot_index.py --download

    # Afficher les colonnes du shapefile sans générer l'index
    python build_lot_index.py --inspect

Prérequis :
    pip install geopandas shapely tqdm requests pyogrio
    (ou : pip install -r requirements.txt)
"""

import argparse
import json
import sys
import unicodedata
from pathlib import Path

try:
    import geopandas as gpd
    from tqdm import tqdm
    import requests
except ImportError:
    print(
        "Dépendances manquantes. Exécutez :\n"
        "  pip install -r requirements.txt\n"
        "ou : pip install geopandas shapely tqdm requests pyogrio",
        file=sys.stderr,
    )
    sys.exit(1)

# ── Chemins ──────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent.parent
RAW_DIR  = ROOT / "data" / "raw"
OUTPUT   = ROOT / "lot_index.json"

# Cadastre provincial complet — MERN / Géobase du cadastre rénové
PROVINCE_URL = (
    "https://diffusion.mern.gouv.qc.ca/Diffusion/RGQ/Vectoriel/Theme/Local/"
    "Cadastre_Renove/Shapefile/Q00/Province/S_MAJ_UNITE_EVAL_SHP.zip"
)
PROVINCE_ZIP = RAW_DIR / "province" / "cadastre_province.zip"
PROVINCE_SHP = RAW_DIR / "province" / "shp"

# CRS source du cadastre québécois
SRC_CRS  = "EPSG:32198"   # NAD83 / Québec Lambert
DEST_CRS = "EPSG:4326"

# ── MRCs de chasse — noms normalisés (sans accents, minuscules) ───────────────
HUNTING_MRCS = {
    "maskinonge",
    "matawinie",
    "les laurentides",
    "antoine-labelle",
    "papineau",
    "argenteuil",
    "deux-montagnes",
    "the high laurentians",
    "pontiac",
    "la vallee-de-la-gatineau", "vallee-de-la-gatineau",
    "portneuf",
    "mekinac",
    "lac-saint-jean-est",
    "le domaine-du-roy", "domaine-du-roy",
    "maria-chapdelaine",
    # Villes avec territoire de chasse important
    "shawinigan",
    "saguenay",
}


def normalize(s: str) -> str:
    """Minuscules, sans accents."""
    return (
        unicodedata.normalize("NFD", str(s or "").lower())
        .encode("ascii", "ignore")
        .decode()
        .strip()
    )


# ── Téléchargement ───────────────────────────────────────────────────────────

def download_province():
    if PROVINCE_SHP.exists() and any(PROVINCE_SHP.glob("*.shp")):
        print(f"✓ Shapefile provincial déjà présent dans {PROVINCE_SHP}")
        return

    PROVINCE_ZIP.parent.mkdir(parents=True, exist_ok=True)

    if not PROVINCE_ZIP.exists():
        print(f"→ Téléchargement du cadastre provincial (~500 MB)…")
        print(f"  {PROVINCE_URL}\n")
        resp = requests.get(PROVINCE_URL, stream=True, timeout=60)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        with open(PROVINCE_ZIP, "wb") as f, tqdm(
            desc="cadastre_province.zip", total=total, unit="B", unit_scale=True
        ) as bar:
            for chunk in resp.iter_content(65536):
                f.write(chunk)
                bar.update(len(chunk))
        print(f"  ✓ Téléchargé : {PROVINCE_ZIP}")
    else:
        print(f"✓ Archive déjà présente : {PROVINCE_ZIP}")

    print(f"  → Extraction…")
    import zipfile
    PROVINCE_SHP.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(PROVINCE_ZIP) as z:
        z.extractall(PROVINCE_SHP)
    print(f"  ✓ {len(list(PROVINCE_SHP.rglob('*')))} fichiers extraits")


# ── Détection des shapefiles disponibles ─────────────────────────────────────

def find_shapefiles() -> list[Path]:
    """Retourne tous les .shp trouvés sous data/raw/."""
    shps = sorted(RAW_DIR.rglob("*.shp"), key=lambda p: p.stat().st_size, reverse=True)
    return shps


# ── Traitement d'un shapefile ────────────────────────────────────────────────

def process_shp(shp_path: Path, filter_mrcs: bool) -> dict:
    """Lit un shapefile et retourne un dict NO_LOT → [lat, lng]."""
    print(f"\n→ Lecture : {shp_path.name}")
    try:
        gdf = gpd.read_file(shp_path, engine="pyogrio")
    except Exception:
        gdf = gpd.read_file(shp_path)

    print(f"  {len(gdf):,} lots  |  CRS : {gdf.crs}")
    print(f"  Colonnes : {list(gdf.columns)}")

    # ── Reprojection ──
    if gdf.crs is None:
        print(f"  ⚠ CRS non défini, on suppose {SRC_CRS}")
        gdf = gdf.set_crs(SRC_CRS)
    if str(gdf.crs).upper() != DEST_CRS and gdf.crs.to_epsg() != 4326:
        print(f"  → Reprojection {gdf.crs.to_epsg()} → 4326…")
        gdf = gdf.to_crs(DEST_CRS)

    # ── Détecter colonne NO_LOT ──
    lot_col = next(
        (c for c in gdf.columns if c.upper() in ("NO_LOT", "NOLOT")), None
    )
    if not lot_col:
        print(f"  ✗ Colonne NO_LOT introuvable — shapefile ignoré.")
        return {}
    print(f"  Colonne lot : {lot_col}")

    # ── Détecter colonne MRC (optionnelle) ──
    mrc_col = next(
        (c for c in gdf.columns
         if any(k in c.upper() for k in ("MRC", "NOM_MRC", "MRC_S"))),
        None,
    )

    # ── Filtrer par MRC ──
    if filter_mrcs and mrc_col:
        before = len(gdf)
        mask = gdf[mrc_col].apply(lambda v: normalize(v) in HUNTING_MRCS)
        gdf = gdf[mask].copy()
        print(f"  Filtre MRCs chasse : {before:,} → {len(gdf):,} lots  (col: {mrc_col})")
    elif filter_mrcs and not mrc_col:
        print(f"  ⚠ Colonne MRC introuvable — tous les lots inclus (pas de filtre)")

    # ── Supprimer géométries vides ──
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

    # ── Calculer centroïdes ──
    print(f"  Calcul des centroïdes…")
    centroids = gdf.geometry.centroid

    # ── Construire l'index ──
    index = {}
    skipped = 0
    for lot_no, centroid in zip(gdf[lot_col], centroids):
        lot_str = str(lot_no).strip()
        if not lot_str or lot_str in ("nan", "None", ""):
            skipped += 1
            continue
        if centroid.is_empty or centroid.x == 0.0:
            skipped += 1
            continue
        # [lat, lng] arrondi à 5 décimales ≈ 1 m de précision
        index[lot_str] = [round(centroid.y, 5), round(centroid.x, 5)]

    print(f"  ✓ {len(index):,} lots indexés  ({skipped} ignorés)")
    return index


# ── Point d'entrée ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Génère lot_index.json pour la PWA Qub Hunter"
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Télécharger le shapefile provincial complet avant de traiter (~500 MB)"
    )
    parser.add_argument(
        "--all-mrcs", action="store_true",
        help="Inclure toutes les MRCs (fichier plus grand, non recommandé pour PWA)"
    )
    parser.add_argument(
        "--inspect", action="store_true",
        help="Afficher les colonnes disponibles sans générer l'index"
    )
    args = parser.parse_args()

    if args.download:
        download_province()

    shps = find_shapefiles()
    if not shps:
        print(
            "\n✗ Aucun shapefile trouvé sous data/raw/\n\n"
            "Options :\n"
            "  1. Téléchargement automatique (recommandé) :\n"
            "       python build_lot_index.py --download\n\n"
            "  2. Téléchargement manuel par région :\n"
            "       python download_cadastre.py --region mauricie\n"
            "     puis relancez build_lot_index.py",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"\nShapefiles trouvés : {len(shps)}")
    for p in shps:
        size_mb = p.stat().st_size / 1_048_576
        print(f"  {p.relative_to(ROOT)}  ({size_mb:.0f} MB)")

    if args.inspect:
        for shp in shps:
            gdf = gpd.read_file(shp, rows=1)
            print(f"\n{shp.name} — colonnes :")
            for c in gdf.columns:
                print(f"  {c}")
        return

    # ── Traitement ──
    filter_mrcs = not args.all_mrcs
    combined = {}
    for shp in shps:
        partial = process_shp(shp, filter_mrcs)
        combined.update(partial)   # dernière valeur gagne en cas de doublon

    if not combined:
        print("\n✗ Aucun lot extrait. Vérifiez les colonnes avec --inspect.", file=sys.stderr)
        sys.exit(1)

    # ── Export ──
    print(f"\n→ Écriture de {OUTPUT.name}…")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(combined, f, separators=(",", ":"), ensure_ascii=False)

    size_kb = OUTPUT.stat().st_size // 1024
    size_mb = size_kb / 1024
    print(f"  ✓ {len(combined):,} lots  |  {size_mb:.1f} MB  →  {OUTPUT}")
    print(
        f"\n  Le fichier lot_index.json est prêt.\n"
        f"  La PWA le chargera automatiquement à la première recherche cadastrale.\n"
    )


if __name__ == "__main__":
    main()
