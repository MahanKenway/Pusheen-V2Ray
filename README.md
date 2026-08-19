# Pusheen V2Ray

<p align="center">
  <img src="assets/brand/pusheen-playing-bone.jpg" alt="Selected Pusheen brand artwork" width="280">
</p>

> **Playful branding. Measured routes.**

**Pusheen V2Ray** is a quality-first proxy feed pipeline. It replaces the opaque pattern of collecting a large list and publishing it immediately with a traceable process: reviewed sources, typed parsing, bounded validation, health history, transparent scoring, and immutable publications.

Pusheen V2Ray is an independent project that began from the public Freedom-V2Ray codebase under its MIT license. Its product direction, architecture, release process, and automation are independent; `upstream` remains configured only as an optional reference.

## Subscription links

The repository is public and publishes consumer-facing feeds under `subscriptions/`. Stable URLs change their contents only after the qualified feed itself changes.

| Feed | Raw URI list | Base64 subscription |
|---|---|---|
| All qualified protocols | [all.txt](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all.txt) | [all.base64](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all.base64) |
| VLESS | `subscriptions/vless.txt` after first qualified VLESS publication | `subscriptions/vless.base64` after first qualified VLESS publication |
| VMess | `subscriptions/vmess.txt` after first qualified VMess publication | `subscriptions/vmess.base64` after first qualified VMess publication |
| Trojan | `subscriptions/trojan.txt` after first qualified Trojan publication | `subscriptions/trojan.base64` after first qualified Trojan publication |
| Shadowsocks | `subscriptions/ss.txt` after first qualified Shadowsocks publication | `subscriptions/ss.base64` after first qualified Shadowsocks publication |

Use [manifest.v1.json](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/manifest.v1.json) to inspect snapshot metadata. Before the first end-to-end qualified result, the feed files are intentionally empty.

## Quality contract

A candidate progresses through this lifecycle:

```text
DISCOVERED → PARSED → POLICY_ACCEPTED → QUEUED
  → REACHABLE → E2E_VERIFIED → QUALIFIED → PUBLISHED
```

A successful TCP connection is never enough to qualify a feed entry. Pusheen V2Ray creates a temporary local Xray SOCKS runtime, probes an approved HTTPS endpoint through that runtime, records structured evidence in PostgreSQL, and requires `END_TO_END` success before publication.

| Capability | Status |
|---|---|
| Versioned source registry, typed parsing, and canonical deduplication | Implemented |
| Bounded HTTPS ingestion and reviewable source policy | Implemented |
| Xray runtime configuration and isolated end-to-end probe | Implemented |
| Persistent PostgreSQL history, status, scorecards, and snapshots | Implemented |
| Stable raw/Base64 subscription artifacts | Implemented |
| Scheduled guarded publication | Implemented; disabled until production settings are configured |

## Automation

The guarded subscription workflow targets minutes **07, 22, 37, and 52** of each hour. It permits no overlapping runs, applies a hard timeout and candidate cap, uses one pinned Xray binary, and creates a commit only when the qualified feed changes.

Before enabling it, configure the GitHub secret `KAVEH_DATABASE_URL` and the non-secret variables `KAVEH_PROBE_URL`, `KAVEH_VANTAGE_ID`, and `KAVEH_CANDIDATE_LIMIT`. Set `KAVEH_AUTOMATION_ENABLED=true` only after a manual run succeeds. The legacy `KAVEH_*` names and the internal Python package `kaveh` remain deliberately stable for backwards compatibility.

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
