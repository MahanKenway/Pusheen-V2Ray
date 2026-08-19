from __future__ import annotations

import unittest
from datetime import UTC, datetime

from kaveh.cli import _publication_inputs
from kaveh.domain.models import CanonicalConfig, HealthWindow, Protocol, Source
from kaveh.domain.services.qualification import QualificationPolicy


class _HistoricalRepository:
    def __init__(self, configs: tuple[CanonicalConfig, ...]) -> None:
        self.configs = configs

    def recently_qualified(self, max_age_hours: int) -> tuple[CanonicalConfig, ...]:
        self.max_age_hours = max_age_hours
        return self.configs


class _SuccessfulHistory:
    def health_window(self, identity_hash: str) -> HealthWindow:
        return HealthWindow(
            identity_hash=identity_hash,
            sample_count=1,
            success_count=1,
            median_latency_ms=100,
            last_success_at=datetime.now(UTC),
        )


class PublicationFallbackTests(unittest.TestCase):
    def test_fresh_qualified_history_is_used_when_current_run_has_no_success(self) -> None:
        config = CanonicalConfig(
            protocol=Protocol.VLESS,
            host="example.test",
            port=443,
            credential="redacted-for-test",
            source_id="reviewed-source",
            identity_hash="a" * 64,
            raw_uri="vless://redacted@example.test:443",
        )
        policy = QualificationPolicy()

        configs, cards, mode = _publication_inputs(
            (),
            (),
            _HistoricalRepository((config,)),
            _SuccessfulHistory(),
            policy,
            (Source("reviewed-source", "https://example.test/feed", trust_weight=0.9),),
        )

        self.assertEqual(mode, "fresh_history")
        self.assertEqual(configs, (config,))
        self.assertEqual(len(cards), 1)
        self.assertTrue(cards[0].qualified)


if __name__ == "__main__":
    unittest.main()
