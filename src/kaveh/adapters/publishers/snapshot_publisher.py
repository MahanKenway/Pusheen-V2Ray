"""Build immutable, transparent publication snapshots."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from kaveh.domain.models import CanonicalConfig, PublicationSnapshot, ScoreCard
from kaveh.domain.ports import ArtifactStore


class SnapshotPublisher:
    """Publish qualified feeds only after a complete snapshot is assembled."""

    def __init__(self, artifact_store: ArtifactStore, policy_version: str) -> None:
        self.artifact_store = artifact_store
        self.policy_version = policy_version

    def publish(
        self,
        configs: Iterable[CanonicalConfig],
        scorecards: Iterable[ScoreCard],
        source_errors: dict[str, str] | None = None,
    ) -> PublicationSnapshot | None:
        cards = {card.identity_hash: card for card in scorecards if card.qualified}
        qualified = [
            config
            for config in configs
            if config.identity_hash and config.identity_hash in cards
        ]
        if not qualified:
            return None
        qualified.sort(key=lambda config: (-cards[config.identity_hash or ""].score, config.identity_hash or ""))
        timestamp = datetime.now(UTC)
        content = ("\n".join(config.raw_uri for config in qualified) + "\n").encode("utf-8")
        artifact_hash = hashlib.sha256(content).hexdigest()
        snapshot_id = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{artifact_hash[:12]}"
        prefix = f"snapshots/{snapshot_id}"

        self.artifact_store.write_atomic(f"{prefix}/stable.txt", content)
        self.artifact_store.write_atomic(f"{prefix}/stable.base64", _b64(content))
        for protocol in sorted({config.protocol.value for config in qualified}):
            protocol_content = (
                "\n".join(config.raw_uri for config in qualified if config.protocol.value == protocol)
                + "\n"
            ).encode("utf-8")
            self.artifact_store.write_atomic(f"{prefix}/protocols/{protocol}.txt", protocol_content)

        manifest = {
            "schema_version": 1,
            "snapshot_id": snapshot_id,
            "created_at": timestamp.isoformat(),
            "policy_version": self.policy_version,
            "artifact_hash": artifact_hash,
            "qualified_count": len(qualified),
            "by_protocol": {
                protocol: sum(1 for config in qualified if config.protocol.value == protocol)
                for protocol in sorted({config.protocol.value for config in qualified})
            },
            "score": {
                "minimum": min(cards[config.identity_hash or ""].score for config in qualified),
                "maximum": max(cards[config.identity_hash or ""].score for config in qualified),
            },
            "source_errors": source_errors or {},
            "notice": "Results are time- and vantage-specific; no availability guarantee is implied.",
        }
        self.artifact_store.write_atomic(
            f"{prefix}/manifest.v1.json",
            (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        self.artifact_store.switch_latest(snapshot_id)
        return PublicationSnapshot(
            snapshot_id=snapshot_id,
            created_at=timestamp,
            policy_version=self.policy_version,
            config_count=len(qualified),
            artifact_hash=artifact_hash,
        )


def _b64(content: bytes) -> bytes:
    import base64

    return base64.b64encode(content)
