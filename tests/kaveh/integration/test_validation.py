from __future__ import annotations

import unittest

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.application.commands.validate_batch import ValidateBatch
from kaveh.domain.models import ProbeResult, ProbeStage, Source
from kaveh.domain.services.qualification import QualificationPolicy
from kaveh.infrastructure.persistence.in_memory import InMemoryConfigRepository
from kaveh.infrastructure.persistence.in_memory_history import InMemoryValidationHistory
from kaveh.infrastructure.probes.schema_probe import SchemaProbe
from kaveh.infrastructure.probes.supervisor import ValidationSupervisor


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


if __name__ == "__main__":
    unittest.main()
