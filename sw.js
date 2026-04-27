/* Qub Hunter — Service Worker — Phase 03 */
'use strict';

var STATIC = 'qub-hunter-static-v1';
var MRNF   = 'qub-hunter-mrnf-v1';
var TILES  = 'qub-hunter-tiles-v1';
var ALL_CACHES = [STATIC, MRNF, TILES];
var MAX_TILES  = 500;

var PRECACHE_URLS = [
  'https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.css',
  'https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.js',
  'https://cdn.jsdelivr.net/npm/pmtiles@3.2.0/dist/pmtiles.js'
];

// ── INSTALL : pré-cache assets statiques ──────────────────────────────────────
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(STATIC).then(function(cache) {
      return cache.addAll(PRECACHE_URLS).catch(function() {});
    })
  );
  self.skipWaiting();
});

// ── ACTIVATE : purge anciens caches ──────────────────────────────────────────
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return ALL_CACHES.indexOf(k) === -1; })
            .map(function(k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

// ── FETCH : stratégies de cache ───────────────────────────────────────────────
self.addEventListener('fetch', function(e) {
  var url;
  try { url = new URL(e.request.url); } catch(_) { return; }

  if (e.request.method !== 'GET') return;

  var host = url.hostname;

  // Assets statiques CDN (MapLibre, PMTiles.js, Google Fonts)
  if (host.indexOf('jsdelivr') !== -1 ||
      host.indexOf('googleapis') !== -1 ||
      host.indexOf('gstatic') !== -1) {
    e.respondWith(cacheFirst(e.request, STATIC));
    return;
  }

  // APIs MRNF (ArcGIS REST) et iCherche : Network First avec fallback cache
  if (host.indexOf('mern.gouv.qc.ca') !== -1 ||
      host.indexOf('msp.gouv.qc.ca') !== -1) {
    e.respondWith(networkFirst(e.request, MRNF));
    return;
  }

  // Tuiles raster (CARTO, OSM, Stadia) : Cache First avec limite 500 tuiles
  if (host.indexOf('cartocdn') !== -1 ||
      host.indexOf('openstreetmap') !== -1 ||
      host.indexOf('stadiamaps') !== -1) {
    e.respondWith(tileFirst(e.request));
    return;
  }
});

// Cache First : sert depuis le cache, tente le réseau si absent
function cacheFirst(request, cacheName) {
  return caches.match(request).then(function(cached) {
    if (cached) return cached;
    return fetch(request).then(function(response) {
      if (response.ok) {
        caches.open(cacheName).then(function(c) { c.put(request, response.clone()); });
      }
      return response;
    });
  });
}

// Network First : tente le réseau, fallback cache si hors-ligne
function networkFirst(request, cacheName) {
  return fetch(request).then(function(response) {
    if (response.ok) {
      caches.open(cacheName).then(function(c) { c.put(request, response.clone()); });
    }
    return response;
  }).catch(function() {
    return caches.match(request).then(function(cached) {
      if (cached) return cached;
      return new Response(JSON.stringify({ error: 'offline', features: [] }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      });
    });
  });
}

// Tile First : Cache First avec FIFO si limite atteinte
function tileFirst(request) {
  return caches.match(request).then(function(cached) {
    if (cached) return cached;
    return fetch(request).then(function(response) {
      if (!response.ok) return response;
      caches.open(TILES).then(function(cache) {
        cache.keys().then(function(keys) {
          if (keys.length >= MAX_TILES) cache.delete(keys[0]);
          cache.put(request, response.clone());
        });
      });
      return response;
    }).catch(function() {
      return new Response('', { status: 503, statusText: 'Offline' });
    });
  });
}
