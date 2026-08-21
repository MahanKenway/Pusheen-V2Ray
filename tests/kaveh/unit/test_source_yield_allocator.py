from __future__ import annotations

import unittest

from kaveh.domain.models import CanonicalConfig, Protocol
from kaveh.domain.services.source_yield_allocator import (
    SourceYieldMetric,
    allocate_validation_candidates,
)


def _config(source_id: str, identity: str) -> CanonicalConfig:
    return CanonicalConfig(
        protocol=Protocol.VLESS,
        host=f"{identity}.example.invalid",
        port=443,
        credential="test-only",
        source_id=source_id,
        identity_hash=identity,
    )


class SourceYieldAllocatorTests(unittest.TestCase):
    def test_empty_history_keeps_full_candidate_budget(self) -> None:
        candidates = tuple(_config("source-a", f"id-{index}") for index in range(8))

        report = allocate_validation_candidates(candidates, (), limit=8)

        self.assertEqual(8, len(report.selected))
        self.assertEqual([item.identity_hash for item in candidates], [item.identity_hash for item in report.selected])
        self.assertEqual(4, report.high_yield_budget)
        self.assertEqual(2, report.provisional_budget)
        self.assertEqual(2, report.exploration_budget)

    def test_high_yield_source_is_prioritized_but_new_source_is_explored(self) -> None:
        candidates = (
            _config("source-provisional", "p-1"),
            _config("source-high", "h-1"),
            _config("source-high", "h-2"),
            _config("source-high", "h-3"),
            _config("source-high", "h-4"),
            _config("source-new", "n-1"),
            _config("source-new", "n-2"),
            _config("source-provisional", "p-2"),
        )
        metrics = (
            SourceYieldMetric("source-high", "vless", 12, 8, 5),
            SourceYieldMetric("source-provisional", "vless", 2, 0, 0),
        )

        report = allocate_validation_candidates(candidates, metrics, limit=8)

        source_ids = [item.source_id for item in report.selected]
        self.assertEqual(8, len(report.selected))
        self.assertEqual("source-high", source_ids[0])
        self.assertIn("source-new", source_ids)
        self.assertEqual(4, report.high_yield_selected)
        self.assertGreaterEqual(report.exploration_selected, 1)


if __name__ == "__main__":
    unittest.main()
