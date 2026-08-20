from __future__ import annotations

import unittest

from kaveh.domain.models import CanonicalConfig, ProbeResult, ProbeStage, Protocol, Transport
from kaveh.domain.services.identity import with_identity
from kaveh.infrastructure.probes.supervisor import ValidationSupervisor


class RecordingRunner:
    def __init__(self, name: str, calls: list[str]) -> None:
        self.name = name
        self.calls = calls

    def run(self, config: CanonicalConfig) -> ProbeResult:
        self.calls.append(self.name)
        stage = {
            "schema": ProbeStage.SCHEMA,
            "reachability": ProbeStage.REACHABILITY,
            "end_to_end": ProbeStage.END_TO_END,
        }[self.name]
        return ProbeResult.passed(config.identity_hash or "unknown", stage)


class ValidationSupervisorTests(unittest.TestCase):
    def test_naive_quic_skips_tcp_and_requires_runtime_path(self) -> None:
        config = with_identity(
            CanonicalConfig(
                protocol=Protocol.NAIVE,
                host="naive.example",
                port=443,
                credential="user:secret",
                transport=Transport(network="udp", security="tls", extra={"quic": "true"}),
                raw_uri="profile-json://fixture",
            )
        )
        calls: list[str] = []
        results = ValidationSupervisor(
            RecordingRunner("schema", calls),
            RecordingRunner("reachability", calls),
            end_to_end_runner=RecordingRunner("end_to_end", calls),
        ).run(config)

        self.assertEqual(calls, ["schema", "end_to_end"])
        self.assertEqual([result.stage for result in results], [ProbeStage.SCHEMA, ProbeStage.END_TO_END])

    def test_naive_http2_keeps_tcp_reachability_stage(self) -> None:
        config = with_identity(
            CanonicalConfig(
                protocol=Protocol.NAIVE,
                host="naive.example",
                port=443,
                credential="user:secret",
                transport=Transport(network="tcp", security="tls"),
                raw_uri="profile-json://fixture",
            )
        )
        calls: list[str] = []
        ValidationSupervisor(
            RecordingRunner("schema", calls),
            RecordingRunner("reachability", calls),
            end_to_end_runner=RecordingRunner("end_to_end", calls),
        ).run(config)

        self.assertEqual(calls, ["schema", "reachability", "end_to_end"])


if __name__ == "__main__":
    unittest.main()
