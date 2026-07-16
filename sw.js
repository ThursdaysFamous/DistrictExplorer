/* ==== ENGINE:BEGIN sw-header ==== */
// App-shell + app-data cache. Never serve live district/roster API responses
// stale — a stale roster could name the wrong officeholder, and this app's
// rule is that officeholder data is never guessed or served stale. Bump
// CACHE_NAME whenever SHELL_URLS, GEOMETRY_URLS, or ROSTER_URLS change so a
// removed entry can't live forever; the activate handler deletes every
// other-named cache.
//
// The config section below is this fork's METRO block (docs/ENGINE_SYNC.md):
// a per-city cache name, the shell assets, and the fork's data/app/*.json
// files split by caching policy — ~static boundary geometry (cache-first,
// precached) vs officeholder rosters (network-first, never stale). Every file
// under data/app/ must appear in exactly one of the two data lists;
// validate_index.py enforces it. The handler logic below the config is shared
// engine and stays byte-identical across every metro fork.
//
// "./" and "./index.html" resolve to the same GitHub Pages document, so we
// precache only the canonical "./" — caching both stored two ~112 KB-gzip
// copies under two keys and re-downloaded the page at install. The manifest's
// start_url is still ./index.html and a deep bookmark may hit /index.html
// directly; the navigate-request branch in the fetch handler serves the cached
// "./" shell for any such navigation, so offline boot still works either way.
/* ==== ENGINE:END sw-header ==== */

/* ==== METRO:BEGIN sw-config ==== */
// (-v3 dropped the duplicate "./index.html" shell entry; -v4 added the two
// roster files missing from ROSTER_URLS; -v5 added the water-taxi marker
// icon shown when a point lands on water; -v6/-v7 added the Will County
// outline + board roster; -v8 added the Cook County seal marker icon shown
// for a point in Cook County outside the City of Chicago; -v9 dropped
// leaflet.css from the shell — it's now inlined in index.html (was a
// render-blocking <link>), so the page no longer requests it; -v10 added the
// pre-built legislative-district geometry (congress / il-senate / il-house),
// moved off live TIGERweb to same-origin cache-first data/app files; -v11
// precached the collar-county seal markers (Kane, Lake, Will) alongside Cook
// (-v8) — the counties in this Chicago app's usual footprint. Five more seals
// ship for downstate counties (Hamilton, Macon, Saline, St. Clair, Washington)
// but are intentionally left out of the shell precache: they load on demand
// (network, then the name-badge fallback offline), so rarely-seen markers don't
// weigh down every install.)
/* ==== GENERATED:BEGIN sw-metro-config ==== */
const CACHE_NAME = "district-explorer-shell-v11";

const SHELL_URLS = [
  "./",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/water-taxi.png",
  "./icons/seals/cook-county.png",
  "./icons/seals/kane.png",
  "./icons/seals/lake.png",
  "./icons/seals/will.png",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js",
];

// Boundary geometry (data/app/*.json, fetched lazily on first toggle).
// Boundaries change ~once a decade, so serve them cache-first (instant, and
// works offline) and refresh in the background. Precached at install so
// those layers work offline.
const GEOMETRY_URLS = [
  "./data/app/school-board-districts.json",
  "./data/app/il-supreme-court-districts.json",
  "./data/app/ccbr-districts.json",
  "./data/app/will-county-outline.json",
  "./data/app/congress-districts.json",
  "./data/app/il-senate-districts.json",
  "./data/app/il-house-districts.json",
];

// Roster/officeholder data (also in data/app/) is refreshed by the weekly CI
// and must never be served stale — network-first, with the cached copy only
// as an offline fallback. Same freshness rule as the shell.
const ROSTER_URLS = [
  "./data/app/il-senate-members.json",
  "./data/app/il-house-members.json",
  "./data/app/school-board-members.json",
  "./data/app/congress-roster.json",
  "./data/app/cpd-district-info.json",
  "./data/app/ccpsa-district-councils.json",
  "./data/app/will-county-board-members.json",
];
/* ==== GENERATED:END sw-metro-config ==== */
/* ==== METRO:END sw-config ==== */

/* ==== ENGINE:BEGIN sw-handlers ==== */
const PRECACHE_URLS = SHELL_URLS.concat(GEOMETRY_URLS);

function inList(href, list) {
  return list.some((url) => new URL(url, self.registration.scope).href === href);
}

self.addEventListener("install", (event) => {
  // Cache each URL independently so one unreachable resource (e.g. a CDN blip)
  // doesn't fail the whole install — addAll() would abort atomically.
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      Promise.all(PRECACHE_URLS.map((url) => cache.add(url).catch(() => {})))
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// Network-first: online visitors always get the current copy, and the cache is
// refreshed as a side effect; offline falls back to the last good cached copy.
function networkFirst(request) {
  return fetch(request)
    .then((response) => {
      if (response.ok) {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
      }
      return response;
    })
    .catch(() => caches.match(request));
}

// Cache-first with background revalidation: serve the cached copy instantly
// (or fetch it the first time), and quietly refresh the cache for next time.
function cacheFirst(request) {
  return caches.match(request).then((cached) => {
    const network = fetch(request)
      .then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return response;
      })
      .catch(() => cached);
    return cached || network;
  });
}

self.addEventListener("fetch", (event) => {
  const href = new URL(event.request.url).href;

  // Page navigations (including an installed PWA's ./index.html start_url and
  // any deep /index.html bookmark): network-first so an online visitor always
  // gets the current page, falling back offline to the cached canonical shell
  // ("./") — which is why the duplicate "./index.html" precache entry could be
  // dropped without losing offline boot.
  if (event.request.mode === "navigate") {
    event.respondWith(
      networkFirst(event.request).then(
        (resp) => resp || caches.match(new URL("./", self.registration.scope).href)
      )
    );
    return;
  }

  // Shell and roster data: never stale online, cached only for offline boot.
  if (inList(href, SHELL_URLS) || inList(href, ROSTER_URLS)) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  // Boundary geometry: ~static, so cache-first for instant toggles + offline.
  if (inList(href, GEOMETRY_URLS)) {
    event.respondWith(cacheFirst(event.request));
    return;
  }

  // Everything else (all live district/roster API calls) hits the network normally.
});
/* ==== ENGINE:END sw-handlers ==== */
