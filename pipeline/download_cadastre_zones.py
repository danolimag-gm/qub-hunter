#!/usr/bin/env python3
"""
Télécharge le cadastre des zones de chasse 02-29 uniquement.
Génère cadastre_zones.geojson pour la PWA Qub Hunter.

Usage :
    python3 download_cadastre_zones.py

Prérequis :
    pip3 install requests --break-system-packages
"""

import json
import sys
from pathlib import Path
from urllib.parse import quote

try:
    import requests
except ImportError:
    print("Installez requests : pip3 install requests --break-system-packages", file=sys.stderr)
    sys.exit(1)

# ── Chemins ───────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent
ZONES_FILE  = ROOT / "zones_chasse.geojson"
OUTPUT      = ROOT / "data" / "processed" / "cadastre_zones.geojson"

# ── Source MRNF GeoEnvironnement ───────────────────────────────────────────────
CADASTRA_URL = (
    "https://geo.environnement.gouv.qc.ca/donnees/rest/services/Reference/"
    "Cadastre_allege/MapServer/0/query"
)

HEADERS = {
    "User-Agent": "QubHunter/1.0 (pipeline)",
    "Referer": "https://gouv.qc.ca/",
}


def get_zone_bbox(zone_geojson):
    """Calcule la bbox d'une zone de chasse."""
    coords = []
    
    def extract_coords(geom):
        if geom["type"] == "Polygon":
            return geom["coordinates"][0]
        elif geom["type"] == "MultiPolygon":
            return [c for poly in geom["coordinates"] for c in poly[0]]
        return []
    
    for f in zone_geojson.get("features", []):
        coords.extend(extract_coords(f["geometry"]))
    
    if not coords:
        return None
    
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return [min(lons), min(lats), max(lons), max(lats)]


def download_cadastre_for_bbox(bbox, zone_name):
    """Télécharge le cadastre pour une bbox donnée."""
    params = {
        "where": "1=1",
        "outFields": "NO_LOT",
        "f": "geojson",
        "resultRecordCount": 2000,
        "geometry": quote(f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"),
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "maxAllowableOffset": 0.0005,
        "returnGeometry": "true",
    }
    
    try:
        r = requests.get(CADASTRA_URL, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        if "error" in data:
            print(f"    ⚠ Erreur ArcGIS pour {zone_name}: {data['error']}", file=sys.stderr)
            return []
        
        return data.get("features", [])
    except Exception as e:
        print(f"    ⚠ Erreur pour {zone_name}: {e}", file=sys.stderr)
        return []


def main():
    print("→ Chargement des zones de chasse…")
    
    if not ZONES_FILE.exists():
        print(f"✗ Fichier non trouvé: {ZONES_FILE}", file=sys.stderr)
        print("  Exécutez d'abord: python3 download_zones.py", file=sys.stderr)
        sys.exit(1)
    
    with open(ZONES_FILE, "r", encoding="utf-8") as f:
        zones_data = json.load(f)
    
    print(f"  ✓ {len(zones_data['features'])} polygones de zones chargés\n")
    
    # Grouper les features par zone
    zones = {}
    for f in zones_data["features"]:
        zone_no = f["properties"].get("NO_ZONE", "inconnu")
        if zone_no not in zones:
            zones[zone_no] = {"type": "FeatureCollection", "features": []}
        zones[zone_no]["features"].append(f)
    
    print(f"→ Téléchargement du cadastre pour {len(zones)} zones…\n")
    
    all_lots = []
    total_lots = 0
    
    for zone_no in sorted(zones.keys(), key=lambda x: int(x)):
        zone_data = zones[zone_no]
        zone_name = f"Zone {zone_no}"
        
        bbox = get_zone_bbox(zone_data)
        if not bbox:
            print(f"  ⚠ Pas de géométrie pour {zone_name}")
            continue
        
        print(f"  → {zone_name}… ", end="", flush=True)
        
        lots = download_cadastre_for_bbox(bbox, zone_name)
        
        # Ajouter l'info de zone à chaque lot
        for lot in lots:
            lot["properties"]["ZONE_CHASSE"] = zone_no
            all_lots.append(lot)
        
        total_lots += len(lots)
        print(f"+{len(lots)} lots (total: {total_lots})")
    
    if not all_lots:
        print("\n✗ Aucun lot téléchargé", file=sys.stderr)
        sys.exit(1)
    
    # Créer le GeoJSON final
    output_data = {
        "type": "FeatureCollection",
        "name": "cadastre_zones",
        "description": f"Cadastre des zones de chasse 02-29 ({len(all_lots)} lots)",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": all_lots,
    }
    
    # Sauvegarder
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"\n→ Écriture de {OUTPUT.name}…")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, separators=(",", ":"))
    
    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    
    print(f"  ✓ {len(all_lots)} lots")
    print(f"  ✓ {size_mb:.1f} Mo")
    print(f"  → {OUTPUT}")
    
    # Afficher quelques exemples
    print(f"\n  Exemples de lots:")
    for lot in all_lots[:5]:
        no_lot = lot["properties"].get("NO_LOT", "N/A")
        zone = lot["properties"].get("ZONE_CHASSE", "N/A")
        print(f"    - Lot {no_lot} (Zone {zone})")
    
    print(f"\n  💡 Pour l'utiliser dans la PWA:")
    print(f"     cp {OUTPUT} {ROOT / 'cadastre_zones.geojson'}")


if __name__ == "__main__":
    main()
