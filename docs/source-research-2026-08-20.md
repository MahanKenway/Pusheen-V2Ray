# Source research — 2026-08-20

## Current registry baseline

- Existing source: `https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt`
- Latest Pusheen V2Ray validation: 4,087 discovered; 2,089 parsed; 12 candidates tested end-to-end; 0 qualified for publication.
- Registry currently permits VLESS, VMess, Trojan, and Shadowsocks, with a 2 MB fetch cap.

## Candidate sources evaluated

| Candidate | Raw feed considered | Evidence reviewed | Decision |
| --- | --- | --- | --- |
| 0xRadikal/Free-v2ray-Configs | `https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/verified/configs.txt` | README states the verified tier requires a real proxied HTTP request in all three rounds. Fresh `health.json` is timestamped `2026-08-19T22:19:44Z` and reports 15 healthy upstreams out of 21 total. The verified feed was non-empty, plain URI text, and approximately 343 KB at retrieval. | Add as a high-trust, bounded source, while retaining Pusheen's own independent Xray validation. |
| Delta-Kronecker/V2ray-Config | `https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/refs/heads/main/config/protocols/vless.txt` | Plain VLESS feed; repository claims TCP-passed lists but this protocol feed is not independently evidenced by a fresh per-source health artifact. | Do not add in this change; retain as a future candidate after separate controlled tests. |
| ebrasha/free-v2ray-public-list | `https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/vless_configs.txt` | Feed retrieved at approximately 5 MB, above Pusheen's 2 MB source cap. First records included structural anomalies such as loopback endpoints and zero UUIDs. | Reject; violates size budget and creates high rejection load. |
| Epodonios/v2ray-configs | `https://github.com/Epodonios/v2ray-configs/raw/main/All_Configs_Sub.txt` | Public aggregated all-protocol feed advertised as updated frequently. The 0xRadikal health report listed it as `unknown` in its latest run. | Do not add now; lacks current independent quality evidence. |
| barry-far/V2ray-config | protocol-specific raw files | Public feed with clearly documented protocol split but it is already represented in 0xRadikal's current upstream health report. | Do not add directly; avoid likely upstream duplication. |

## Source evidence URLs

1. https://github.com/0xRadikal/Free-v2ray-Configs
2. https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/verified/configs.txt
3. https://raw.githubusercontent.com/0xRadikal/Free-v2ray-Configs/main/health.json
4. https://github.com/Delta-Kronecker/V2ray-Config
5. https://github.com/ebrasha/free-v2ray-public-list
6. https://github.com/Epodonios/v2ray-configs
7. https://github.com/barry-far/V2ray-config

## Implementation principle

Add only the 0xRadikal `verified/configs.txt` feed with a higher trust weight and a conservative fetch cap. It should not be trusted for publication by itself: every candidate must still pass Pusheen V2Ray's own parser, deduplication, Xray end-to-end probe, and qualification policy.
