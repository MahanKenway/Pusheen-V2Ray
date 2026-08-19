"""Transparent scoring and qualification rules for Kaveh feeds."""

from __future__ import annotations

from datetime import UTC, datetime

from kaveh.domain.models import HealthWindow, ScoreCard


class QualificationPolicy:
    """Versioned, inspectable quality policy for the initial release."""

    version = "kaveh-standard-v1"
    min_success_rate = 0.70
    min_samples = 1
    max_staleness_hours = 12
    min_qualified_score = 70

    def score(
        self,
        health: HealthWindow,
        trust_weight: float,
        now: datetime | None = None,
    ) -> ScoreCard:
        """Calculate a score from end-to-end history and source evidence."""

        now = now or datetime.now(UTC)
        success_component = round(50 * health.success_rate)
        latency_component = self._latency_component(health.median_latency_ms)
        freshness_component = self._freshness_component(health.last_success_at, now)
        trust_component = round(10 * min(max(trust_weight, 0.0), 1.0))
        score = min(
            100,
            max(0, success_component + latency_component + freshness_component + trust_component),
        )
        qualified = (
            health.sample_count >= self.min_samples
            and health.success_rate >= self.min_success_rate
            and freshness_component > 0
            and score >= self.min_qualified_score
        )
        return ScoreCard(
            identity_hash=health.identity_hash,
            score=score,
            policy_version=self.version,
            explanation={
                "success": success_component,
                "latency": latency_component,
                "freshness": freshness_component,
                "source_trust": trust_component,
            },
            qualified=qualified,
        )

    @staticmethod
    def _latency_component(latency_ms: int | None) -> int:
        if latency_ms is None:
            return 0
        if latency_ms <= 200:
            return 20
        if latency_ms <= 500:
            return 15
        if latency_ms <= 1000:
            return 8
        return 2

    def _freshness_component(self, last_success_at: datetime | None, now: datetime) -> int:
        if last_success_at is None:
            return 0
        age_seconds = max(0.0, (now - last_success_at).total_seconds())
        if age_seconds <= 2 * 60 * 60:
            return 20
        if age_seconds <= self.max_staleness_hours * 60 * 60:
            return 10
        return 0
