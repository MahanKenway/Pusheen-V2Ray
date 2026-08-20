from __future__ import annotations

import threading
import time
import unittest

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.application.commands.validate_batch import ValidateBatch
from kaveh.domain.models import ProbeResult, ProbeStage, Source
from kaveh.domain.services.qualification import QualificationPolicy
from kaveh.infrastructure.persistence.in_memory import InMemoryConfigRepository
from kaveh.infrastructure.persistence.in_memory_history import InMemoryValidationHistory
from kaveh.infrastructure.probes.schema_probe import SchemaProbe
from kaveh.infrastructure.probes.supervisor import ValidationSupervisor


class RecordingPassingStage:
    def __init__(self, stage: ProbeStage, latency: int | None = None) -> None:
        self.stage = stage
        self.latency = latency
        self.thread_ids: set[int] = set()
        self._lock = threading.Lock()

    def run(self, config):  # type: ignore[no-untyped-def]
        with self._lock:
            self.thread_ids.add(threading.get_ident())
        time.sleep(0.02)
        return ProbeResult.passed(config.identity_hash or "", self.stage, self.latency)


class PassingStage:
    def __init__(self, stage: ProbeStage, latency: int | None = None) -> None:
        self.stage = stage
        self.latency = latency

    def run(self, config):  # type: ignore[no-untyped-def]
        return ProbeResult.passed(config.identity_hash or "", self.stage, self.latency)


class ValidationBatchTests(unittest.TestCase):
    def test_end_to_end_evidence_produces_qualified_scorecard(self) -> None:
        config = ParserRegistry().parse("trojan://secret@example.com:443?security=tls")
        repository = InMemoryConfigRepository()
        repository.upsert(config)
        supervisor = ValidationSupervisor(
            SchemaProbe(),
            PassingStage(ProbeStage.REACHABILITY, 42),
            end_to_end_runner=PassingStage(ProbeStage.END_TO_END, 120),
        )
        report = ValidateBatch(
            repository,
            supervisor,
            InMemoryValidationHistory(),
            QualificationPolicy(),
            [Source("source", "https://example.com/sub", trust_weight=0.8)],
        ).run()
        self.assertEqual(report.validated_count, 1)
        self.assertEqual(report.end_to_end_verified_count, 1)
        self.assertEqual(report.qualified_count, 1)
        self.assertTrue(report.scorecards[0].qualified)

    def test_quic_protocol_skips_tcp_reachability_and_runs_end_to_end(self) -> None:
        config = ParserRegistry().parse("hysteria2://secret@hy.example:8443?sni=cdn.example")
        reachability = RecordingPassingStage(ProbeStage.REACHABILITY, 42)
        results = ValidationSupervisor(
            SchemaProbe(), reachability, end_to_end_runner=PassingStage(ProbeStage.END_TO_END, 120)
        ).run(config)
        self.assertEqual([result.stage for result in results], [ProbeStage.SCHEMA, ProbeStage.END_TO_END])
        self.assertEqual(reachability.thread_ids, set())

    def test_parallel_workers_preserve_end_to_end_qualification(self) -> None:
        repository = InMemoryConfigRepository()
        for index in range(4):
            repository.upsert(
                ParserRegistry().parse(
                    f"trojan://secret@example{index}.com:443?security=tls#sample{index}"
                )
            )
        reachability = RecordingPassingStage(ProbeStage.REACHABILITY, 42)
        end_to_end = RecordingPassingStage(ProbeStage.END_TO_END, 120)
        report = ValidateBatch(
            repository,
            ValidationSupervisor(SchemaProbe(), reachability, end_to_end_runner=end_to_end),
            InMemoryValidationHistory(),
            QualificationPolicy(),
            [Source("source", "https://example.com/sub", trust_weight=0.8)],
            max_workers=4,
        ).run()
        self.assertEqual(report.validated_count, 4)
        self.assertEqual(report.qualified_count, 4)
        self.assertGreater(len(end_to_end.thread_ids), 1)


if __name__ == "__main__":
    unittest.main()
