from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from kaveh.domain.models import HealthWindow, ProbeResult, ProbeStage
from kaveh.domain.services.qualification import QualificationPolicy
from kaveh.infrastructure.probes.supervisor import has_end_to_end_success


class QualificationTests(unittest.TestCase):
    def test_fresh_successful_history_is_qualified(self) -> None:
        policy = QualificationPolicy()
        health = HealthWindow(
            identity_hash="a" * 64,
            sample_count=4,
            success_count=4,
            median_latency_ms=180,
            last_success_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        card = policy.score(health, trust_weight=0.8)
        self.assertTrue(card.qualified)
        self.assertGreaterEqual(card.score, policy.min_qualified_score)
        self.assertEqual(sum(card.explanation.values()), card.score)

    def test_stale_history_is_not_qualified(self) -> None:
        health = HealthWindow(
            identity_hash="b" * 64,
            sample_count=2,
            success_count=2,
            median_latency_ms=100,
            last_success_at=datetime.now(UTC) - timedelta(hours=13),
        )
        self.assertFalse(QualificationPolicy().score(health, trust_weight=1).qualified)

    def test_tcp_success_does_not_count_as_end_to_end_success(self) -> None:
        result = ProbeResult.passed("c" * 64, ProbeStage.REACHABILITY, latency_ms=12)
        self.assertFalse(has_end_to_end_success([result]))

    def test_end_to_end_success_counts_as_evidence(self) -> None:
        result = ProbeResult.passed("d" * 64, ProbeStage.END_TO_END, latency_ms=120)
        self.assertTrue(has_end_to_end_success([result]))


if __name__ == "__main__":
    unittest.main()
