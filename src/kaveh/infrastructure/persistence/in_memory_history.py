"""In-memory validation history for local runs and tests."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from statistics import median

from kaveh.domain.models import HealthWindow, ProbeOutcome, ProbeResult, ProbeStage


class InMemoryValidationHistory:
    def __init__(self) -> None:
        self._results: dict[str, list[ProbeResult]] = defaultdict(list)

    def append(self, results: Iterable[ProbeResult]) -> None:
        for result in results:
            self._results[result.identity_hash].append(result)

    def results_for(self, identity_hash: str) -> tuple[ProbeResult, ...]:
        return tuple(self._results.get(identity_hash, []))

    def health_window(self, identity_hash: str) -> HealthWindow:
        relevant = [
            result
            for result in self._results.get(identity_hash, [])
            if result.stage is ProbeStage.END_TO_END
        ]
        successes = [result for result in relevant if result.outcome is ProbeOutcome.PASS]
        latencies = [result.latency_ms for result in successes if result.latency_ms is not None]
        last_success = max((result.observed_at for result in successes), default=None)
        return HealthWindow(
            identity_hash=identity_hash,
            sample_count=len(relevant),
            success_count=len(successes),
            median_latency_ms=int(median(latencies)) if latencies else None,
            last_success_at=last_success,
        )
