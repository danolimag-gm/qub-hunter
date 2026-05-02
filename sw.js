/* Qub Hunter — Service Worker — Phase 03 — V2 */
'use strict';

const STATIC = 'qub-hunter-static-v1';
const MRNF = 'qub-hunter-mrnf-v1';
const TILES = 'qub-hunter-tiles-v1';
const ALL_CACHES = [STATIC, MRNF, TILES];
const MAX_TILES = 500;

const PRECACHE_URLS = [
  'https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.css',
  'https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.js',
  'https://cdn.jsdelivr.net/npm/pmtiles@3.2.0/dist/pmtiles.js'
];

// ── INSTALL : pré-cache assets statiques ──────────────────────────────────────
self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const cache = await caches.open(STATIC);
    await cache.addAll(PRECACHE_URLS).catch(() => { });
  })());
  self.skipWaiting();
});

// ── ACTIVATE : purge anciens caches ──────────────────────────────────────────
self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys.filter(k => !ALL_CACHES.includes(k))
        .map(k => caches.delete(k))
    );
  })());
  self.clients.claim();
});

// ── FETCH : stratégies de cache ───────────────────────────────────────────────
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;

  let url;
  try { url = new URL(e.request.url); } catch { return; }

  const host = url.hostname;

  // Assets statiques CDN (MapLibre, PMTiles.js, Google Fonts)
  if (host.includes('jsdelivr') ||
    host.includes('googleapis') ||
    host.includes('gstatic')) {
    e.respondWith(cacheFirst(e.request, STATIC));
    return;
  }

  // APIs MRNF (ArcGIS REST) et iCherche : Network First avec fallback cache
  if (host.includes('mern.gouv.qc.ca') ||
    host.includes('msp.gouv.qc.ca')) {
    e.respondWith(networkFirst(e.request, MRNF));
    return;
  }

  // Tuiles raster (CARTO, OSM, Stadia) : Cache First avec limite 500 tuiles
  if (host.includes('cartocdn') ||
    host.includes('openstreetmap') ||
    host.includes('stadiamaps')) {
    e.respondWith(tileFirst(e.request));
    return;
  }
});

// Cache First : sert depuis le cache, tente le réseau si absent
async function cacheFirst(request, cacheName) {
  try {
    const cached = await caches.match(request);
    if (cached) return cached;

    const response = await fetch(request);
    if (response.ok && response.status !== 206) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Network error', { status: 408 });
  }
}

// Network First : tente le réseau, fallback cache si hors-ligne
async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok && response.status !== 206) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;

    return new Response(JSON.stringify({ error: 'offline', features: [] }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

// Tile First : Cache First avec FIFO si limite atteinte
async function tileFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (!response.ok || response.status === 206) return response;

    const cache = await caches.open(TILES);
    const keys = await cache.keys();
    if (keys.length >= MAX_TILES) {
      await cache.delete(keys[0]);
    }
    cache.put(request, response.clone());
    return response;
  } catch {
    return new Response('', { status: 503, statusText: 'Offline' });
  }
}
