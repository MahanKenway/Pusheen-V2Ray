"""Bounded TCP reachability probe.

A successful result means only that a TCP endpoint accepted a connection; it is
not treated as end-to-end qualification evidence.
"""

from __future__ import annotations

import socket
import time
from queue import Empty, Queue
from threading import Thread

from kaveh.domain.models import CanonicalConfig, ProbeResult, ProbeStage


class TcpReachabilityProbe:
    def __init__(self, timeout_seconds: float = 2.0) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, config: CanonicalConfig) -> ProbeResult:
        if not config.identity_hash:
            return ProbeResult.failed("unknown", ProbeStage.REACHABILITY, "MISSING_IDENTITY")
        started = time.perf_counter()
        try:
            addresses = _resolve_addresses(
                config.host, config.port, timeout_seconds=self.timeout_seconds
            )
        except socket.gaierror:
            return ProbeResult.failed(config.identity_hash, ProbeStage.REACHABILITY, "DNS_FAILURE")
        if addresses is None:
            return ProbeResult.failed(config.identity_hash, ProbeStage.REACHABILITY, "DNS_TIMEOUT")
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


def _resolve_addresses(host: str, port: int, timeout_seconds: float):  # type: ignore[no-untyped-def]
    """Resolve in a daemon thread so a stalled system resolver cannot exhaust CI.

    DNS success remains necessary before any TCP evidence is recorded. A timeout
    is represented explicitly rather than being mistaken for a failed connection.
    """

    result_queue: Queue[tuple[str, object]] = Queue(maxsize=1)

    def resolve() -> None:
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as error:
            result_queue.put(("error", error))
            return
        result_queue.put(("ok", addresses))

    resolver = Thread(target=resolve, name="kaveh-tcp-dns", daemon=True)
    resolver.start()
    try:
        outcome, value = result_queue.get(timeout=timeout_seconds)
    except Empty:
        return None
    if outcome == "error":
        raise value  # type: ignore[misc]
    return value
