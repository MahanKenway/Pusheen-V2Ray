/*
 * Pusheen V2Ray delivery gateway.
 *
 * This Worker intentionally exposes only reviewed public artifacts. It reads
 * them from GitHub from the Cloudflare edge, so clients do not need a direct
 * route to github.com/raw.githubusercontent.com. It is not a guarantee against
 * an international blackout or a Cloudflare-specific restriction.
 */

const UPSTREAM_ROOT = "https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/";
// Keep origin cache shorter than the 15-minute publisher cadence so a newly
// published feed is never delayed by a five-minute shared edge entry.
const CACHE_SECONDS = 60;
const ARTIFACTS = {
  "all.txt": "subscriptions/all.txt",
  "balanced.txt": "subscriptions/reachable.txt",
  "fast.txt": "subscriptions/reachable-fast.txt",
  "strict.txt": "subscriptions/strict.txt",
  "resilient.txt": "subscriptions/resilient.txt",
  "resilient.receipts.v1.json": "subscriptions/resilient.receipts.v1.json",
  "resilient.manifest.v1.json": "subscriptions/resilient.manifest.v1.json",
  "resilient-xray.json": "profiles/resilient-xray.json",
  "resilient-xray.meta.v1.json": "profiles/resilient-xray.meta.v1.json",
  "status.json": "status.json",
};

addEventListener("fetch", (event) => {
  event.respondWith(handleRequest(event.request, event));
});

async function handleRequest(request, ctx) {
    const url = new URL(request.url);
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
    }
    if (url.pathname === "/health") {
      return jsonResponse({
        service: "Pusheen V2Ray delivery gateway",
        schema_version: 1,
        artifacts: Object.keys(ARTIFACTS),
        cache_seconds: CACHE_SECONDS,
        notice: "Independent delivery origin; not an availability guarantee during an international shutdown.",
      });
    }
    const artifact = ARTIFACTS[url.pathname.slice(1)];
    if (!artifact) {
      return jsonResponse({ error: "artifact_not_found", available: Object.keys(ARTIFACTS) }, 404);
    }

    const cache = caches.default;
    const cacheKey = new Request(url.origin + url.pathname, { method: "GET" });
    const cached = await cache.match(cacheKey);
    try {
      const upstream = await fetch(new URL(artifact, UPSTREAM_ROOT), {
        headers: { Accept: "text/plain, application/json;q=0.9" },
        cf: { cacheTtl: CACHE_SECONDS, cacheEverything: true },
      });
      if (!upstream.ok) throw new Error(`upstream_${upstream.status}`);
      const body = await upstream.arrayBuffer();
      if (body.byteLength === 0) throw new Error("empty_upstream_artifact");
      const response = artifact.endsWith(".json")
        ? new Response(body, { status: 200, headers: safeHeaders("application/json; charset=utf-8", artifact, "fresh") })
        : new Response(body, { status: 200, headers: safeHeaders("text/plain; charset=utf-8", artifact, "fresh") });
      ctx.waitUntil(cache.put(cacheKey, response.clone()));
      return request.method === "HEAD" ? headResponse(response) : response;
    } catch (error) {
      if (cached) {
        const stale = withHeader(cached, "X-Pusheen-Delivery", "stale-edge-cache");
        return request.method === "HEAD" ? headResponse(stale) : stale;
      }
      return jsonResponse({ error: "upstream_unavailable", artifact, retryable: true }, 503);
    }
}

function safeHeaders(contentType, artifact, state) {
  return {
    "Content-Type": contentType,
    "Cache-Control": `public, max-age=60, s-maxage=${CACHE_SECONDS}, stale-if-error=86400`,
    "X-Content-Type-Options": "nosniff",
    "X-Pusheen-Artifact": artifact,
    "X-Pusheen-Delivery": state,
  };
}

function withHeader(response, name, value) {
  const headers = new Headers(response.headers);
  headers.set(name, value);
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

function headResponse(response) {
  return new Response(null, { status: response.status, statusText: response.statusText, headers: response.headers });
}

function jsonResponse(value, status = 200) {
  return new Response(JSON.stringify(value, null, 2) + "\n", {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" },
  });
}
