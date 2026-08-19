"""Bounded TCP reachability probe.

A successful result means only that a TCP endpoint accepted a connection; it is
not treated as end-to-end qualification evidence.
"""

from __future__ import annotations

import socket
import time

from kaveh.domain.models import CanonicalConfig, ProbeResult, ProbeStage


class TcpReachabilityProbe:
    def __init__(self, timeout_seconds: float = 2.0) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, config: CanonicalConfig) -> ProbeResult:
        if not config.identity_hash:
            return ProbeResult.failed("unknown", ProbeStage.REACHABILITY, "MISSING_IDENTITY")
        started = time.perf_counter()
        try:
            addresses = socket.getaddrinfo(config.host, config.port, type=socket.SOCK_STREAM)
        except socket.gaierror:
            return ProbeResult.failed(config.identity_hash, ProbeStage.REACHABILITY, "DNS_FAILURE")
        for family, socktype, proto, _, sockaddr in addresses:
            try:
                with socket.socket(family, socktype, proto) as sock:
                    sock.settimeout(self.timeout_seconds)
                    sock.connect(sockaddr)
                return ProbeResult.passed(
                    config.identity_hash,
                    ProbeStage.REACHABILITY,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
            except (socket.timeout, OSError):
                continue
        return ProbeResult.failed(config.identity_hash, ProbeStage.REACHABILITY, "TCP_TIMEOUT")
