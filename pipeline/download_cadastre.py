#!/usr/bin/env python3
"""
Télécharge le cadastre rénové du Québec (province entière) depuis Données Québec.

Usage:
    python download_cadastre.py
    python download_cadastre.py --force   # re-télécharge même si déjà présent
"""
import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

# Source unique : province entière (MERN / Données Québec)
PROVINCE_URL = (
    "https://diffusion.mern.gouv.qc.ca/Diffusion/RGQ/Vectoriel/Theme/Local/"
    "Cadastre_Renove/Shapefile/Q00/Province/S_MAJ_UNITE_EVAL_SHP.zip"
)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
PROVINCE_DIR = RAW_DIR / "province"
ZIP_PATH = PROVINCE_DIR / "cadastre_province.zip"
SHP_DIR = PROVINCE_DIR / "shp"


def download_file(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ✗ Erreur réseau : {e}", file=sys.stderr)
        return False

    total = int(resp.headers.get("content-length", 0))
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, "wb") as f, tqdm(
        desc="cadastre_province.zip",
        total=total,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in resp.iter_content(chunk_size=131_072):
            f.write(chunk)
            bar.update(len(chunk))
    return True


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(131_072), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(zip_path: Path, dest: Path):
    print(f"  → extraction dans {dest} …")
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    shps = list(dest.rglob("*.shp"))
    print(f"  ✓ {len(shps)} shapefile(s) extrait(s)")


def main():
    parser = argparse.ArgumentParser(description="Télécharge le cadastre province-entière")
    parser.add_argument("--force", action="store_true", help="Re-télécharge même si déjà présent")
    args = parser.parse_args()

    if SHP_DIR.exists() and list(SHP_DIR.rglob("*.shp")) and not args.force:
        print(f"✓ Shapefiles déjà présents dans {SHP_DIR}")
        print("  Utilisez --force pour re-télécharger.")
        return

    print("→ Téléchargement du cadastre rénové — province entière")
    print(f"  Source : {PROVINCE_URL}")
    print("  Taille estimée : ~1–3 Go — patience…\n")

    ok = download_file(PROVINCE_URL, ZIP_PATH)
    if not ok:
        print("\n✗ Téléchargement échoué.", file=sys.stderr)
        print("  Téléchargez manuellement depuis :")
        print("  https://www.donneesquebec.ca/recherche/dataset/cadastre-renove-du-quebec")
        print(f"  et placez le ZIP dans : {ZIP_PATH}")
        sys.exit(1)

    size_mb = ZIP_PATH.stat().st_size / 1_048_576
    print(f"\n  ✓ {size_mb:.0f} Mo téléchargés — MD5 : {md5(ZIP_PATH)}")

    extract(ZIP_PATH, SHP_DIR)

    print(f"\n✓ Prêt. Prochaine étape :")
    print("  python process_cadastre.py --region all")


if __name__ == "__main__":
    main()
