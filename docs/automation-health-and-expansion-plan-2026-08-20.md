# Automation Health and Expansion Plan — 2026-08-20

## Current Health

| Check | Result |
|---|---|
| Latest subscription pipeline | Manual run `#14` succeeded in 4m 39s on commit `ab181ac`. |
| Latest scheduled subscription pipeline | Run `#13` succeeded in 1m 43s. |
| Current strict feed | 7 published end-to-end-qualified configs. |
| Current balanced feed | 34 published TCP-reachable configs; Base64 decodes exactly to the raw feed. |
| Latest quality gates | The four code commits covering reachable publishing, CLI, repository selection, and tests all succeeded. |
| Earlier cancellations | Runs `#7` and `#8` were from the pre-budget workflow; later successful runs show the timeout issue is resolved. |

The Actions REST token cannot list repository variables (`HTTP 403`), but a successful scheduled run is direct runtime evidence that the configured automation guard is active.

## Capacity Assessment

The active registry currently provides 3,954 canonical configs. The latest database evidence includes 43 TCP reachability passes and 13 end-to-end passes across historical probe results. The balanced feed contains 34 recently reachable entries because its publication window is deliberately broader than the strict feed.

The current workflow considers up to eight candidates per run and completed in 4m 39s. It has headroom below the 12-minute job timeout, but source additions should first be tested with a controlled run because ingesting more candidates can increase both database writes and runtime.

## Candidate Source Decision

[ConfigForge VLESS](https://raw.githubusercontent.com/ShatakVPN/ConfigForge-V2Ray/main/configs/vless.txt) is the strongest next source candidate. It is 212 KB, provides 810 lines, parsed 200/200 in a local compatibility audit, and yielded 4 successful end-to-end results from a 12-config read-only sample. Its source entry should be probationary: 200 entries per cycle, a lower trust weight than the in-house verified source, and no bypass of Pusheen validation.

## Prioritized Capability Roadmap

| Priority | Capability | Value |
|---|---|---|
| P0 | Automated per-source health score and auto-quarantine | Keeps a noisy source from consuming the candidate budget after persistent parse or probe failures. |
| P0 | Candidate rotation and untested-first selection | Maximizes coverage of the available source pool instead of repeatedly probing the same recent configs. |
| P1 | `fast` and protocol-specific balanced feeds | Lets clients import a smaller ranked feed or only the protocol they support. |
| P1 | Dual probe endpoints and multi-vantage evidence | Reduces false negatives from one validator location or one HTTPS test endpoint. |
| P1 | Generated public status page | Publishes last run time, source health, feed counts, and failure reasons without exposing credentials. |
| P2 | Source provenance and duplicate-overlap report | Shows which sources add unique configs versus duplicate noise. |
| P2 | Privacy-preserving opt-in client feedback | Could rank by user-network experience only with explicit consent and aggregation safeguards. |

## Recommended Next Change

Run one controlled pipeline with ConfigForge VLESS enrolled as a probationary source. Compare the incremental count of unique parsed, TCP-reachable, and end-to-end-successful configs against the current 34-entry balanced feed before enabling it in the scheduled registry.
