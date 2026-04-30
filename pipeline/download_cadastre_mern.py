#!/usr/bin/env python3
"""
Télécharge le cadastre rénové du Québec depuis le service MRNF GeoEnvironnement
et génère un fichier GeoJSON pour la PWA Qub Hunter.

Source : https://geo.environnement.gouv.qc.ca/donnees/rest/services/Reference/Cadastre_allege/MapServer/0

Usage :
    python3 download_cadastre_mern.py
    
    # Avec limitation de régions (pour test)
    python3 download_cadastre_mern.py --limit 1000

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
OUTPUT = ROOT / "data" / "processed" / "cadastre_mern.geojson"

# ── Source MRNF GeoEnvironnement ───────────────────────────────────────────────
CADASTRA_URL = (
    "https://geo.environnement.gouv.qc.ca/donnees/rest/services/Reference/"
    "Cadastre_allege/MapServer/0/query"
)

HEADERS = {
    "User-Agent": "QubHunter/1.0 (pipeline)",
    "Referer": "https://gouv.qc.ca/",
}

# ── BBox du Québec (en EPSG:4326) ─────────────────────────────────────────────
QC_BBOX = {
    "geometry": "-79.8,44.9,-57.1,62.6",
    "geometryType": "esriGeometryEnvelope",
    "inSR": "4326",
    "spatialRel": "esriSpatialRelIntersects",
}


def download(limit: int = None) -> dict:
    """Télécharge les lots du cadastre depuis le service MRNF."""
    
    all_features = []
    offset = 0
    batch_size = 2000  # Max autorisé par le service
    
    print(f"→ Téléchargement depuis MRNF GeoEnvironnement…")
    print(f"  URL: {CADASTRA_URL}")
    print(f"  Limite: {limit or 'illimité'} lots\n")
    
    while True:
        params = {
            "where": "1=1",
            "outFields": "NO_LOT,OBJECTID",
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": min(batch_size, limit - offset) if limit else batch_size,
            "maxAllowableOffset": 0.001,  # Simplification légère
            "returnGeometry": "true",
            **QC_BBOX,
        }
        
        try:
            r = requests.get(CADASTRA_URL, params=params, headers=HEADERS, timeout=60)
            r.raise_for_status()
        except requests.exceptions.Timeout:
            print(f"✗ Délai dépassé à l'offset {offset}", file=sys.stderr)
            break
        except requests.exceptions.RequestException as e:
            print(f"✗ Erreur réseau: {e}", file=sys.stderr)
            break
        
        data = r.json()
        
        if "error" in data:
            print(f"✗ Erreur ArcGIS: {data['error']}", file=sys.stderr)
            break
        
        features = data.get("features", [])
        if not features:
            break
        
        all_features.extend(features)
        print(f"  ✓ Offset {offset}: +{len(features)} lots (total: {len(all_features)})")
        
        offset += len(features)
        
        # Arrêter si on a atteint la limite demandée
        if limit and len(all_features) >= limit:
            all_features = all_features[:limit]
            break
        
        # Arrêter si on a moins de batch_size résultats (fin des données)
        if len(features) < batch_size:
            break
    
    if not all_features:
        print("✗ Aucun lot reçu", file=sys.stderr)
        sys.exit(1)
    
    return {
        "type": "FeatureCollection",
        "name": "cadastre_mern",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": all_features,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Génère cadastre_mern.geojson pour la PWA Qub Hunter"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limiter le nombre de lots (défaut: illimité)"
    )
    args = parser.parse_args()
    
    # Créer le dossier de sortie si nécessaire
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    
    data = download(args.limit)
    n = len(data["features"])
    
    print(f"\n→ Écriture de {OUTPUT.name}…")
    
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    
    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"  ✓ {n} lots → {size_mb:.1f} Mo")
    print(f"  → {OUTPUT}")
    
    # Afficher quelques exemples
    print(f"\n  Exemples de lots:")
    for f in data["features"][:5]:
        lot = f.get("properties", {}).get("NO_LOT", "N/A")
        print(f"    - {lot}")
    if n > 5:
        print(f"    ... et {n - 5} autres")


if __name__ == "__main__":
    main()
