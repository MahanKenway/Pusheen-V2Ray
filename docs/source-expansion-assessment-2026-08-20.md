# Source Expansion Assessment — 2026-08-20

## Purpose

This assessment evaluates public feeds for expanding the `tcp-reachable-v1` tier without directly publishing untested third-party content. Each source was evaluated for stable raw URLs, bounded size, parser compatibility, and a small read-only Xray probe sample.

| Candidate | Raw feed size | Parser compatibility | Sample Xray result | Decision |
|---|---:|---:|---:|---|
| [ConfigForge VLESS](https://raw.githubusercontent.com/ShatakVPN/ConfigForge-V2Ray/main/configs/vless.txt) | 212,242 bytes, 810 physical lines | 200 / 200 first candidates parsed | 4 / 12 end-to-end passes; 8 failures | **Probationary candidate** for a bounded source entry, with lower trust weight and current validation retained. |
| [ConfigForge light](https://raw.githubusercontent.com/ShatakVPN/ConfigForge-V2Ray/main/configs/light.txt) | 6,293 bytes, 30 lines | 30 / 30 parsed | Not independently probed as a separate set; likely overlaps the larger ConfigForge feed | Optional fallback, not needed if the VLESS source is enrolled. |
| [EbraSha aggregate](https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/V2Ray-Config-By-EbraSha.txt) | 435,216 bytes, 1,649 lines | 0 / 200 first candidates parsed | Not run | **Reject for now**; parser/format compatibility must be solved before use. |
| [ABC Configs README](https://github.com/FreeFolksOn/abc-configs-free-vpn-proxy-list) | Dynamic mixed document | Not a stable, protocol-only feed | Not run | **Reject**; it contains prose and non-supported proxy formats alongside URI strings. |

## Controlled ConfigForge Probe

The probe used the project’s normal parser, schema probe, TCP reachability probe, temporary Xray SOCKS runtime, and the approved HTTPS 204 endpoint. It did not write to Neon, change the public feed, or reveal URI credentials.

> Twelve VLESS records were sampled from ConfigForge’s structured VLESS feed. Four completed the end-to-end probe and eight returned `E2E_PROBE_FAILED`.

This result does not guarantee availability on every user network, but it is sufficient evidence to admit ConfigForge as a **probationary bounded source** rather than publishing its feed without Pusheen’s own checks.

## Recommended Next Step

Add only the structured ConfigForge VLESS feed with a maximum of 200 entries per cycle and a trust weight below the in-house verified source. Run a controlled pipeline after enrollment and measure the incremental count of recent TCP-reachable configs before changing public source policy further.
