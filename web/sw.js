// Service worker : l'app reste utilisable hors ligne avec les derniers prix chargés.
const CACHE = "prix-eau-v2";
const COQUILLE = ["./", "index.html", "style.css", "app.js", "manifest.webmanifest", "img/icone.svg", "data/produits.json"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(COQUILLE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(cles => Promise.all(cles.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  // Prix et pages : réseau d'abord (données fraîches), cache en secours.
  // Images produits : cache d'abord (elles ne changent pas).
  const imageProduit = url.pathname.includes("/img/produits/");
  e.respondWith(imageProduit
    ? caches.match(e.request).then(r => r || fetch(e.request).then(rep => mettreEnCache(e.request, rep)))
    : fetch(e.request).then(rep => mettreEnCache(e.request, rep)).catch(() => caches.match(e.request)));
});

function mettreEnCache(req, rep) {
  if (rep.ok) {
    const copie = rep.clone();
    caches.open(CACHE).then(c => c.put(req, copie));
  }
  return rep;
}
