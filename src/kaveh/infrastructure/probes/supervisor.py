"""Ordered validation supervisor with explicit end-to-end evidence."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from kaveh.domain.models import CanonicalConfig, ProbeOutcome, ProbeResult, ProbeStage


class StageRunner(Protocol):
    def run(self, config: CanonicalConfig) -> ProbeResult:
        ...


class ValidationSupervisor:
    """Run schema, reachability, and end-to-end stages in a known order."""

    def __init__(
        self,
        schema_runner: StageRunner,
        reachability_runner: StageRunner,
        runtime_runner: StageRunner | None = None,
        end_to_end_runner: StageRunner | None = None,
    ) -> None:
        self._runners: tuple[StageRunner, ...] = tuple(
            runner
            for runner in (
                schema_runner,
                reachability_runner,
                runtime_runner,
                end_to_end_runner,
            )
            if runner is not None
        )

    def run(self, config: CanonicalConfig) -> tuple[ProbeResult, ...]:
        results: list[ProbeResult] = []
        for runner in self._runners:
            result = runner.run(config)
            results.append(result)
            if result.outcome is ProbeOutcome.FAIL:
                break
        return tuple(results)


def has_end_to_end_success(results: Iterable[ProbeResult]) -> bool:
    """Qualification must rely on an actual proxy-path success, never TCP alone."""

    return any(
        result.stage is ProbeStage.END_TO_END and result.outcome is ProbeOutcome.PASS
        for result in results
    )
