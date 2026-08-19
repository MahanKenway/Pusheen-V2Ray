# Kaveh Subscription Automation

## What the workflow does

`subscription-pipeline.yml` runs at minutes **07, 22, 37, and 52** of each hour. It fetches only enabled sources in `configs/sources/registry.v1.json`, validates a bounded number of candidates through isolated Xray processes, writes PostgreSQL evidence, builds the `subscriptions/` files only if the qualified feed changed, and commits only those changed files.

The workflow uses a single concurrency group and waits for any active run to finish. It has a 14-minute hard timeout, an explicit candidate cap, a cache for one pinned and checksum-verified Xray binary, and no loop or retry pattern intended to evade GitHub policies. Scheduled GitHub Actions are best effort, so this cadence is a target rather than an availability guarantee.

## Required repository configuration

The job remains inactive until the repository variable `KAVEH_AUTOMATION_ENABLED` is exactly `true`. Before setting it, create the following values.

| Type | Name | Value |
|---|---|---|
| Secret | `KAVEH_DATABASE_URL` | PostgreSQL URI reachable from the GitHub-hosted runner. |
| Variable | `KAVEH_PROBE_URL` | An approved HTTPS URL that responds with HTTP 204. |
| Variable | `KAVEH_VANTAGE_ID` | A descriptive label such as `github-runner-us-east`. |
| Variable | `KAVEH_CANDIDATE_LIMIT` | Start with `12`; raise only after observing stable run duration and source quality. |
| Variable | `KAVEH_AUTOMATION_ENABLED` | Set to `true` only after the items above are configured. |

A database bound only to `127.0.0.1` cannot be reached by GitHub-hosted runners. Use a managed PostgreSQL instance or a deployment environment reachable through authenticated TLS. Never place the connection URI in the repository, workflow file, or source registry.

## Subscription output

The workflow updates these stable paths only after a qualified feed changes:

```text
subscriptions/all.txt
subscriptions/all.base64
subscriptions/<protocol>.txt
subscriptions/<protocol>.base64
subscriptions/manifest.v1.json
```

The repository is currently private. Raw GitHub URLs work as ordinary client subscriptions only after the repository becomes public; otherwise they require authorization and should not be shared as public feeds.

## Operational recommendation

Fifteen minutes is the fastest initial cadence recommended for this bounded GitHub-hosted validator. It is materially faster than a two-hour update cycle while avoiding zero-minute scheduler contention and allowing a bounded Xray probe batch to complete. If the product later needs a strict sub-five-minute SLA, run the same `kaveh validate` command on a persistent service with its own PostgreSQL network path rather than increasing GitHub Action frequency.
