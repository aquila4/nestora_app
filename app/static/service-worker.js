const CACHE_NAME = "nestora-v2";

// Cache core app shell
const urlsToCache = [
  "/",
  "/static/logo.png",
  "/static/back.png",
  "/static/favicon_io/apple-touch-icon.png",
  "/static/favicon_io/android-chrome-192x192.png"
];

// INSTALL → preload app shell
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
  self.skipWaiting();
});

// ACTIVATE → clean old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// FETCH → instant load first, network fallback
self.addEventListener("fetch", (event) => {

  // Only cache GET requests
  if (event.request.method !== "GET") return;

  event.respondWith(
    caches.match(event.request).then((cached) => {

      if (cached) {
        return cached;
      }

      return fetch(event.request).then((response) => {

        // Skip non-success responses
        if (!response || response.status !== 200) {
          return response;
        }

        // Clone response
        const responseClone = response.clone();

        caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, responseClone);
        });

        return response;
      });

    })
  );
});