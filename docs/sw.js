/* Service worker : la coquille de l'appli et l'index sont mis en cache, donc
   l'appli s'ouvre et cherche sans reseau. Les tuiles de carte ne sont PAS
   mises en cache a l'avance : sans reseau la carte reste vide, mais les
   portions s'affichent et le GPX s'exporte quand meme. */
var V = "vr-v1";
var SHELL = [
  "./", "./index.html", "./manifest.webmanifest",
  "./icon-192.png", "./icon-512.png", "./icon-maskable-512.png", "./favicon-32.png",
  "./data/index.json",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js",
  "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(V).then(function (c) {
      // addAll echoue en bloc si une seule entree manque : on ajoute une a une
      return Promise.all(SHELL.map(function (u) {
        return c.add(new Request(u, { mode: u.indexOf("http") === 0 ? "cors" : "same-origin" }))
          .catch(function () { return null; });
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (ks) {
      return Promise.all(ks.map(function (k) { return k === V ? null : caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  var r = e.request;
  if (r.method !== "GET") return;
  var u = new URL(r.url);

  // tuiles de carte : reseau seulement, jamais de cache (volume illimite)
  if (u.hostname.indexOf("tile.openstreetmap.org") >= 0) return;

  // l'index : le reseau d'abord pour attraper une mise a jour, le cache sinon
  if (u.pathname.indexOf("/data/index.json") >= 0) {
    e.respondWith(
      fetch(r).then(function (res) {
        if (res && res.ok) caches.open(V).then(function (c) { c.put(r, res.clone()); });
        return res;
      }).catch(function () { return caches.match(r); })
    );
    return;
  }

  // le reste : cache d'abord
  e.respondWith(
    caches.match(r).then(function (hit) {
      return hit || fetch(r).then(function (res) {
        if (res && res.ok && u.origin === location.origin) {
          caches.open(V).then(function (c) { c.put(r, res.clone()); });
        }
        return res;
      });
    })
  );
});
