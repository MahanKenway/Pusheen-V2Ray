# Pusheen V2Ray

<p align="center">
  <img src="assets/brand/pusheen-v2ray-header.png" alt="Pusheen V2Ray — a lazy cat with fast, resilient routes" width="900">
</p>

<p align="center">
  <strong>A lazy cat, with fast and resilient routes.</strong><br>
  Public V2Ray and sing-box feeds for simpler use on unstable networks.
</p>

<p align="center">
  <a href="README.md">نسخهٔ فارسی</a> ·
  <a href="https://github.com/MahanKenway/Pusheen-V2Ray/actions">Automation status</a> ·
  <a href="https://pusheen-feed-gateway.mahankenway.workers.dev/status.json">Live feed status</a> ·
  <a href="https://pusheen-feed-gateway.mahankenway.workers.dev/dashboard">SLO dashboard</a>
</p>

> Pusheen V2Ray is a free public project for publishing reviewed feeds. No feed guarantees connectivity on every network or at every time; test several entries in your client before relying on one.

## Which link should I use?

For **severe disruption and lower correlated-failure risk**, start with `outage.txt`. It is smaller, but selected with more diversity across sources, protocols, and transports. If you need a wider fallback, use `resilient.txt`. `all.txt` and `balanced.txt` contain more entries, but they are broader and are not specifically optimized for severe disruption.

| Priority | Recommended feed | Current count | Best for | Stable Gateway link |
|---:|---|---:|---|---|
| 1 | Outage-diverse | 33 | First choice during severe disruption; lower concentration of similar paths | [outage.txt](https://pusheen-feed-gateway.mahankenway.workers.dev/outage.txt) |
| 2 | Resilient | 53 | A wider set with source, protocol, and endpoint diversity | [resilient.txt](https://pusheen-feed-gateway.mahankenway.workers.dev/resilient.txt) |
| 3 | Balanced | 250 | More entries and more manual choice | [balanced.txt](https://pusheen-feed-gateway.mahankenway.workers.dev/balanced.txt) |
| 4 | Primary | 250 | Broadest public coverage | [all.txt](https://pusheen-feed-gateway.mahankenway.workers.dev/all.txt) |
| 5 | Strict | 7 | Stronger evidence; smaller list | [strict.txt](https://pusheen-feed-gateway.mahankenway.workers.dev/strict.txt) |

### GitHub Raw alternatives

If the Gateway is unavailable, use the Raw alternatives: [outage](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/outage.txt), [resilient](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/resilient.txt), [balanced](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/reachable.txt), [all](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all.txt), and [strict](https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/strict.txt).

## Sing-box and Hiddify links

For a client that accepts a **full sing-box profile**, use [outage-singbox.json](https://pusheen-feed-gateway.mahankenway.workers.dev/outage-singbox.json). It is published with URLTest and local fallback behavior. In Hiddify, if your version does not accept a full JSON profile, use [outage.txt](https://pusheen-feed-gateway.mahankenway.workers.dev/outage.txt) as a normal subscription; it is the most compatible path.

## Status and update timing

<p align="center">
  <a href="https://github.com/MahanKenway/Pusheen-V2Ray/actions/workflows/subscription-pipeline.yml"><img src="https://github.com/MahanKenway/Pusheen-V2Ray/actions/workflows/subscription-pipeline.yml/badge.svg" alt="Subscription pipeline status"></a>
  <a href="https://github.com/MahanKenway/Pusheen-V2Ray/actions/workflows/beta-compatibility.yml"><img src="https://github.com/MahanKenway/Pusheen-V2Ray/actions/workflows/beta-compatibility.yml/badge.svg" alt="Beta compatibility status"></a>
</p>

**🚀 Publication schedule:** the pipeline runs at minutes **07, 22, 37, and 52 of every hour**, giving a nominal maximum interval of 15 minutes between publication windows. Actual publication depends on ingestion and validation results. For the current snapshot, feed counts, and evidence freshness, see [status.json](https://pusheen-feed-gateway.mahankenway.workers.dev/status.json).

| Status | Link |
|---|---|
| Current public status | [status.json](https://pusheen-feed-gateway.mahankenway.workers.dev/status.json) |
| Release pointer | [current-release.json](https://pusheen-feed-gateway.mahankenway.workers.dev/current-release.json) |
| Versioned manifest pointer | [current release](https://pusheen-feed-gateway.mahankenway.workers.dev/current-release.json) |
| Pipeline runs | [GitHub Actions](https://github.com/MahanKenway/Pusheen-V2Ray/actions) |
| sing-box beta checks | [Beta Compatibility](https://github.com/MahanKenway/Pusheen-V2Ray/actions/workflows/beta-compatibility.yml) |

## Client setup guides

The guides below are short and visual. Copy a link from the table above and add it as a subscription in your client. If one feed does not connect quickly, update it and test another entry with lower delay.

### Hiddify — recommended general client

In Hiddify, open **Home → + → Add manually**, paste `outage.txt` or `resilient.txt` into the URL field, save, and run Update and the delay test. Hiddify supports V2Ray subscriptions and sing-box profiles; import [outage-singbox.json](https://pusheen-feed-gateway.mahankenway.workers.dev/outage-singbox.json) as a full profile only if your version supports JSON profile import. See the [official Hiddify App documentation](https://hiddify.com/app/How-to-use-Hiddify-app/).

<p align="center"><img src="docs/images/hiddify-import.svg" alt="Visual guide for adding a Pusheen feed to Hiddify" width="900"></p>

### v2rayNG — Android

Open subscription groups, create a new group, paste `outage.txt` or `resilient.txt`, update the group, and select a node. See the official [v2rayNG repository](https://github.com/2dust/v2rayNG) for the client and release information.

<p align="center"><img src="docs/images/v2rayng-import.svg" alt="Visual guide for adding a Pusheen feed to v2rayNG" width="900"></p>

### NekoBox — Android

Open Groups, create a new group, add the feed URL, and update it. Start with `outage.txt` during severe disruption. See the [NekoBox tutorial](https://hiddify.com/manager/client-software-on-android/Tutorial-for-Nekobox-app/) and the [NekoBoxForAndroid repository](https://github.com/MatsuriDayo/NekoBoxForAndroid).

<p align="center"><img src="docs/images/nekobox-import.svg" alt="Visual guide for adding a Pusheen feed to NekoBox" width="900"></p>

### sing-box — full profile

For a client that accepts a full sing-box profile, download [outage-singbox.json](https://pusheen-feed-gateway.mahankenway.workers.dev/outage-singbox.json), use Import/Open file, and run URLTest. See the official [sing-box documentation](https://sing-box.sagernet.org/).

<p align="center"><img src="docs/images/singbox-import.svg" alt="Visual guide for importing the full sing-box profile" width="900"></p>

## Connection notes

During severe disruption, do not treat one feed as a guarantee. Try `outage.txt`, then `resilient.txt`, and finally `balanced.txt`. After each update, test several entries; low delay alone does not guarantee filtering circumvention or long-term stability.

Pusheen feeds are based on time-bound evidence from a specific validation vantage. A larger list does not mean every entry will work for every user. During a complete network shutdown, no public link can guarantee access.

## Project links

| Item | Link |
|---|---|
| Main repository | [MahanKenway/Pusheen-V2Ray](https://github.com/MahanKenway/Pusheen-V2Ray) |
| Issues and reports | [Issues](https://github.com/MahanKenway/Pusheen-V2Ray/issues) |
| Versioned releases | [Releases](https://github.com/MahanKenway/Pusheen-V2Ray/releases) |
| Workflow history | [Actions](https://github.com/MahanKenway/Pusheen-V2Ray/actions) |
| Gateway health | [health](https://pusheen-feed-gateway.mahankenway.workers.dev/health) |
| Public feed status | [status.json](https://pusheen-feed-gateway.mahankenway.workers.dev/status.json) |
| Delivery and SLO dashboard | [dashboard](https://pusheen-feed-gateway.mahankenway.workers.dev/dashboard) |
| Sampled delivery data | [delivery-status.v1.json](https://pusheen-feed-gateway.mahankenway.workers.dev/delivery-status.v1.json) |
| Public SLO and alert state | [slo-status.v1.json](https://pusheen-feed-gateway.mahankenway.workers.dev/slo-status.v1.json) |

## License and attribution

The project is released under the [MIT License](LICENSE). The header image was supplied by the project owner and is used for this repository’s visual identity. Pusheen names and artwork may belong to their respective rights holders; this repository does not claim ownership of them.
