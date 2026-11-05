// عامل خدمة بسيط: يخزّن ملفات الواجهة فقط، أما /api فمن الشبكة دائمًا.
const CACHE = "smm-v10";
const FILES = ["./", "style.css", "app.js", "manifest.webmanifest", "privacy.html", "terms.html", "icons/icon-512-maskable.png", "icons/icon-192.png", "icons/icon-512.png", "locales/languages.json", "locales/ar.json", "locales/en.json", "locales/fr.json", "locales/es.json", "locales/tr.json"];
self.addEventListener("install", e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES))));
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/")) return;
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
