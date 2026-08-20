# Iran outage resilience research — 2026-08-20

## Scope and limitation

This note records network-resilience facts relevant to Pusheen V2Ray's feed delivery and evidence model. It does not claim that any protocol, provider, hostname, or configuration can remain available during a total international Internet blackout. If a user has no path to the global Internet, an off-country subscription endpoint cannot deliver a fresh configuration. A sound design therefore separates **delivery resilience** from **tunnel reachability**, exposes evidence origin, and retains a previously successful feed rather than replacing it with an empty or unverified one.

## Measured disruption patterns

The OONI/IODA multi-stakeholder report on 2022 disruptions documented ISP- and network-specific effects: recurring mobile outages, regional outages, application blocking, encrypted-DNS interference, and a near-zero drop in QUIC/HTTP/3 traffic that is consistent with UDP/443 being blocked. Fixed-line access sometimes differed from mobile access. This means a single test result cannot be generalized across Iranian networks.

The 2026 public-data study describes several distinct patterns: BGP withdrawal in earlier blackouts; layered DNS, HTTP, TLS/SNI, and UDP interference; geographical and ISP-level variation; and a 2025 style of filtering that preserved the appearance of connectivity at some layers while substantially restricting international services. It explicitly notes that single-source monitoring is insufficient and that in-country measurement coverage is limited.

## Engineering consequences for Pusheen

| Finding | Safe product response |
|---|---|
| GitHub content may be inaccessible even when some global paths remain | Publish an independent delivery origin which serves last-known-good artifacts and does not require the client to contact GitHub. |
| HTTP/3, QUIC, and UDP may be selectively or broadly disrupted | Do not prioritize QUIC-only configs during an outage based on a generic latency score; preserve TCP/TLS transport diversity in the fallback feed. |
| Mobile, fixed-line, province, ISP, IPv4, and IPv6 paths can differ | Track evidence by vantage identifier and surface it separately. Do not label a config as Iran-working without an Iran-located or explicitly reported vantage. |
| Users can lose access to app stores and update channels | Publish simple, stable, copyable subscription URLs and failover-ready local profiles before an outage; do not rely on on-demand application installation during an event. |
| A total international blackout prevents foreign hosting from refreshing | Keep cached last-known-good feeds, publish integrity metadata, and distinguish stale-but-previously-evidenced content from current evidence. |

## Methods observed in literature

The research describes several general categories used for censorship resilience: conventional encrypted proxy tunnels; systems built around traffic obfuscation and dynamic transport selection; volunteer/ephemeral proxy systems; and managed multi-protocol systems. Their effectiveness varies by time, network, and censorship technique. The 2022 report in particular contradicts the assumption that a newer UDP/QUIC transport is always advantageous: its data showed QUIC traffic falling near zero during the event.

## Architecture recommendation

1. Maintain the current GitHub feed as an audit and source-control origin.
2. Add an independent public delivery edge that proxies or serves a cached, last-known-good artifact with a short, explicit cache policy and content hash.
3. Make the resilient feed a TCP-evidence fallback with anti-concentration selection; it must remain labelled as TCP-reachable only.
4. Add an evidence-receipt manifest and reserve multi-vantage labels for independently operated probes. This requires a trusted in-country or regional observer before any Iran-specific claim.
5. Generate client failover profiles only after their output schemas are checked by the real runtime binaries.

## Sources

1. OONI, IODA, M-Lab, Cloudflare, Kentik, Censored Planet, ISOC, and Article 19, *Technical multi-stakeholder report on Internet shutdowns: The case of Iran amid autumn 2022 protests*: https://ooni.org/post/2022-iran-technical-multistakeholder-report/
2. *Iran’s January 2026 Internet Shutdown: Public Data, Censorship Methods, and Circumvention Techniques*: https://arxiv.org/html/2603.28753v1
3. IODA report mirror: https://ioda.inetintel.cc.gatech.edu/reports/technical-multi-stakeholder-report-on-internet-shutdowns-the-case-of-iran-amid-autumn-2022-protests/

## Delivery architecture decision

The connected Cloudflare account has an existing Workers subdomain (`mahankenway.workers.dev`) but no active custom DNS zone. The deployable independent public origin is therefore a Worker URL under that subdomain. It is a delivery alternative to raw GitHub rather than a claim of national-shutdown resistance.

The recommended first implementation is a narrow allowlisted Worker gateway. It receives an approved artifact path, reads only the matching public raw file from the Pusheen GitHub repository from the Cloudflare edge, checks that the upstream response is non-empty and of the expected class, and caches successful replies for a short period. The Worker exposes integrity and source headers and never handles private credentials. This removes the client-to-GitHub dependency while retaining GitHub as the source-control and publication origin. A custom-domain route can be added later only when an active user-owned zone exists.

A Worker route does not solve a true international disconnection, an account-level Cloudflare block, or a user device without any network route. The client must retain the last usable subscription and failover profile before an outage. Multi-vantage validation must remain unclaimed until independently operated probes are available; the existing `github-actions` vantage is only an external validator origin.

## Delivery validation

On 2026-08-20 the `pusheen-feed-gateway` Worker was deployed on the existing `mahankenway.workers.dev` subdomain and workers.dev access was explicitly enabled for that script. Its public health endpoint returned the restricted artifact allowlist. The independent endpoint also returned a non-empty `resilient.txt` feed from the Cloudflare edge. This verifies a client-to-Cloudflare delivery path that does not require a direct client connection to GitHub; it does not verify availability from Iranian networks or during a complete international shutdown.
