from __future__ import annotations

import socket
import time
import unittest
from unittest.mock import patch

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.domain.models import ProbeOutcome
from kaveh.infrastructure.probes.tcp_probe import TcpReachabilityProbe


class TcpReachabilityProbeTests(unittest.TestCase):
    def test_stalled_dns_returns_explicit_timeout_within_deadline(self) -> None:
        config = ParserRegistry().parse("trojan://secret@example.com:443?security=tls")

        def stalled_getaddrinfo(*_args, **_kwargs):  # type: ignore[no-untyped-def]
            time.sleep(0.2)
            return []

        probe = TcpReachabilityProbe(timeout_seconds=0.02)
        started = time.perf_counter()
        with patch("kaveh.infrastructure.probes.tcp_probe.socket.getaddrinfo", stalled_getaddrinfo):
            result = probe.run(config)

        self.assertEqual(result.outcome, ProbeOutcome.FAIL)
        self.assertEqual(result.error_code, "DNS_TIMEOUT")
        self.assertLess(time.perf_counter() - started, 0.1)

    def test_dns_failure_remains_distinct_from_timeout(self) -> None:
        config = ParserRegistry().parse("trojan://secret@example.com:443?security=tls")
        probe = TcpReachabilityProbe(timeout_seconds=0.1)
        with patch(
            "kaveh.infrastructure.probes.tcp_probe.socket.getaddrinfo",
            side_effect=socket.gaierror("not found"),
        ):
            result = probe.run(config)

        self.assertEqual(result.outcome, ProbeOutcome.FAIL)
        self.assertEqual(result.error_code, "DNS_FAILURE")


if __name__ == "__main__":
    unittest.main()
