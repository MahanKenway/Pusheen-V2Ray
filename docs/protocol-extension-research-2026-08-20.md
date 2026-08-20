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

