"""Publication application command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from kaveh.adapters.publishers.snapshot_publisher import SnapshotPublisher
from kaveh.domain.models import CanonicalConfig, PublicationSnapshot, ScoreCard


@dataclass(frozen=True)
class PublishReport:
    published: bool
    snapshot: PublicationSnapshot | None
    reason: str | None = None


class PublishSnapshot:
    def __init__(self, publisher: SnapshotPublisher) -> None:
        self.publisher = publisher

    def run(
        self,
        configs: Iterable[CanonicalConfig],
        scorecards: Iterable[ScoreCard],
        source_errors: dict[str, str] | None = None,
    ) -> PublishReport:
        snapshot = self.publisher.publish(configs, scorecards, source_errors)
        if snapshot is None:
            return PublishReport(
                published=False,
                snapshot=None,
                reason=self.publisher.last_skip_reason or "NO_QUALIFIED_CONFIGS",
            )
        return PublishReport(published=True, snapshot=snapshot)
