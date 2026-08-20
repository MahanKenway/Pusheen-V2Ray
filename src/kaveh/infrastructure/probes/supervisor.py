"""Ordered validation supervisor with explicit end-to-end evidence."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from kaveh.domain.models import CanonicalConfig, ProbeOutcome, ProbeResult, ProbeStage, Protocol as ProxyProtocol


class StageRunner(Protocol):
    def run(self, config: CanonicalConfig) -> ProbeResult:
        ...


class ValidationSupervisor:
    """Run appropriate evidence stages in a known protocol-aware order.

    TCP reachability is useful for TCP-oriented protocols. QUIC-native Hysteria
    2 and TUIC must instead reach the local runtime end-to-end stage directly;
    a TCP socket to their endpoint is not meaningful evidence.
    """

    _quic_protocols = frozenset({ProxyProtocol.HYSTERIA2, ProxyProtocol.TUIC})

    def __init__(
        self,
        schema_runner: StageRunner,
        reachability_runner: StageRunner,
        runtime_runner: StageRunner | None = None,
        end_to_end_runner: StageRunner | None = None,
    ) -> None:
        self.schema_runner = schema_runner
        self.reachability_runner = reachability_runner
        self.runtime_runner = runtime_runner
        self.end_to_end_runner = end_to_end_runner

    def run(self, config: CanonicalConfig) -> tuple[ProbeResult, ...]:
        results: list[ProbeResult] = []
        quic_native = (
            config.protocol in self._quic_protocols
            or (config.protocol is ProxyProtocol.NAIVE and config.transport.extra.get("quic") == "true")
        )
        runners: tuple[StageRunner | None, ...] = (
            self.schema_runner,
            None if quic_native else self.reachability_runner,
            self.runtime_runner,
            self.end_to_end_runner,
        )
        for runner in runners:
            if runner is None:
                continue
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
