# Kaveh PostgreSQL and Xray Runbook

## Scope

This runbook enables persistent Kaveh validation. It is designed for a controlled environment where the database, binary path, probe endpoint, source registry, and outbound network policy are explicitly managed.

## Required configuration

Create a protected `.env.local` from `.env.example`. The database URL and any credentials belong in a secret store or a file readable only by the Kaveh service account. Do not commit the file.

| Variable | Purpose | Requirement |
|---|---|---|
| `KAVEH_DATABASE_URL` | PostgreSQL connection URI | Required for migrations and persistent validation. |
| `XRAY_BINARY` | Absolute path to an audited Xray binary | Required for end-to-end probes. |
| `KAVEH_PROBE_URL` | Approved HTTPS endpoint returning HTTP 204 | Required; do not use a URL that you do not control or approve. |
| `KAVEH_VANTAGE_ID` | Label for the network perspective that runs probes | Required in production; it makes results interpretable. |
| `XRAY_WORK_ROOT` | Temporary directory for one-use Xray workspaces | Must be writable only by the service account. |

## Database initialization

```bash
set -a && . ./.env.local && set +a
python -m kaveh migrate
```

The first migration creates tables for canonical configs, source observations, runs, append-only probe results, materialized current status, scorecards, and immutable publication snapshots. PostgreSQL backups must be treated as sensitive because `configs.raw_uri` contains the material necessary to build feeds.

## Binary installation

Install a version-pinned Xray binary outside of the repository or in a protected tools directory. Verify the release checksum before enabling it. Kaveh deliberately accepts an existing `XRAY_BINARY`; it never downloads a new binary during a scheduled validation run.

## One controlled run

```bash
set -a && . ./.env.local && set +a
python -m kaveh validate \
  --registry configs/sources/registry.v1.json \
  --limit 25 \
  --publish-root /var/lib/kaveh/public
```

Each selected candidate is parsed, recorded, checked structurally, tested for reachability, rendered into a temporary Xray configuration, and probed through a temporary local SOCKS listener. The process is terminated and the temporary configuration is removed regardless of outcome. Only an HTTP 204 response received through that listener produces `END_TO_END=pass`.

## Safety and failure behavior

Kaveh records safe failure codes such as `XRAY_STARTUP_FAILED`, `E2E_PROBE_FAILED`, and `PROBE_STATUS_INVALID`. It must not write raw URI values into application logs, status pages, metrics labels, or issue responses. A run with no qualified candidates does not replace the `latest` snapshot.

The initial validation command has an explicit `--limit`. Keep the limit small while onboarding sources and increasing the runtime budget; scale only after source quality, host capacity, and the probe endpoint’s allowable traffic are known.
