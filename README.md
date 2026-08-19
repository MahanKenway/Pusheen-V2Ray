# Kaveh

> **Measured routes. Clear choices.**

Kaveh is a **quality-first proxy feed pipeline**. It is designed to replace the opaque model of “collect a large list and publish it” with a traceable process: reviewed sources, typed parsing, deterministic validation stages, health history, transparent scoring, and immutable publications.

Kaveh is an independent repository that began from the public Freedom-V2Ray codebase under its MIT license. It preserves the license and keeps `upstream` configured for optional reference; its product direction, architecture, and releases are independent.

## Why Kaveh

A reachable TCP port is not proof that a configuration works for an end user. Kaveh separates parsing, network reachability, runtime construction, end-to-end validation, scoring, and publishing. A future `stable` feed will require successful end-to-end evidence rather than a TCP handshake alone.

| Capability | Kaveh foundation | Status |
|---|---|---|
| Versioned source registry | Reviewable JSON registry outside application code | Implemented |
| Typed protocol parsing | VLESS, VMess, Trojan, and Shadowsocks adapters | Implemented |
| Canonical identity | SHA-256 identity from connection-significant fields | Implemented |
| Safe deduplication | Source and label do not create duplicate identities | Implemented |
| Bounded ingestion | HTTPS-only, timeout, size cap, redirect rejection | Implemented |
| Validation policy | Explicit schema and TCP stages; E2E required for qualification | Implemented foundation |
| Health scoring | Explainable score policy and in-memory history | Implemented foundation |
| Atomic publication | Immutable snapshot artifacts and `latest` pointer | Implemented foundation |
| Runtime end-to-end adapter | Xray/sing-box isolated runtime probe | Planned next milestone |
| Persistent history / dashboard | PostgreSQL, queue, status UI | Planned after runtime validation |

## Architecture

```text
Source Registry → Fetcher → Container Normalizer → Protocol Parsers
    → Canonical Identity & Dedupe → Validation Queue
    → Schema / Reachability / Runtime / End-to-End evidence
    → Health History & Scoring → Immutable Snapshot Publisher
```

The source tree follows a modular-monolith design.

```text
src/kaveh/
├── domain/          # Typed models, business policies, and ports
├── application/     # Ingestion, validation, and publication commands
├── adapters/        # Protocol parsers, containers, and publishers
├── infrastructure/  # HTTP, persistence, probes, storage, observability
├── interfaces/      # Future CLI/API/job endpoints
└── config/          # Loading versioned source registries and policies
```

The dependency rule is deliberate: `domain` does not import HTTP, database, process, or framework code. Infrastructure implements domain ports; interfaces call application commands.

## Quick start

Kaveh has no third-party runtime dependency in the foundation release.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
cp configs/sources/registry.v1.example.json configs/sources/registry.v1.json
# Review the registry, add only approved HTTPS sources, then explicitly enable them.
python -m kaveh ingest --registry configs/sources/registry.v1.json
```

The example registry is disabled by default. Do not add unreviewed URLs or credentials to the repository.

## Quality contract

A candidate progresses through this lifecycle:

```text
DISCOVERED → PARSED → POLICY_ACCEPTED → QUEUED
  → REACHABLE → E2E_VERIFIED → QUALIFIED → PUBLISHED
```

A failed TCP check is not equivalent to a failed end-to-end check, and a successful TCP check is never enough for the future `stable` feed. Every score will record a policy version and its contributing components.

## Security posture

Kaveh treats upstream source content and public issue text as untrusted data. The foundation uses reviewable registries, HTTPS-only source URLs, response limits, safe errors that avoid logging raw URIs, and atomic snapshots that do not replace the last known-good publication with an empty run.

The scheduled pipeline is intentionally not enabled until the isolated runtime validation adapter and persistent history are added. This is preferable to publishing outputs that have not satisfied the Kaveh quality contract.

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests/kaveh -p 'test_*.py'
PYTHONPATH=src python -m kaveh --help
```

## License and attribution

Kaveh is distributed under the repository's [MIT License](LICENSE). The project originated from [Freedom-V2Ray](https://github.com/MahanKenway/Freedom-V2Ray); the original copyright and license notices are retained.
