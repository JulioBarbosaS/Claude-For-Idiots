// public/ is Astro's default static-assets directory (favicon, robots.txt,
// and -- with a PWA integration -- a hand-written or generated service
// worker like this one).
self.addEventListener("install", () => self.skipWaiting());
