#!/usr/bin/env python3
"""
Télécharge les 29 zones de chasse officielles du Québec depuis le serveur MRNF
et génère zones_chasse.geojson pour la PWA Qub Hunter.

La PWA charge ce fichier statiquement (pas de CORS, disponible hors ligne).

Usage :
    python3 download_zones.py

    # Géométries moins précises mais fichier plus léger (~400 Ko)
    python3 download_zones.py --simplify

Prérequis :
    pip3 install requests --break-system-packages
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Installez requests : pip3 install requests --break-system-packages", file=sys.stderr)
    sys.exit(1)

# ── Chemins ───────────────────────────────────────────────────────────────────
ROOT   = Path(__file__).parent.parent
OUTPUT = ROOT / "zones_chasse.geojson"

# ── Source MRNF (ArcGIS REST — accessible côté serveur, pas depuis le navigateur) ──
ZONES_URL = (
    "https://servicescarto.mern.gouv.qc.ca/pes/rest/services/Territoire/"
    "ZoneChasse/MapServer/0/query"
)

HEADERS = {
    "User-Agent": "QubHunter/1.0 (pipeline)",
    "Referer":    "https://mern.gouv.qc.ca/",
}


def download(simplify: bool) -> dict:
    offset_val = 0.01 if simplify else 0.003

    params = {
        "where":              "1=1",
        "outFields":          "*",
        "f":                  "geojson",
        "resultRecordCount":  100,           # Max par requête
        "maxAllowableOffset": offset_val,    # Simplification géométrique
        "returnGeometry":     "true",
    }

    print(f"→ Téléchargement depuis MRNF (offset={offset_val})…")
    print(f"  {ZONES_URL}\n")

    try:
        r = requests.get(ZONES_URL, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except requests.exceptions.Timeout:
        print("✗ Délai dépassé. Réessayez ou vérifiez votre connexion.", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"✗ Erreur HTTP {e.response.status_code}.", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"✗ Erreur réseau : {e}", file=sys.stderr)
        sys.exit(1)

    data = r.json()

    if "error" in data:
        print(f"✗ Erreur ArcGIS : {data['error']}", file=sys.stderr)
        sys.exit(1)

    features = data.get("features", [])
    if not features:
        print("✗ Aucune zone reçue. Vérifiez l'URL ou réessayez.", file=sys.stderr)
        sys.exit(1)

    # Ajouter le champ NOM si absent (certaines versions de l'API omettent NOM_ZON)
    for f in features:
        p = f.get("properties", {})
        zone_no = p.get("NO_ZONE") or p.get("ZONE_NO") or p.get("NOM_ZON") or ""
        if zone_no and not p.get("NOM"):
            p["NOM"] = f"Zone {int(zone_no)}"

    return data


def main():
    parser = argparse.ArgumentParser(
        description="Génère zones_chasse.geojson pour la PWA Qub Hunter"
    )
    parser.add_argument(
        "--simplify", action="store_true",
        help="Géométries allégées (fichier ~400 Ko plutôt que ~1.5 Mo)"
    )
    args = parser.parse_args()

    data = download(args.simplify)
    n = len(data["features"])

    print(f"  ✓ {n} zones reçues")
    print(f"\n→ Écriture de {OUTPUT.name}…")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = OUTPUT.stat().st_size // 1024
    print(f"  ✓ {size_kb} Ko → {OUTPUT}")
    print(
        f"\n  La PWA chargera automatiquement zones_chasse.geojson.\n"
        f"  Ouvrez qub-hunter-phase06.html — les {n} zones apparaîtront directement.\n"
    )


if __name__ == "__main__":
    main()
