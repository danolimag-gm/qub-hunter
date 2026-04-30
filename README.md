# Qub Hunter

**Application web progressive (PWA) pour la chasse au Québec**

Qub Hunter affiche les lots du cadastre rénové, zones de chasse, ZECs, pourvoiries et réserves fauniques du Québec sur une carte interactive. Mobile-first, optimisé pour une utilisation hors-ligne sur le terrain.

**Lien du projet :** [https://[VOTRE_NOM_UTILISATEUR].github.io/qub_hunter/](https://[VOTRE_NOM_UTILISATEUR].github.io/qub_hunter/)  
**Dépôt GitHub :** [https://github.com/[VOTRE_NOM_UTILISATEUR]/qub_hunter](https://github.com/[VOTRE_NOM_UTILISATEUR]/qub_hunter)

---

## 🎯 Objectifs du projet

- **Carte cadastrale interactive** : tous les lots du Québec avec numéros d'inscription
- **Territoires fauniques officiels** : ZECs, pourvoiries à droits exclusifs, réserves fauniques, parcs
- **Zones de chasse** : frontières administratives des zones 1-29
- **Recherche rapide** : par numéro de lot, nom de territoire, coordonnées
- **Hors-ligne** : téléchargement par région pour usage terrain sans réseau
- **Open source** : données publiques, code libre

---

## 📦 Statut actuel : Phase 02 (Données officielles)

### ✅ Phase 01 — Prototype
- Carte MapLibre GL avec fond de carte OSM/CARTO/Stadia
- Interface mobile-first avec drawer panel
- Géolocalisation GPS
- Affichage de coordonnées en temps réel (lat/lon/zoom)
- Polygones de démonstration (19 territoires synthétiques)

### ✅ Phase 02 — Données officielles (`qub-hunter-phase02.html`)
- **Données MRNF réelles** via ArcGIS REST (`servicescarto.mern.gouv.qc.ca`)
  - ZEC (layer 16), Pourvoiries DE (layer 8), Réserves fauniques (layer 11), Parcs nationaux (layer 5)
  - Fallback automatique vers données démo si l'API est inaccessible
- **Zones de chasse 1-29** — service `ZoneChasse` MRNF (+ fallback démo)
- **Recherche** par numéro de lot, territoire ou coordonnées (API iCherche)
  - Fallback vers recherche locale dans les couches chargées
- **Support PMTiles** — couche cadastre prête (nécessite `data/pmtiles/cadastre_mauricie.pmtiles`)
- **Pipeline Python** dans `pipeline/` :
  - `download_cadastre.py` — téléchargement shapefiles par région
  - `process_cadastre.py` — reprojection + simplification → GeoJSON
  - `generate_pmtiles.py` — conversion Tippecanoe → PMTiles

### 🚧 En développement (Phase 03)
- Service Worker pour cache intelligent
- Téléchargement par région
- IndexedDB pour stockage PMTiles

---

## 🛠️ Stack technique

### Frontend
- **MapLibre GL JS 4.7.1** : rendu cartographique WebGL
- **Vanilla JavaScript (ES5/ES6)** : aucune dépendance framework
- **CSS3** avec variables personnalisées
- **Service Worker** (Phase 03) pour mode hors-ligne

### Backend / Pipeline
- **Python 3.9+** pour traitement des données géospatiales
- **GDAL/OGR** : manipulation de Shapefiles
- **Tippecanoe** (Mapbox) : génération de tuiles vectorielles PMTiles
- **Requests** : téléchargement des données publiques

### Sources de données
- **MRNF (Ministère des Ressources naturelles et des Forêts)**
  - Service ArcGIS REST : `https://servicescarto.mern.gouv.qc.ca/pes/rest/services/Territoire/TRQ_WMS/MapServer`
  - 17 layers disponibles (ZECs, pourvoiries, réserves, parcs, etc.)
- **Données Québec** : cadastre rénové par région (Shapefiles)
- **API iCherche** (gouvernement du Québec) : géocodage par numéro de lot

### Hébergement (prévu)
- **Frontend** : [GitHub Pages](https://[VOTRE_NOM_UTILISATEUR].github.io/qub_hunter/)
- **PMTiles** : Cloudflare R2 (10 Go gratuits)

---

## 📁 Structure du projet

```
qub-hunter/
├── web/                      # Application frontend
│   ├── index.html            # App principale
│   ├── assets/
│   │   ├── css/
│   │   └── js/
│   └── pmtiles/              # Tuiles vectorielles (générées)
│
├── pipeline/                 # Scripts de traitement de données
│   ├── download_cadastre.py  # Téléchargement des SHP par région
│   ├── process_cadastre.py   # Reprojection + simplification
│   ├── generate_pmtiles.py   # Conversion en PMTiles
│   └── requirements.txt      # Dépendances Python
│
├── data/                     # Données brutes (git-ignorées)
│   ├── raw/                  # Shapefiles téléchargés
│   ├── processed/            # GeoJSON nettoyés
│   └── pmtiles/              # PMTiles finales
│
├── docs/                     # Documentation
│   ├── PHASE_01.md           # Détails Phase 01
│   ├── PHASE_02.md           # Plan Phase 02
│   └── DATA_SOURCES.md       # Références des sources officielles
│
├── .gitignore
├── README.md                 # Ce fichier
└── LICENSE                   # À définir (MIT recommandé)
```

---

## 🚀 Installation et usage

### Prérequis

- **Navigateur moderne** : Chrome 90+, Safari 14+, Firefox 88+
- **Python 3.9+** (pour le pipeline de données)
- **GDAL** (pour traitement géospatial)
- **Tippecanoe** (pour génération PMTiles)

### Installation locale (développement)

```bash
# Cloner le projet
git clone https://github.com/<votre-username>/qub-hunter.git
cd qub-hunter

# Option 1 : Serveur HTTP simple pour tester
python3 -m http.server 8000
# Ouvrir http://localhost:8000/web/

# Option 2 : Ouvrir directement le HTML
open web/index.html  # macOS
xdg-open web/index.html  # Linux
start web/index.html  # Windows
```

### Installation du pipeline (Phase 02+)

```bash
cd pipeline

# Créer environnement virtuel
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# ou
venv\Scripts\activate  # Windows

# Installer dépendances
pip install -r requirements.txt

# Télécharger cadastre Mauricie
python download_cadastre.py --region mauricie

# Générer PMTiles
python generate_pmtiles.py --region mauricie --output ../data/pmtiles/
```

---

## 🎨 Design & UX

### Palette de couleurs

Le design s'inspire des **cartes d'arpentage anciennes** et de l'esthétique **outdoor/topographique** :

```css
--forest-deep: #1d2818    /* Vert forêt profond */
--forest: #2a3826          /* Vert forêt principal */
--moss: #6b7d4a            /* Mousse */
--bark: #4a3829            /* Écorce */
--paper: #f0e8d6           /* Papier vieilli */
--paper-aged: #d4c5a0      /* Papier crème */
--gold: #b88a3e            /* Or (accent) */
--rust: #a04a28            /* Rouille */
--blood: #6b1a14           /* Sang (erreurs) */
```

### Typographie

- **Titres** : Cormorant Garamond (serif, style cartes anciennes)
- **Données techniques** : IBM Plex Mono (monospace)
- **Corps de texte** : Inria Sans (sans-serif lisible)

---

## 📊 Données & Layers

### Territoires récréatifs (TRQ) — MRNF

| Layer ID | Nom | Description |
|----------|-----|-------------|
| 0 | Aire faunique communautaire | AFC |
| 1 | Entente autochtones | Territoires spéciaux |
| 8 | Pourvoiries à droits exclusifs | ~600 territoires |
| 10 | Refuges fauniques | Protection de la faune |
| 11 | Réserves fauniques | SÉPAQ, réservation requise |
| 16 | ZEC (Zones d'exploitation contrôlée) | 63 territoires, chasse permise |
| 4-5 | Parcs nationaux (Canada + Québec) | Chasse interdite |

### Cadastre rénové

- **Format source** : Shapefile (EPSG:32198 — NAD83 Québec Lambert)
- **Découpage** : par région administrative (17 régions)
- **Nombre de lots** : ~3,5 millions au total
- **Attributs clés** : 
  - `NO_LOT` : Numéro de lot
  - `NO_CADASTRE` : Code cadastre
  - `SUPERFICIE` : Superficie en m²

### Régions disponibles (Phase 02+)

- ✅ **Mauricie** (Phase 02 — première région)
- 🔜 Outaouais, Laurentides, Saguenay–Lac-St-Jean (Phase 03)
- 🔜 Toutes les régions (Phase 04)

---

## 🗺️ Feuille de route

### Phase 01 : Prototype ✅
- [x] Carte MapLibre fonctionnelle
- [x] Interface mobile-first
- [x] Polygones de démonstration
- [x] Géolocalisation
- [x] Diagnostic du chargement

### Phase 02 : Données officielles ✅
- [x] Connexion ArcGIS REST MRNF (ZEC, pourvoiries, réserves, parcs)
- [x] Pipeline cadastre Mauricie → PMTiles (scripts Python)
- [x] Recherche par numéro de lot (API iCherche + fallback local)
- [x] Zones de chasse 1-29

### Phase 03 : Mode hors-ligne
- [ ] Service Worker pour cache intelligent
- [ ] Téléchargement par région
- [ ] IndexedDB pour stockage PMTiles
- [ ] Interface de gestion des téléchargements

### Phase 04 : Fonctionnalités avancées
- [ ] Cadastre complet (17 régions)
- [ ] Filtres par espèce (orignal, chevreuil, ours, dinde)
- [ ] Règlements par zone/territoire
- [ ] Partage de position GPS
- [ ] Export GPX/KML

---

## 🤝 Contribution

Ce projet est **open source**. Les contributions sont bienvenues !

### Comment contribuer

1. Fork le projet
2. Crée une branche pour ta fonctionnalité (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commit tes changements (`git commit -m 'Ajout de X'`)
4. Push vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Ouvre une Pull Request

### Guidelines

- Code en **vanilla JavaScript** (pas de frameworks lourds)
- Respecter la **palette de couleurs** existante
- Tester sur **mobile** avant de soumettre
- Documenter les nouvelles sources de données

---

## 📜 Licence

*À définir. Suggestions : MIT, Apache 2.0, ou GNU GPLv3.*

---

## 🙏 Crédits

### Données

- **Gouvernement du Québec** — Données ouvertes
  - Ministère des Ressources naturelles et des Forêts (MRNF)
  - Cadastre rénové du Québec
  - Territoires récréatifs (TRQ)
- **OpenStreetMap Contributors** — Fond de carte
- **CARTO** — Tuiles raster Voyager

### Outils

- **MapLibre GL JS** — Carte interactive open-source
- **Tippecanoe** (Mapbox) — Génération de tuiles vectorielles
- **GDAL/OGR** — Traitement géospatial

---

## 📧 Contact

Pour questions, suggestions ou signaler un bug :
- Ouvrir une **issue** sur GitHub
- Email : *[à compléter]*

---

## 📝 Notes de développement

### Problèmes connus (Phase 01)

1. **Web Workers bloqués dans preview Claude** : `useWebWorkers: false` ajouté pour compatibilité sandbox. Retirer cette ligne en production.
2. **Tuiles raster bloquées dans sandbox** : Les services OSM/CARTO/Stadia peuvent échouer dans l'environnement de prévisualisation Claude. Fonctionne normalement en local ou déployé.
3. **Géolocalisation indisponible en sandbox** : Normal, nécessite un contexte HTTPS sécurisé.

### Optimisations prévues

- **Phase 02** : Chargement progressif des couches (zoom-dependent)
- **Phase 03** : Compression Brotli des PMTiles
- **Phase 04** : Simplification géométrique adaptative selon zoom

---

**Dernière mise à jour** : 27 avril 2026  
**Version** : 0.2.0-alpha (Phase 02)
