# Source expansion research — 2026-08-20

## Scope

This assessment evaluates public GitHub subscription sources for possible probationary addition to Pusheen V2Ray. A repository's claim of being Iran-optimized, frequently refreshed, fast, or tested is not treated as validation evidence. A candidate must be fetched through the existing bounded HTTPS client, parsed under an explicit protocol allowlist, and later gain runtime evidence before it can influence public feeds.

## Signals from X and public reports

A dedicated X connector is not configured in the current session. Public X-indexed results contained general reports about the 2026 shutdown and individual configuration claims, but none was accepted as a trusted configuration source. Social posts are discovery signals only, not availability or safety evidence.

Public reporting and technical discussions confirm that Iranian disruptions can include severe, country-wide restrictions. This supports source diversity and protocol diversity, but it does not establish that any specific public proxy endpoint will work from a client network in Iran.

## GitHub candidates

| Candidate | Public endpoint | Discovery characteristics | Proposed treatment |
|---|---|---|---|
| EbraSha multi-protocol | `https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/refs/heads/main/V2Ray-Config-By-EbraSha.txt` | Repository claims 15-minute updates, Persian support, and separate VLESS/VMess/Trojan/SS files. | Fetch and measure; use only bounded protocol-specific endpoints if available. |
| DukeMehdi Lite | `https://raw.githubusercontent.com/DukeMehdi/FreeList-V2ray-Configs/refs/heads/main/Configs/Lite-DukeMehdi-Configs.txt` | Persian README, two-hour refresh claim, and a reduced all-protocol list. | Candidate only after confirming format, entry count, parser success and duplicate ratio. |
| Epodonios aggregate | `https://github.com/Epodonios/v2ray-configs/raw/main/All_Configs_Sub.txt` | Claims frequent updates and protocol variety including TUIC. | Candidate only after confirming actual URI mix and acceptable bounded size. |

## Sources consulted

1. https://github.com/ebrasha/free-v2ray-public-list
2. https://github.com/DukeMehdi/FreeList-V2ray-Configs
3. https://github.com/Epodonios/v2ray-configs
4. https://github.com/net4people/bbs/issues/586
5. https://github.com/net4people/bbs/issues/484


## Measured candidate results

A bounded dry-run ingestion of five candidates established that two VLESS endpoints should not be added under the project resource policy: EbraSha VLESS was approximately 8.24 MB and DukeMehdi VLESS approximately 8.97 MB, both above the registry's 2 MB hard source limit. They were rejected as `SOURCE_TOO_LARGE`; this is intentional resource protection, not a temporary error.

Three protocol-isolated endpoints were within the safe retrieval budget and collectively produced 600 bounded discoveries in a dry run: 544 parsed configurations, 55 deduplicated configurations, and one invalid URI rejection. The candidates are Farid-Karimi's `vless_iran.txt` (approximately 632 KB; 2,687 VLESS URI occurrences), Farid-Karimi's `trojan_iran.txt` (approximately 89 KB; 521 Trojan URI occurrences), and EbraSha's `trojan_configs.txt` (approximately 1.27 MB; 9,211 Trojan URI occurrences). The pipeline limits each source to the first 200 entries, so their total upstream volume cannot consume the validation budget.

The selection remains probationary: source claims about Iran suitability or freshness are discovery metadata only. Later end-to-end results from the existing validator remain the sole basis for a configuration to qualify or appear in any evidence-backed feed.


## Approved probationary additions

Three sources were admitted to the production registry with a trust weight of 0.35 and a protocol-specific allowlist. Farid-Karimi VLESS is bounded to 700,000 bytes and 200 candidates; Farid-Karimi Trojan is bounded to 120,000 bytes and 200 candidates; EbraSha Trojan is bounded to 1,500,000 bytes and 200 candidates. The lower trust setting intentionally prevents source provenance claims from outweighing the pipeline's own evidence, while source-health quarantine remains active for each source.

A full registry dry run after the addition had no source-fetch errors. It discovered 1,390 bounded entries, parsed 1,108, deduplicated 178, and rejected 104 malformed or unsupported inputs. This ingest result establishes parser compatibility and resource safety only. It does not constitute latency, reachability, end-to-end, or Iran-network availability evidence.

The reported X posts and GitHub README claims are not included as validation inputs. No claim is made that a source will work during every Iranian outage; public endpoint accessibility must be established afresh by the scheduled validator from its own vantage point.

