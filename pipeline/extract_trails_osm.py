#!/usr/bin/env python3
"""
Extract trail data from OpenStreetMap for Quebec using Overpass API.
Extracts various trail types: hiking, snowmobile, atv, bicycle, footpaths.
"""

import requests
import json
import time

# Mauricie region bounding box (smaller test area around Shawinigan)
BBOX = "-73.0,46.5,-72.5,47.0"  # west, south, east, north (small test area)

# Overpass API query for trails (very simple)
OVERPASS_QUERY = f"""
[out:json][timeout:60];
(
  way["highway"="path"]({BBOX});
);
out body;
>;
out skel qt;
"""

def overpass_to_geojson(data):
    """Convert Overpass JSON output to GeoJSON."""
    features = []
    
    for element in data['elements']:
        if element['type'] == 'way':
            if 'nodes' not in element or len(element['nodes']) < 2:
                continue
            
            # Get coordinates for each node
            coords = []
            for node_id in element['nodes']:
                # Find node in elements
                node = next((n for n in data['elements'] if n['type'] == 'node' and n['id'] == node_id), None)
                if node:
                    coords.append([node['lon'], node['lat']])
            
            if len(coords) < 2:
                continue
            
            # Determine trail type from tags
            tags = element.get('tags', {})
            highway = tags.get('highway', '')
            route = tags.get('route', '')
            
            # Classify trail type
            trail_type = 'other'
            if highway in ['footway', 'path', 'track', 'trail'] or route == 'hiking':
                trail_type = 'hiking'
            elif highway == 'snowmobile' or route == 'snowmobile':
                trail_type = 'snowmobile'
            elif highway in ['atv', 'off_road']:
                trail_type = 'atv'
            elif highway == 'cycleway' or route == 'bicycle':
                trail_type = 'bicycle'
            elif highway == 'bridleway':
                trail_type = 'horse'
            elif highway == 'ski':
                trail_type = 'ski'
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords
                },
                "properties": {
                    "type": trail_type,
                    "highway": highway,
                    "route": route,
                    "name": tags.get('name', ''),
                    "osm_id": element['id']
                }
            }
            features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features
    }

def main():
    print("Fetching trail data from OpenStreetMap...")
    print(f"Bounding box: {BBOX}")
    
    # Try different Overpass API endpoints
    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter"
    ]
    
    for url in endpoints:
        print(f"Trying endpoint: {url}")
        params = {'data': OVERPASS_QUERY}
        try:
            response = requests.get(url, params=params, timeout=120)
            if response.status_code == 200:
                print(f"Success with endpoint: {url}")
                break
            else:
                print(f"  Status: {response.status_code}")
        except Exception as e:
            print(f"  Error: {e}")
    
    if response.status_code != 200:
        print(f"Error: All endpoints failed. Last status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return
    
    data = response.json()
    print(f"Retrieved {len(data['elements'])} elements from OSM")
    
    # Convert to GeoJSON
    geojson = overpass_to_geojson(data)
    print(f"Converted to {len(geojson['features'])} trail features")
    
    # Save to file
    output_file = 'data/trails_quebec.geojson'
    with open(output_file, 'w') as f:
        json.dump(geojson, f)
    
    print(f"Saved to {output_file}")
    
    # Print statistics
    trail_types = {}
    for feature in geojson['features']:
        t = feature['properties']['type']
        trail_types[t] = trail_types.get(t, 0) + 1
    
    print("\nTrail type breakdown:")
    for t, count in sorted(trail_types.items()):
        print(f"  {t}: {count}")

if __name__ == '__main__':
    main()
