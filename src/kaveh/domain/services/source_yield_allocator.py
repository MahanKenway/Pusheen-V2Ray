from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping

from kaveh.domain.models import CanonicalConfig


@dataclass(frozen=True)
class SourceYieldMetric:
    """Public-safe historical yield used only to order a bounded probe budget."""

    source_id: str
    protocol: str
    validation_samples: int
    end_to_end_successes: int
    qualified_count: int

    @property
    def smoothed_e2e_rate(self) -> float:
        """Use a small Beta prior so one lucky sample cannot dominate selection."""

        return (self.end_to_end_successes + 1.0) / (self.validation_samples + 2.0)


@dataclass(frozen=True)
class AllocationReport:
    selected: tuple[CanonicalConfig, ...]
    high_yield_budget: int
    provisional_budget: int
    exploration_budget: int
    high_yield_selected: int
    provisional_selected: int
    exploration_selected: int
    fallback_selected: int


def allocate_validation_candidates(
    candidates: Iterable[CanonicalConfig],
    metrics: Iterable[SourceYieldMetric],
    limit: int,
) -> AllocationReport:
    """Allocate a fixed validation budget without excluding unexplored sources.

    The 60/25/15 split is an ordering policy, not a qualification shortcut:
    every selected candidate is still submitted to the same Xray/sing-box
    validation and evidence policy.  The input candidate order remains the
    deterministic fallback, so an empty or newly-created metrics table cannot
    reduce the current validation throughput.
    """

    if limit < 1:
        raise ValueError("limit must be at least one")
    ordered = tuple(candidate for candidate in candidates if candidate.identity_hash)
    if not ordered:
        return AllocationReport((), 0, 0, 0, 0, 0, 0, 0)

    actual_limit = min(limit, len(ordered))
    high_budget = int(actual_limit * 0.60)
    provisional_budget = int(actual_limit * 0.25)
    exploration_budget = actual_limit - high_budget - provisional_budget
    metric_by_source = _aggregate_metrics(metrics)
    high_sources = {
        source_id
        for source_id, metric in metric_by_source.items()
        if metric.validation_samples >= 4 and metric.smoothed_e2e_rate >= 0.25
    }
    provisional_sources = set(metric_by_source) - high_sources

    selected: list[CanonicalConfig] = []
    selected_hashes: set[str] = set()

    def take(predicate, budget: int) -> int:
        taken = 0
        if budget <= 0:
            return taken
        for candidate in ordered:
            identity_hash = candidate.identity_hash
            if not identity_hash or identity_hash in selected_hashes or not predicate(candidate):
                continue
            selected.append(candidate)
            selected_hashes.add(identity_hash)
            taken += 1
            if taken == budget:
                break
        return taken

    high_selected = take(lambda candidate: candidate.source_id in high_sources, high_budget)
    provisional_selected = take(
        lambda candidate: candidate.source_id in provisional_sources,
        provisional_budget,
    )

    # Prefer a source not represented yet for the exploration share.  Sources
    # without metrics are specifically included to avoid lock-in to old winners.
    represented_sources = {candidate.source_id for candidate in selected if candidate.source_id}
    exploration_selected = take(
        lambda candidate: candidate.source_id not in represented_sources,
        exploration_budget,
    )
    if exploration_selected < exploration_budget:
        exploration_selected += take(lambda _candidate: True, exploration_budget - exploration_selected)

    fallback_selected = take(lambda _candidate: True, actual_limit - len(selected))
    return AllocationReport(
        selected=tuple(selected),
        high_yield_budget=high_budget,
        provisional_budget=provisional_budget,
        exploration_budget=exploration_budget,
        high_yield_selected=high_selected,
        provisional_selected=provisional_selected,
        exploration_selected=exploration_selected,
        fallback_selected=fallback_selected,
    )


def _aggregate_metrics(metrics: Iterable[SourceYieldMetric]) -> Mapping[str, SourceYieldMetric]:
    totals: dict[str, SourceYieldMetric] = {}
    for metric in metrics:
        if not metric.source_id:
            continue
        current = totals.get(metric.source_id)
        if current is None:
            totals[metric.source_id] = SourceYieldMetric(
                source_id=metric.source_id,
                protocol="all",
                validation_samples=max(0, metric.validation_samples),
                end_to_end_successes=max(0, metric.end_to_end_successes),
                qualified_count=max(0, metric.qualified_count),
            )
            continue
        totals[metric.source_id] = SourceYieldMetric(
            source_id=metric.source_id,
            protocol="all",
            validation_samples=current.validation_samples + max(0, metric.validation_samples),
            end_to_end_successes=current.end_to_end_successes + max(0, metric.end_to_end_successes),
            qualified_count=current.qualified_count + max(0, metric.qualified_count),
        )
    return totals
