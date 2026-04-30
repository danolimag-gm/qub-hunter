/**
 * Qub Hunter — Offline Manager
 * Gère le stockage IndexedDB pour les fichiers PMTiles volumineux.
 */
'use strict';

const DB_NAME = 'qub-hunter-off-db';
const DB_VERSION = 1;
const STORE_NAME = 'pmtiles-store';

const OfflineManager = {
    db: null,

    // Initialise la connexion à IndexedDB
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    db.createObjectStore(STORE_NAME);
                }
            };
            request.onsuccess = (e) => {
                this.db = e.target.result;
                resolve(this.db);
            };
            request.onerror = (e) => reject(e.target.error);
        });
    },

    // Télécharge une région et la stocke
    async downloadRegion(regionId, url, onProgress) {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const contentLength = response.headers.get('content-length');
            const total = parseInt(contentLength, 10);
            let loaded = 0;

            const reader = response.body.getReader();
            const chunks = [];

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                chunks.push(value);
                loaded += value.length;
                if (onProgress && total) {
                    onProgress(Math.round((loaded / total) * 100));
                }
            }

            const blob = new Blob(chunks);
            await this.saveBlob(regionId, blob);
            return blob;
        } catch (err) {
            console.error(`Erreur téléchargement ${regionId}:`, err);
            throw err;
        }
    },

    // Enregistre un Blob dans IndexedDB
    async saveBlob(id, blob) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.put(blob, id);
            request.onsuccess = () => resolve();
            request.onerror = (e) => reject(e.target.error);
        });
    },

    // Récupère un Blob depuis IndexedDB
    async getBlob(id) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_NAME], 'readonly');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.get(id);
            request.onsuccess = () => resolve(request.result);
            request.onerror = (e) => reject(e.target.error);
        });
    },

    // Supprime une région
    async deleteRegion(id) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_NAME], 'readwrite');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.delete(id);
            request.onsuccess = () => resolve();
            request.onerror = (e) => reject(e.target.error);
        });
    },

    // Liste les régions téléchargées
    async listDownloaded() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_NAME], 'readonly');
            const store = transaction.objectStore(STORE_NAME);
            const request = store.getAllKeys();
            request.onsuccess = () => resolve(request.result);
            request.onerror = (e) => reject(e.target.error);
        });
    }
};

// Export pour utilisation globale
window.OfflineManager = OfflineManager;