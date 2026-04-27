#!/usr/bin/env python3
"""
Génère les fichiers PMTiles à partir des GeoJSON traités.

Prérequis : Tippecanoe installé
  macOS  : brew install tippecanoe
  Linux  : https://github.com/felt/tippecanoe#installation

Usage:
    python generate_pmtiles.py --region mauricie
    python generate_pmtiles.py --region mauricie --min-zoom 10 --max-zoom 16
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROC_DIR   = Path(__file__).parent.parent / "data" / "processed"
TILES_DIR  = Path(__file__).parent.parent / "data" / "pmtiles"

# Paramètres Tippecanoe par défaut pour le cadastre
# z10-16 : raisonnable pour les lots (~3.5M parcelles à z16 = ~800 Mo)
DEFAULT_MIN_ZOOM = 10
DEFAULT_MAX_ZOOM = 16


def check_tippecanoe():
    path = shutil.which("tippecanoe")
    if path is None:
        print("✗ Tippecanoe introuvable.", file=sys.stderr)
        print("  Installation :")
        print("    macOS  : brew install tippecanoe")
        print("    Ubuntu : sudo apt-get install tippecanoe")
        print("    Manuel : https://github.com/felt/tippecanoe#installation")
        sys.exit(1)
    return path


def find_geojson(region: str) -> Path:
    path = PROC_DIR / region / f"cadastre_{region}.geojson"
    if not path.exists():
        print(f"✗ GeoJSON introuvable : {path}", file=sys.stderr)
        print(f"  Exécutez d'abord : python process_cadastre.py --region {region}", file=sys.stderr)
        sys.exit(1)
    return path


def run_tippecanoe(geojson: Path, output: Path, min_zoom: int, max_zoom: int, layer_name: str):
    cmd = [
        "tippecanoe",
        "--output", str(output),
        "--layer", layer_name,
        "--minimum-zoom", str(min_zoom),
        "--maximum-zoom", str(max_zoom),
        # Simplification automatique selon le zoom
        "--simplification", "4",
        # Garder tous les features même à bas zoom
        "--no-feature-limit",
        "--no-tile-size-limit",
        # Attributs à conserver
        "--include", "NO_LOT",
        "--include", "NO_CADASTRE",
        "--include", "SUPERFICIE",
        # Forcer PMTiles v3
        "--output-to-directory" if output.suffix != ".pmtiles" else "--output",
        str(output),
        str(geojson),
    ]

    # Reconstruire la commande proprement
    cmd = [
        "tippecanoe",
        f"--output={output}",
        f"--layer={layer_name}",
        f"--minimum-zoom={min_zoom}",
        f"--maximum-zoom={max_zoom}",
        "--simplification=4",
        "--no-feature-limit",
        "--no-tile-size-limit",
        "--include=NO_LOT",
        "--include=NO_CADASTRE",
        "--include=SUPERFICIE",
        "--force",
        str(geojson),
    ]

    print(f"\n→ Tippecanoe : {' '.join(cmd[:3])} … (peut prendre plusieurs minutes)")
    print(f"  Zoom {min_zoom}–{max_zoom} | couche : {layer_name}")

    result = subprocess.run(cmd, capture_output=False, text=True)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Génère les PMTiles du cadastre")
    parser.add_argument("--region", required=True, metavar="NOM",
                        help="Région à traiter (ex: mauricie)")
    parser.add_argument("--min-zoom", type=int, default=DEFAULT_MIN_ZOOM,
                        help=f"Zoom minimum (défaut: {DEFAULT_MIN_ZOOM})")
    parser.add_argument("--max-zoom", type=int, default=DEFAULT_MAX_ZOOM,
                        help=f"Zoom maximum (défaut: {DEFAULT_MAX_ZOOM})")
    parser.add_argument("--layer", default="cadastre",
                        help="Nom de la couche dans le PMTiles (défaut: cadastre)")
    args = parser.parse_args()

    tippecanoe = check_tippecanoe()
    print(f"✓ Tippecanoe : {tippecanoe}")

    geojson = find_geojson(args.region)
    size_mb = geojson.stat().st_size / 1_048_576
    print(f"✓ GeoJSON source : {size_mb:.1f} Mo")

    TILES_DIR.mkdir(parents=True, exist_ok=True)
    output = TILES_DIR / f"cadastre_{args.region}.pmtiles"

    success = run_tippecanoe(geojson, output, args.min_zoom, args.max_zoom, args.layer)

    if not success:
        print("\n✗ Tippecanoe a échoué.", file=sys.stderr)
        sys.exit(1)

    out_mb = output.stat().st_size / 1_048_576 if output.exists() else 0
    print(f"\n✓ PMTiles généré : {output.name} ({out_mb:.1f} Mo)")
    print(f"  Chemin complet : {output}")
    print()
    print("Prochaines étapes :")
    print("  1. Déployer sur Cloudflare R2 ou GitHub Pages :")
    print(f"     cp {output} ../web/pmtiles/")
    print("  2. Dans qub-hunter-phase02.html, définir :")
    print(f"     var CADASTRE_PMTILES = './pmtiles/cadastre_{args.region}.pmtiles';")
    print("  3. Activer la couche cadastre dans la carte.")


if __name__ == "__main__":
    main()
