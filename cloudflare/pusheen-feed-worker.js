/*
 * Pusheen V2Ray delivery gateway.
 *
 * The Worker publishes only an explicit allowlist of reviewed public artifacts.
 * It refreshes a Cloudflare KV mirror from GitHub and serves the live GitHub
 * artifact while the origin is healthy. If GitHub is unavailable, it falls back
 * to the most recently mirrored non-empty artifact. This is independent of the
 * GitHub request path, but it is not a guarantee during a complete international
 * shutdown or a Cloudflare-specific restriction.
 */

const UPSTREAM_ROOT = "https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/";
const CACHE_SECONDS = 60;
const UPSTREAM_TIMEOUT_MS = 12_000;
const KV_ARTIFACT_PREFIX = "artifact:";
const KV_METADATA_PREFIX = "metadata:";

const ARTIFACTS = {
  "all.txt": "subscriptions/all.txt",
  "balanced.txt": "subscriptions/reachable.txt",
  "fast.txt": "subscriptions/reachable-fast.txt",
  "strict.txt": "subscriptions/strict.txt",
  "resilient.txt": "subscriptions/resilient.txt",
  "outage.txt": "subscriptions/outage.txt",
  "resilient.receipts.v1.json": "subscriptions/resilient.receipts.v1.json",
  "resilient.manifest.v1.json": "subscriptions/resilient.manifest.v1.json",
  "outage.receipts.v1.json": "subscriptions/outage.receipts.v1.json",
  "outage.manifest.v1.json": "subscriptions/outage.manifest.v1.json",
  "resilient-xray.json": "profiles/resilient-xray.json",
  "resilient-xray.meta.v1.json": "profiles/resilient-xray.meta.v1.json",
  "status.json": "status.json",
  "current-release.json": "releases/current-release.json",
};

// These five artifacts are mirrored by Cron after each publication window.
// The remaining allowlisted artifacts are mirrored opportunistically on a
// successful client request, avoiding needless KV writes while retaining a
// last-known-good path for the continuity tier.
const SCHEDULED_ARTIFACTS = [
  "subscriptions/resilient.txt",
  "subscriptions/outage.txt",
  "subscriptions/strict.txt",
  "subscriptions/resilient.receipts.v1.json",
  "subscriptions/outage.receipts.v1.json",
  "profiles/resilient-xray.json",
  "status.json",
  "releases/current-release.json",
];

addEventListener("fetch", (event) => {
  event.respondWith(handleRequest(event.request, event));
});

addEventListener("scheduled", (event) => {
  event.waitUntil(refreshAllArtifacts());
});

async function handleRequest(request, ctx) {
  const url = new URL(request.url);
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("method not allowed", { status: 405, headers: { Allow: "GET, HEAD" } });
  }
  if (url.pathname === "/health") {
    return jsonResponse({
      service: "Pusheen V2Ray delivery gateway",
      schema_version: 2,
      artifacts: Object.keys(ARTIFACTS),
      cache_seconds: CACHE_SECONDS,
      delivery: "fresh GitHub origin with Cloudflare KV last-known-good fallback",
      notice: "Independent of the GitHub request path; not an availability guarantee during an international shutdown.",
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
    const upstream = await fetchUpstream(artifact);
    const body = await upstream.arrayBuffer();
    if (body.byteLength === 0) throw new Error("empty_upstream_artifact");
    const response = artifactResponse(body, artifact, "fresh-origin");
    ctx.waitUntil(Promise.all([cache.put(cacheKey, response.clone()), mirrorArtifact(artifact, body)]));
    return request.method === "HEAD" ? headResponse(response) : response;
  } catch (error) {
    const mirrored = await readMirroredArtifact(artifact);
    if (mirrored) {
      const response = artifactResponse(mirrored.body, artifact, "kv-last-known-good", mirrored.metadata);
      return request.method === "HEAD" ? headResponse(response) : response;
    }
    if (cached) {
      const stale = withHeader(cached, "X-Pusheen-Delivery", "edge-cache-last-known-good");
      return request.method === "HEAD" ? headResponse(stale) : stale;
    }
    return jsonResponse({ error: "upstream_unavailable", artifact, retryable: true }, 503);
  }
}

async function refreshAllArtifacts() {
  const results = await Promise.allSettled(
    SCHEDULED_ARTIFACTS.map(async (artifact) => {
      const upstream = await fetchUpstream(artifact);
      const body = await upstream.arrayBuffer();
      if (body.byteLength === 0) throw new Error("empty_upstream_artifact");
      await mirrorArtifact(artifact, body);
    }),
  );
  return results.filter((result) => result.status === "fulfilled").length;
}

async function fetchUpstream(artifact) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort("upstream_timeout"), UPSTREAM_TIMEOUT_MS);
  try {
    const upstream = await fetch(new URL(artifact, UPSTREAM_ROOT), {
      headers: { Accept: "text/plain, application/json;q=0.9" },
      cf: { cacheTtl: CACHE_SECONDS, cacheEverything: true },
      signal: controller.signal,
    });
    if (!upstream.ok) throw new Error(`upstream_${upstream.status}`);
    return upstream;
  } finally {
    clearTimeout(timeout);
  }
}

async function mirrorArtifact(artifact, body) {
  if (typeof PUSHEEN_FEEDS === "undefined") return;
  const metadata = {
    mirrored_at: new Date().toISOString(),
    artifact,
    byte_length: body.byteLength,
    origin: "github-raw",
  };
  await Promise.all([
    PUSHEEN_FEEDS.put(KV_ARTIFACT_PREFIX + artifact, body),
    PUSHEEN_FEEDS.put(KV_METADATA_PREFIX + artifact, JSON.stringify(metadata)),
  ]);
}

async function readMirroredArtifact(artifact) {
  if (typeof PUSHEEN_FEEDS === "undefined") return null;
  const [body, metadata] = await Promise.all([
    PUSHEEN_FEEDS.get(KV_ARTIFACT_PREFIX + artifact, "arrayBuffer"),
    PUSHEEN_FEEDS.get(KV_METADATA_PREFIX + artifact, "json"),
  ]);
  if (!body || body.byteLength === 0) return null;
  return { body, metadata };
}

function artifactResponse(body, artifact, delivery, metadata) {
  const headers = safeHeaders(contentTypeFor(artifact), artifact, delivery, metadata);
  return new Response(body, { status: 200, headers });
}

function contentTypeFor(artifact) {
  return artifact.endsWith(".json")
    ? "application/json; charset=utf-8"
    : "text/plain; charset=utf-8";
}

function safeHeaders(contentType, artifact, delivery, metadata) {
  const headers = {
    "Content-Type": contentType,
    "Cache-Control": `public, max-age=60, s-maxage=${CACHE_SECONDS}, stale-if-error=86400`,
    "X-Content-Type-Options": "nosniff",
    "X-Pusheen-Artifact": artifact,
    "X-Pusheen-Delivery": delivery,
  };
  if (metadata && metadata.mirrored_at) headers["X-Pusheen-Mirrored-At"] = metadata.mirrored_at;
  return headers;
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
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
