# Protocol-extension research — 2026-08-20

## Official Xray findings

- Project X documents Hysteria as its implementation of the underlying QUIC transport for **Hysteria2** and states that it is typically used with `hysteria` outbound/inbound and compatible with the official implementation.
- The documented `hysteriaSettings` uses `version: 2`; relevant documented fields are `auth`, `udpIdleTimeout`, and optional HTTP/3 `masquerade` settings.
- Xray documentation tracks the latest release and cautions that fields can differ by installed version. The project pins Xray v26.3.27, so any Hysteria2 support must be confirmed with an actual `xray run -test` configuration before publish.
- The official documentation currently retrieved did **not** document TUIC as an Xray outbound. TUIC therefore requires an alternate runtime adapter (for example, a separately pinned compatible runtime) or must remain unsupported; it must not be represented as Xray-validated without evidence.

## Feed-ranking implication

- TCP probe latency is currently source-vantage-specific. It is suitable for ordering the broad/primary feed when paired with evidence freshness, but must not be advertised as client-region latency or end-to-end throughput.
- The strict feed continues to require successful HTTPS transit through its temporary Xray runtime. Hysteria2 can enter that tier only after parser, runtime builder, and real probe coverage are all implemented and passing.

## Sources

1. https://xtls.github.io/en/config/transports/hysteria.html
2. https://xtls.github.io/en/config/


## URI and runtime findings

### Hysteria 2

- Official URI schemes are `hysteria2` and `hy2`.
- The URI carries authentication in userinfo, an address with optional port (default 443), and documented query parameters such as `obfs`, `obfs-password`, `sni`, `insecure`, `pinSHA256`, and `ech`.
- The official Xray transport documentation confirms Hysteria version 2 and documents `auth`, `udpIdleTimeout`, and optional masquerade settings.
- Implementation policy: accept documented standard URI fields; reject unsupported realm and multi-port forms until a dedicated canonical representation and runtime test exist.

### TUIC

- TUIC is an implementation-agnostic QUIC proxy specification, currently version `0x05` according to the official TUIC repository.
- The official Xray source tree has a `proxy/hysteria` implementation but no `proxy/tuic` implementation. It is therefore incorrect to send TUIC through the current Xray adapter.
- Implementation policy: add TUIC only behind a separately pinned, tested runtime adapter compatible with v5 (for example, an independently maintained client runtime), with an explicit probe-evidence label distinct from Xray.

## Additional sources

3. https://v2.hysteria.network/docs/developers/URI-Scheme/
4. https://github.com/EAimTY/tuic
5. https://github.com/XTLS/Xray-core/tree/main/proxy


### Official Xray Hysteria outbound structure

- The official Hysteria outbound page specifies `protocol: "hysteria"` and `settings` containing exactly the documented required fields `version: 2`, `address`, and `port`.
- The same documentation explains that Hysteria proxy protocol and QUIC transport configuration are separated; Hysteria2 authentication belongs in the transport `hysteriaSettings` object.
- Implementation policy: generate `protocol: "hysteria"`, `settings: {version: 2, address, port}`, and `streamSettings: {network: "hysteria", security: "tls", hysteriaSettings: {version: 2, auth}}` with only documented URI fields mapped after an Xray `run -test` integration test.

6. https://xtls.github.io/en/config/outbounds/hysteria.html


### TUIC runtime candidate: sing-box

- sing-box is an actively maintained, high-adoption runtime candidate (37k+ GitHub stars at the time of assessment) that documents a TUIC outbound with required `server`, `server_port`, `uuid`, and TLS configuration. `password` is optional according to the documented outbound fields.
- Documented selectable transport properties include `congestion_control` (`cubic`, `new_reno`, or `bbr`), `udp_relay_mode`, `udp_over_stream`, `zero_rtt_handshake`, and `heartbeat`.
- The adapter boundary is explicit: use Xray only for Xray-supported protocols such as Hysteria2; use a separately pinned sing-box runtime for TUIC. A config is not eligible for strict publication until its own runtime completes the same local SOCKS HTTPS probe.

7. https://sing-box.sagernet.org/configuration/outbound/tuic/
8. https://github.com/SagerNet/sing-box


## Runtime validation

The TUIC schema described above was validated locally with the official `sing-box` v1.13.19 Linux amd64 release using `sing-box check`. This verifies the isolated SOCKS-inbound, TUIC-outbound and routing shape required for a future adapter; it does not demonstrate connectivity to a real TUIC server and therefore is not publish evidence.


## Hysteria 2 source assessment

Two public repositories were reviewed for Hysteria 2 availability. `MatinGhanbari/v2ray-configs` publishes a dedicated `subscriptions/filtered/subs/hysteria2.txt` endpoint and claims frequent refreshes; it is the strongest probationary candidate because the feed is protocol-specific. `ebrasha/free-v2ray-public-list` claims broad multi-protocol coverage but exposes only all-protocol lists in the reviewed README, so it offers less isolation and should not be added until a dedicated Hysteria 2 endpoint is identified.

Candidate URL for a bounded probationary source:

`https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/filtered/subs/hysteria2.txt`

The source must still pass the pipeline's HTTPS retrieval, URI parse, TCP reachability and, where compatible, Xray end-to-end validation. README claims about refresh rate, health, or uptime are not treated as validation evidence.

Sources: https://github.com/MatinGhanbari/v2ray-configs and https://github.com/ebrasha/free-v2ray-public-list


## TUIC ingestion boundary

The official TUIC v5 specification defines the protocol framing, UUID/password authentication material and QUIC behavior, but it does not define a subscription or share-URI scheme. Therefore a generic `tuic://` parser would be a vendor-specific assumption, not a protocol-standard parser. The safe ingestion contract is a reviewed JSON profile with the documented sing-box TUIC outbound fields, or a separately versioned source adapter for an explicitly documented vendor format.

Source: https://github.com/EAimTY/tuic/blob/dev/SPEC.md


## NaiveProxy and TUIC v5 extension assessment

NaiveProxy is available as a sing-box outbound since 1.13.0. The documented outbound requires a server address/port and supports username/password, optional QUIC, QUIC congestion control and a narrow TLS surface. On Linux, the official non-suffixed sing-box build includes `libcronet.so`, which must remain beside the executable; this makes the pinned official archive the appropriate runtime distribution for GitHub Actions. NaiveProxy documentation explicitly warns that self-signed certificates alter traffic behavior and should not be used in production.

TUIC v5 runtime fields documented by sing-box include `uuid`, `password`, `congestion_control`, `udp_relay_mode`, `udp_over_stream`, `zero_rtt_handshake`, `heartbeat` and `network`. The existing adapter currently uses the minimal portable subset. A structured JSON profile is the preferred ingestion form because the TUIC protocol specification does not define a generic share URI.

Sources: https://github.com/klzgrad/naiveproxy ; https://sing-box.sagernet.org/configuration/outbound/naive/ ; https://sing-box.sagernet.org/configuration/outbound/tuic/


## Production extension decision

The pinned GitHub Actions runtime was checked locally: `sing-box 1.13.19` Linux amd64 reports the `with_naive_outbound` build tag and ships `libcronet.so` beside the executable. Both a Naive outbound and a detailed TUIC v5 outbound pass `sing-box check` with that exact binary. Therefore, both protocols can use the same disposable SOCKS-plus-approved-HTTPS end-to-end evidence path as existing TUIC support.

A strict `tuic://UUID:PASSWORD@HOST:PORT?...` parser is enabled for the widely implemented v5 URI convention. It requires a UUID and password, retains documented runtime controls such as congestion control, UDP relay mode, 0-RTT, heartbeat, SNI and ALPN, and rejects `insecure` TLS bypasses. The TUIC wire protocol remains the normative compatibility boundary; the share URI is explicitly treated as a de-facto interoperability contract, not a claim of an official standard. Surge independently documents that TUIC v5 uses a UUID/password pair and differs from v4's token authentication.

NaiveProxy does not have a safely distinguishable public share scheme: its documented client configuration uses ordinary `https://` or `quic://` proxy endpoints, which would collide with non-Naive web URLs in mixed feeds. It is therefore supported through a reviewed `json_profiles` source format instead. The ingestion contract requires a versioned JSON container, explicit `naive` protocol, username/password, server/port and verified TLS; insecure TLS profiles are rejected. Internal JSON profiles are never serialized to public feeds, so the existing `strict.txt` and high-coverage URI feeds cannot be contaminated by a nonportable configuration format. A future public Naive feed requires a portable client serializer agreed with the consuming clients.

No new public probationary source was registered solely to create count: the currently reviewed aggregator contained zero `tuic://` entries at the time of inspection, and an upstream source should only be added after it provides parseable candidates. This preserves the pipeline rule that no protocol is published without end-to-end evidence.

Additional references: https://manual.nssurge.com/policies/tuic.html ; https://github.com/tuic-protocol/tuic

