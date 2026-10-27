// 농밥 서비스워커 — 인터넷이 되면 화면·식단 모두 항상 최신을 먼저 받고(받은 것은 저장),
// 오프라인일 때만 마지막으로 저장한 것을 보여줍니다.
// (예전 v1은 화면을 저장본 먼저 보여줘서, 화면과 데이터 구조가 바뀌면 옛 화면이 새 데이터를 못 읽는 문제가 있었음)
const CACHE = "nongbab-v2";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request, {cache: "no-cache"}).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); }
      return res;
    }).catch(() => caches.match(e.request, {ignoreSearch: true}).then(hit => hit || Response.error()))
  );
});
