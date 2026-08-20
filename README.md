# Pusheen V2Ray

<p align="center">
  <img src="assets/brand/pusheen-playing-bone.jpg" alt="Selected Pusheen brand artwork" width="280">
</p>

> **Playful branding. Measured routes.**

**Pusheen V2Ray** is a quality-first proxy feed pipeline. It replaces the opaque pattern of collecting a large list and publishing it immediately with a traceable process: reviewed sources, typed parsing, bounded validation, health history, transparent scoring, and immutable publications.

Pusheen V2Ray is an independent project that began from the public Freedom-V2Ray codebase under its MIT license. Its product direction, architecture, release process, and automation are independent; `upstream` remains configured only as an optional reference.

## Subscription links

The repository is public and publishes consumer-facing feeds under `subscriptions/`. Stable URLs change their contents only after the corresponding feed itself changes.

| Feed | Raw URI list | Base64 subscription |
|---|---|---|
| Primary high-coverage feed (recent TCP-reachable; target: ≥100) | [all.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all.txt) | [all.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all.base64) |
| Strict end-to-end qualified feed | [strict.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/strict.txt) | [strict.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/strict.base64) |
| Primary VLESS | [all-vless.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all-vless.txt) | [all-vless.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all-vless.base64) |
| Primary Trojan | [all-trojan.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all-trojan.txt) | [all-trojan.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all-trojan.base64) |
| Primary VMess | [all-vmess.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all-vmess.txt) | [all-vmess.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all-vmess.base64) |
| Primary Hysteria 2 | `subscriptions/all-hysteria2.txt` when recent evidence exists | `subscriptions/all-hysteria2.base64` when recent evidence exists |
| Balanced TCP-reachable protocols | [reachable.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable.txt) | [reachable.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable.base64) |
| Balanced fast subset | [reachable-fast.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable-fast.txt) | [reachable-fast.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable-fast.base64) |
| Balanced VLESS | [reachable-vless.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable-vless.txt) | [reachable-vless.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable-vless.base64) |
| Balanced VMess | [reachable-vmess.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable-vmess.txt) | [reachable-vmess.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable-vmess.base64) |
| Balanced Trojan | [reachable-trojan.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable-trojan.txt) | [reachable-trojan.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable-trojan.base64) |
| Balanced Shadowsocks | [reachable-ss.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable-ss.txt) | [reachable-ss.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable-ss.base64) |
| Resilient anti-concentration feed (recent TCP-reachable) | [resilient.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/resilient.txt) | [resilient.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/resilient.base64) |
| Strict VLESS | `subscriptions/strict-vless.txt` after first qualified VLESS publication | `subscriptions/strict-vless.base64` after first qualified VLESS publication |
| Strict VMess | `subscriptions/strict-vmess.txt` after first qualified VMess publication | `subscriptions/strict-vmess.base64` after first qualified VMess publication |
| Strict Trojan | `subscriptions/strict-trojan.txt` after first qualified Trojan publication | `subscriptions/strict-trojan.base64` after first qualified Trojan publication |
| Strict Shadowsocks | `subscriptions/strict-ss.txt` after first qualified Shadowsocks publication | `subscriptions/strict-ss.base64` after first qualified Shadowsocks publication |

Use [all.manifest.v1.json](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all.manifest.v1.json) for the primary high-coverage feed and [strict.manifest.v1.json](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/strict.manifest.v1.json) for end-to-end strict metadata. The primary feed retains up to **72 hours** of TCP-reachability evidence, is capped at 250 entries, targets at least 100 entries, and is intentionally broader but is not an end-to-end availability guarantee for every user network. Its ordering follows the **latest successful TCP handshake latency**, then freshness, so the lowest observed latency from the validator vantage is first. Protocol-specific variants remain available for VLESS, Trojan, VMess, and Hysteria 2 when evidence exists. See the public-safe [status.json](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/status.json) for current counts, freshness, and source health; it never exposes subscription URIs or credentials.

### Independent delivery and outage-safe artifacts

If a client cannot reach GitHub content directly, use the **Cloudflare delivery gateway**: [all](https://pusheen-feed-gateway.mahankenway.workers.dev/all.txt), [balanced](https://pusheen-feed-gateway.mahankenway.workers.dev/balanced.txt), [strict](https://pusheen-feed-gateway.mahankenway.workers.dev/strict.txt), [resilient](https://pusheen-feed-gateway.mahankenway.workers.dev/resilient.txt), and [public status](https://pusheen-feed-gateway.mahankenway.workers.dev/status.json). The gateway allowlists a small public artifact set, serves it from the Cloudflare edge, and retains a short edge cache for upstream outages. It is an independent **delivery origin**, not a guarantee that Cloudflare, international connectivity, or any proxy transport will remain reachable during a total shutdown.

The resilient feed applies source, endpoint, protocol, and transport-family concentration limits to the same recent TCP-evidence pool. Its [credential-free evidence receipts](https://pusheen-feed-gateway.mahankenway.workers.dev/resilient.receipts.v1.json) describe each selected member by truncated identity, protocol, transport family, source lineage, evidence contract, and validator vantage without publishing a hostname or credential. Its [Xray failover profile](https://pusheen-feed-gateway.mahankenway.workers.dev/resilient-xray.json) requires **Xray Core 26.3.27+**, listens only on local SOCKS `127.0.0.1:10808`, uses the local `leastPing` observer every five minutes, and deliberately blocks traffic if no observed outbound remains rather than falling back to direct traffic. Review the matching [profile metadata](https://pusheen-feed-gateway.mahankenway.workers.dev/resilient-xray.meta.v1.json) before use.

## Quality contract

A candidate progresses through this lifecycle:

```text
DISCOVERED → PARSED → POLICY_ACCEPTED → QUEUED
  → REACHABLE → E2E_VERIFIED → QUALIFIED → PUBLISHED
```

A successful TCP connection is not enough for the strict feed. Pusheen V2Ray creates a temporary local Xray SOCKS runtime, probes an approved HTTPS endpoint through that runtime, records structured evidence in PostgreSQL, and requires an `END_TO_END` success for strict publication. A second independent HTTPS endpoint is used when the primary destination is unavailable, reducing target-specific false negatives without weakening the evidence requirement. The separately labeled balanced tier retains recent TCP-reachability evidence to offer a broader user-testable set without claiming end-to-end availability.

| Capability | Status |
|---|---|
| Versioned source registry, typed parsing, and canonical deduplication | Implemented |
| Bounded HTTPS ingestion and reviewable source policy | Implemented |
| Xray runtime configuration and isolated end-to-end probe | Implemented |
| Persistent PostgreSQL history, status, scorecards, and snapshots | Implemented |
| Stable raw/Base64 subscription artifacts | Implemented |
| Scheduled guarded publication | Implemented and enabled; up to 8 candidates per run with four bounded validation workers |
| Independent Cloudflare delivery origin | Implemented; short cache, stale-on-upstream-error behavior, and strict public allowlist |
| Resilient anti-concentration tier and evidence receipts | Implemented; TCP-evidence only, credential-free receipts, no Iran-specific availability claim |
| Xray local least-ping failover profile | Implemented; generated only from resilient members and schema-checked with pinned Xray |
| Source health and automatic quarantine | Implemented; repeated fetch failures or ≥80% parse rejection temporarily quarantine a source |
| Public operational status | Implemented via `status.json`; aggregate-only and credential-safe |

## Automation

The guarded subscription workflow targets minutes **07, 22, 37, and 52** of each hour. It permits no overlapping runs, applies a hard timeout, evaluates up to **8 candidates per run** in least-recently-tested order, and runs at most **four isolated Xray validations concurrently**. Each strict candidate still requires a successful HTTPS request through its own temporary Xray SOCKS runtime; concurrency only increases throughput and does not weaken the quality criterion. Sources quarantined by health evidence are excluded from the candidate pool for six hours and recover automatically after a successful later ingestion.

Before enabling it, configure the GitHub secret `KAVEH_DATABASE_URL` and the non-secret variables `KAVEH_PROBE_URL`, `KAVEH_VANTAGE_ID`, and `KAVEH_CANDIDATE_LIMIT`. `KAVEH_PROBE_FALLBACK_URL` is optional for local runs; automation uses a reviewed HTTPS fallback by default. `KAVEH_VALIDATION_WORKERS` accepts 1–8 for controlled local runs; GitHub Actions uses four workers. Set `KAVEH_AUTOMATION_ENABLED=true` only after a manual run succeeds. The legacy `KAVEH_*` names and the internal Python package `kaveh` remain deliberately stable for backwards compatibility.

## Architecture

```text
Source Registry → Fetcher → Container Normalizer → Protocol Parsers
    → Canonical Identity & Dedupe → Validation Queue
    → Schema / Reachability / Runtime / End-to-End evidence
    → PostgreSQL History & Scoring → Immutable Snapshot Publisher
```

The source tree follows a modular-monolith design. The `domain` package has no dependency on HTTP, database, process, or framework code. Infrastructure implements ports; application commands coordinate workflows; runtime adapters create isolated Xray configurations.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
cp configs/sources/registry.v1.example.json configs/sources/registry.v1.json
# Review the registry, add only approved HTTPS sources, then explicitly enable them.
python -m kaveh ingest --registry configs/sources/registry.v1.json
```

For PostgreSQL and Xray validation, see [the runbook](docs/postgres-xray-runbook.md). For scheduled subscription automation, see [the automation guide](docs/subscription-automation.md).

## Brand asset and attribution

The brand image at [`assets/brand/pusheen-playing-bone.jpg`](assets/brand/pusheen-playing-bone.jpg) was selected by the project owner from [Pusheen’s official artwork](https://pusheen.com/). Pusheen artwork and marks are associated with Pusheen Corp.; this repository does not claim ownership of them. Any public use remains subject to the relevant rights and permissions. The project owner may replace the image with licensed or original artwork at any time.

## License and source attribution

The code is distributed under this repository’s [MIT License](LICENSE). The project originated from [Freedom-V2Ray](https://github.com/MahanKenway/Freedom-V2Ray); original copyright and license notices are retained.
