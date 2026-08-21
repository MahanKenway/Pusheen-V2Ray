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
const LEGACY_KV_METADATA_PREFIX = "metadata:";
const RELEASE_MANIFEST_PATH = /^releases\/\d{8}T\d{6}Z-[a-f0-9]{12}\/manifest\.v2\.json$/;

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
  "outage-singbox.json": "profiles/outage-singbox.json",
  "outage-singbox.meta.v1.json": "profiles/outage-singbox.meta.v1.json",
  "status.json": "status.json",
  "current-release.json": "releases/current-release.json",
  "delivery-status.v1.json": "monitoring/delivery-status.v1.json",
  "slo-status.v1.json": "monitoring/slo-status.v1.json",
  "dashboard": "monitoring/dashboard.html",
};

// Continuity artifacts are mirrored only by bounded Cron refreshes, never by
// client traffic. The two-hour Cron mirrors only the delivery-critical paths:
// Primary, Strict, Resilient, Outage, the outage sing-box profile, and the
// current release pointer plus its immutable manifest. This caps worst-case KV
// writes at 84 per day (seven entries × twelve runs), while GitHub origin still
// serves every allowlisted artifact fresh on normal requests.
const SCHEDULED_ARTIFACTS = [
  "subscriptions/all.txt",
  "subscriptions/strict.txt",
  "subscriptions/resilient.txt",
  "subscriptions/outage.txt",
  "profiles/outage-singbox.json",
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
    const mirror = await mirrorHealthSummary();
    return jsonResponse({
      service: "Pusheen V2Ray delivery gateway",
      schema_version: 3,
      artifacts: Object.keys(ARTIFACTS),
      cache_seconds: CACHE_SECONDS,
      delivery: "fresh GitHub origin with Cloudflare KV last-known-good fallback",
      mirror,
      notice: "Independent of the GitHub request path; not an availability guarantee during an international shutdown.",
    });
  }

  const requestedPath = url.pathname.slice(1);
  const artifact = ARTIFACTS[requestedPath]
    || (RELEASE_MANIFEST_PATH.test(requestedPath) ? requestedPath : null);
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
    ctx.waitUntil(cache.put(cacheKey, response.clone()));
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
  const results = await Promise.allSettled([
    ...SCHEDULED_ARTIFACTS.map(refreshArtifact),
    refreshReleasePointerAndManifest(),
  ]);
  return results.filter((result) => result.status === "fulfilled").length;
}

async function refreshArtifact(artifact) {
  const body = await fetchArtifactBody(artifact);
  await mirrorArtifact(artifact, body);
}

async function refreshReleasePointerAndManifest() {
  const pointerArtifact = "releases/current-release.json";
  const pointerBody = await fetchArtifactBody(pointerArtifact);
  let pointer;
  try {
    pointer = JSON.parse(new TextDecoder().decode(pointerBody));
  } catch {
    throw new Error("invalid_current_release_pointer");
  }

  const manifestArtifact = pointer?.manifest_path;
  if (typeof manifestArtifact !== "string" || !RELEASE_MANIFEST_PATH.test(manifestArtifact)) {
    throw new Error("invalid_release_manifest_path");
  }

  const manifestBody = await fetchArtifactBody(manifestArtifact);
  await Promise.all([
    mirrorArtifact(pointerArtifact, pointerBody),
    mirrorArtifact(manifestArtifact, manifestBody),
  ]);
}

async function fetchArtifactBody(artifact) {
  const upstream = await fetchUpstream(artifact);
  const body = await upstream.arrayBuffer();
  if (body.byteLength === 0) throw new Error("empty_upstream_artifact");
  return body;
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
  if (typeof PUSHEEN_FEEDS === "undefined") return { mirrored: false, reason: "not_configured" };
  const key = KV_ARTIFACT_PREFIX + artifact;
  const contentSha256 = await sha256Hex(body);
  const existing = await PUSHEEN_FEEDS.getWithMetadata(key, "arrayBuffer");
  const existingHash = existing?.metadata?.content_sha256;
  if (existingHash === contentSha256 && existing?.value?.byteLength === body.byteLength) {
    return { mirrored: false, reason: "unchanged" };
  }
  const metadata = {
    mirrored_at: new Date().toISOString(),
    artifact,
    byte_length: body.byteLength,
    content_sha256: contentSha256,
    origin: "github-raw",
  };
  await PUSHEEN_FEEDS.put(key, body, { metadata });
  return { mirrored: true, reason: existing?.value ? "changed" : "new" };
}

async function sha256Hex(body) {
  const digest = await crypto.subtle.digest("SHA-256", body);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function mirrorHealthSummary() {
  if (typeof PUSHEEN_FEEDS === "undefined") return { state: "not_configured" };
  const criticalArtifacts = [
    "subscriptions/all.txt",
    "subscriptions/resilient.txt",
    "subscriptions/outage.txt",
    "subscriptions/strict.txt",
    "releases/current-release.json",
  ];
  const metadata = await Promise.all(
    criticalArtifacts.map(async (artifact) => {
      const stored = await PUSHEEN_FEEDS.getWithMetadata(KV_ARTIFACT_PREFIX + artifact, "arrayBuffer");
      return stored?.metadata || PUSHEEN_FEEDS.get(LEGACY_KV_METADATA_PREFIX + artifact, "json");
    })
  );
  const timestamps = metadata
    .map((item) => item?.mirrored_at)
    .filter((value) => typeof value === "string")
    .map((value) => Date.parse(value))
    .filter((value) => Number.isFinite(value));
  if (timestamps.length === 0) {
    return { state: "empty", critical_artifact_count: criticalArtifacts.length };
  }
  return {
    state: "available",
    critical_artifact_count: criticalArtifacts.length,
    mirrored_critical_artifact_count: timestamps.length,
    critical_oldest_age_seconds: Math.max(0, Math.floor((Date.now() - Math.min(...timestamps)) / 1000)),
  };
}

async function readMirroredArtifact(artifact) {
  if (typeof PUSHEEN_FEEDS === "undefined") return null;
  const stored = await PUSHEEN_FEEDS.getWithMetadata(KV_ARTIFACT_PREFIX + artifact, "arrayBuffer");
  if (!stored?.value || stored.value.byteLength === 0) return null;
  const metadata = stored.metadata || await PUSHEEN_FEEDS.get(LEGACY_KV_METADATA_PREFIX + artifact, "json");
  return { body: stored.value, metadata };
}

function artifactResponse(body, artifact, delivery, metadata) {
  const headers = safeHeaders(contentTypeFor(artifact), artifact, delivery, metadata);
  return new Response(body, { status: 200, headers });
}

function contentTypeFor(artifact) {
  if (artifact.endsWith(".json")) return "application/json; charset=utf-8";
  if (artifact.endsWith(".html")) return "text/html; charset=utf-8";
  return "text/plain; charset=utf-8";
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
