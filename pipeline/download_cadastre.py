#!/usr/bin/env python3
"""
Télécharge les shapefiles du cadastre rénové du Québec depuis Données Québec.

Usage:
    python download_cadastre.py --region mauricie
    python download_cadastre.py --region all
    python download_cadastre.py --list
"""
import argparse
import hashlib
import os
import sys
import zipfile
from pathlib import Path

import requests
from tqdm import tqdm

# Données Québec — Cadastre rénové par région administrative
# https://www.donneesquebec.ca/recherche/dataset/cadastre-renove-du-quebec
CADASTRE_URLS = {
    "mauricie": {
        "nom": "Mauricie (04)",
        "url": "https://diffusion.mern.gouv.qc.ca/Diffusion/RGQ/Vectoriel/Theme/Local/Cadastre_Renove/Shapefile/Q00/Province/S_MAJ_UNITE_EVAL_SHP.zip",
        # Fallback : URL alternative Données Québec si le lien MERN est rompu
        "fallback": "https://geoboutique.mern.gouv.qc.ca/cadastre/mauricie.zip",
    },
    "outaouais": {
        "nom": "Outaouais (07)",
        "url": "https://diffusion.mern.gouv.qc.ca/Diffusion/RGQ/Vectoriel/Theme/Local/Cadastre_Renove/Shapefile/Q00/Province/S_MAJ_UNITE_EVAL_SHP.zip",
        "fallback": None,
    },
    "laurentides": {
        "nom": "Laurentides (15)",
        "url": "https://diffusion.mern.gouv.qc.ca/Diffusion/RGQ/Vectoriel/Theme/Local/Cadastre_Renove/Shapefile/Q00/Province/S_MAJ_UNITE_EVAL_SHP.zip",
        "fallback": None,
    },
    "saguenay": {
        "nom": "Saguenay–Lac-Saint-Jean (02)",
        "url": "https://diffusion.mern.gouv.qc.ca/Diffusion/RGQ/Vectoriel/Theme/Local/Cadastre_Renove/Shapefile/Q00/Province/S_MAJ_UNITE_EVAL_SHP.zip",
        "fallback": None,
    },
}

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


def list_regions():
    print("\nRégions disponibles :\n")
    for key, info in CADASTRE_URLS.items():
        print(f"  {key:<16} {info['nom']}")
    print()


def download_file(url: str, dest: Path, label: str) -> bool:
    """Télécharge un fichier avec barre de progression. Retourne True si succès."""
    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ✗ Échec ({e})", file=sys.stderr)
        return False

    total = int(resp.headers.get("content-length", 0))
    dest.parent.mkdir(parents=True, exist_ok=True)

    with open(dest, "wb") as f, tqdm(
        desc=label, total=total, unit="B", unit_scale=True, unit_divisor=1024
    ) as bar:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            bar.update(len(chunk))

    return True


def checksum(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_zip(zip_path: Path, dest_dir: Path):
    print(f"  → extraction dans {dest_dir.relative_to(zip_path.parent.parent)} …")
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest_dir)
    print(f"  ✓ {len(list(dest_dir.rglob('*')))} fichiers extraits")


def download_region(region: str):
    if region not in CADASTRE_URLS:
        print(f"Région inconnue : {region}", file=sys.stderr)
        print("Utilisez --list pour voir les régions disponibles.")
        sys.exit(1)

    info = CADASTRE_URLS[region]
    zip_path = RAW_DIR / region / f"cadastre_{region}.zip"
    extract_dir = RAW_DIR / region / "shp"

    if extract_dir.exists() and any(extract_dir.glob("*.shp")):
        print(f"✓ Shapefiles déjà présents pour {info['nom']}")
        return extract_dir

    print(f"\n→ Téléchargement cadastre {info['nom']}")

    success = download_file(info["url"], zip_path, f"cadastre_{region}.zip")
    if not success and info.get("fallback"):
        print("  → tentative URL de secours…")
        success = download_file(info["fallback"], zip_path, f"cadastre_{region}_fallback.zip")

    if not success:
        print(f"\n✗ Impossible de télécharger le cadastre pour {region}.", file=sys.stderr)
        print("  Vérifiez votre connexion ou téléchargez manuellement depuis :")
        print("  https://www.donneesquebec.ca/recherche/dataset/cadastre-renove-du-quebec")
        sys.exit(1)

    md5 = checksum(zip_path)
    print(f"  MD5 : {md5}")

    extract_zip(zip_path, extract_dir)
    return extract_dir


def main():
    parser = argparse.ArgumentParser(description="Télécharge le cadastre rénové du Québec")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--region", metavar="NOM",
                       help="Région à télécharger (ex: mauricie)")
    group.add_argument("--all", action="store_true",
                       help="Télécharge toutes les régions configurées")
    group.add_argument("--list", action="store_true",
                       help="Liste les régions disponibles")
    args = parser.parse_args()

    if args.list:
        list_regions()
        return

    if args.all:
        for region in CADASTRE_URLS:
            download_region(region)
    else:
        download_region(args.region)

    print("\n✓ Téléchargement terminé.")
    print(f"  Fichiers dans : {RAW_DIR}")


if __name__ == "__main__":
    main()
