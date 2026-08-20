"""Validation use case: execute probes, retain evidence, and score candidates."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Iterable, Protocol

from kaveh.domain.models import CanonicalConfig, ProbeResult, ScoreCard, Source
from kaveh.domain.ports import ConfigRepository
from kaveh.domain.services.qualification import QualificationPolicy
from kaveh.infrastructure.probes.supervisor import ValidationSupervisor, has_end_to_end_success


class ValidationHistory(Protocol):
    def append(self, results: Iterable[ProbeResult]) -> None:
        ...

    def health_window(self, identity_hash: str):  # type: ignore[no-untyped-def]
        ...


@dataclass(frozen=True)
class ValidationReport:
    validated_count: int
    end_to_end_verified_count: int
    qualified_count: int
    scorecards: tuple[ScoreCard, ...]


class ValidateBatch:
    """Application command that preserves the distinction between TCP and E2E."""

    def __init__(
        self,
        repository: ConfigRepository,
        supervisor: ValidationSupervisor,
        history: ValidationHistory,
        policy: QualificationPolicy,
        sources: Iterable[Source],
        max_workers: int = 1,
    ) -> None:
        self.repository = repository
        self.supervisor = supervisor
        self.history = history
        self.policy = policy
        if max_workers < 1 or max_workers > 8:
            raise ValueError("max_workers must be between 1 and 8")
        self.max_workers = max_workers
        self.source_weights = {source.source_id: source.trust_weight for source in sources}

    def run(self) -> ValidationReport:
        scorecards: list[ScoreCard] = []
        validated = e2e_verified = qualified = 0
        configs = tuple(config for config in self.repository.all() if config.identity_hash)

        # Network/Xray work may run concurrently, but persistence and scoring stay
        # ordered and serial. This retains deterministic evidence handling while
        # making a higher candidate budget practical inside the scheduled window.
        if self.max_workers == 1:
            probe_results = tuple(self.supervisor.run(config) for config in configs)
        else:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                probe_results = tuple(executor.map(self.supervisor.run, configs))

        for config, results in zip(configs, probe_results, strict=True):
            validated += 1
            self.history.append(results)
            if not has_end_to_end_success(results):
                continue
            e2e_verified += 1
            health = self.history.health_window(config.identity_hash or "")
            scorecard = self.policy.score(
                health,
                self.source_weights.get(config.source_id or "", 0.5),
            )
            scorecards.append(scorecard)
            save_scorecard = getattr(self.history, "save_scorecard", None)
            if callable(save_scorecard):
                save_scorecard(scorecard)
            if scorecard.qualified:
                qualified += 1
        return ValidationReport(
            validated_count=validated,
            end_to_end_verified_count=e2e_verified,
            qualified_count=qualified,
            scorecards=tuple(scorecards),
        )
