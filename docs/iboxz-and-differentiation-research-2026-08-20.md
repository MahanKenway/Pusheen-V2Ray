# iboxz source assessment and product differentiation research — 2026-08-20

## iboxz/free-v2ray-collector

Repository metadata indicates an active collector with a recent push on 2026-08-20, a declared two-hour update cadence, and protocol-specific public outputs for VLESS, VMess, Trojan, Shadowsocks, Reality, and a combined `mix` feed. The selected combined endpoint is:

```text
https://raw.githubusercontent.com/iboxz/free-v2ray-collector/main/main/mix.txt
```

At assessment time it was 91,141 bytes and contained 402 non-empty lines. It had 312 VLESS, 27 Trojan, 14 VMess, and 35 Shadowsocks URI lines. It also contained 14 non-URI JSON-fragment lines. A bounded trial ingest of the first 200 entries reported 153 parsed, 10 duplicates, and 37 rejections (35 malformed Shadowsocks entries and two invalid URI entries), with no fetch or source errors.

The source remains eligible for probationary use because the valid portion is substantial, the input is bounded, and the pipeline rejects malformed lines before persistence. It should carry a low trust weight and an explicit protocol allowlist. A source README claim of being tested or secure is not validation evidence.

## Comparison findings

| Project | Documented strengths | Gap/opportunity for Pusheen |
|---|---|---|
| iboxz/free-v2ray-collector | Two-hour collection, per-protocol and combined feeds, web access. | Pusheen adds source-health history, parse policy, runtime validation, and evidence-based publication instead of trusting upstream claims. |
| Shayanthn/V2ray-Tester-Pro | Local GUI, ping/speed scans, GeoIP, basic security validator and export. | It is a local tool rather than a continuously published, provenance-aware feed. |
| 0xRadikal/Free-v2ray-Configs | Explicit multi-round HTTP evidence, median-delay tiers, config formats, cascade report, stable IDs, source health. | Strong benchmark for transparency and client exports; Pusheen should avoid duplicating generic tiers without adding an outage-specific benefit. |
| Au1rxx/free-vpn-subscriptions | TCP/TLS/runtime/HTTP probes, two rounds, real HTTP latency, country and client-format shards. | Strong benchmark for end-to-end testing; its documented probe vantage is still a single infrastructure perspective. |

## Differentiators worth prioritizing

1. **Outage-resilient diversity feed:** select only configs with existing reachability evidence, then cap common-mode concentration by protocol, port, source lineage, and transport family. This treats a mass block as a correlated-failure problem instead of simply returning the lowest latency entries.
2. **Evidence receipt manifest:** publish a credential-free record for every selected entry: stable hash, protocol/transport, source lineage count, evidence stage, last observed time, latency, stability score, and exclusion reason where applicable. It lets users audit why a config appeared without leaking URI credentials.
3. **Multi-vantage evidence model:** record independent observer identities, expose a per-vantage matrix, and separately rank local/regional evidence when a volunteer or deployed regional probe is available. This is the highest-value Iran-specific differentiator but requires trusted additional probe deployment; it must not falsely infer Iran availability from GitHub Actions.
4. **Failover-ready client profiles:** generate validated sing-box and Clash/Mihomo profiles that combine a small stable seed set with client-side URL testing and automatic fallback. This improves continuity after publication but needs converter and binary validation work.

Sources: https://github.com/iboxz/free-v2ray-collector ; https://github.com/Shayanthn/V2ray-Tester-Pro ; https://github.com/0xRadikal/Free-v2ray-Configs ; https://github.com/Au1rxx/free-vpn-subscriptions

The per-protocol VLESS endpoint was assessed as the production candidate instead of the mixed endpoint:

```text
https://raw.githubusercontent.com/iboxz/free-v2ray-collector/main/main/vless.txt
```

With the same 200-entry bound, it produced 184 parsed configurations, 13 duplicates, and only three invalid-URI rejections, with no source errors. This is materially cleaner than the mixed endpoint and preserves protocol isolation. The Trojan and VMess endpoints may be separately assessed later; the Shadowsocks output is not selected because the combined test indicated a high malformed-entry share.

