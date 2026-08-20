"""Build immutable snapshots and stable subscription artifacts."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import Iterable

from kaveh.domain.models import CanonicalConfig, PublicationSnapshot, ScoreCard
from kaveh.domain.ports import ArtifactStore


class SnapshotPublisher:
    """Publish qualified feeds only after a complete snapshot is assembled.

    Each successful publication contains an immutable archive under
    ``snapshots/`` and stable consumer URLs under ``subscriptions/``. The
    end-to-end tier is deliberately published under ``strict`` so ``all`` can
    remain the high-coverage public feed without misrepresenting its evidence.
    """

    def __init__(self, artifact_store: ArtifactStore, policy_version: str) -> None:
        self.artifact_store = artifact_store
        self.policy_version = policy_version
        self.last_skip_reason: str | None = None

    def publish(
        self,
        configs: Iterable[CanonicalConfig],
        scorecards: Iterable[ScoreCard],
        source_errors: dict[str, str] | None = None,
    ) -> PublicationSnapshot | None:
        self.last_skip_reason = None
        cards = {card.identity_hash: card for card in scorecards if card.qualified}
        qualified = [
            config
            for config in configs
            if config.identity_hash and config.identity_hash in cards
        ]
        if not qualified:
            self.last_skip_reason = "NO_QUALIFIED_CONFIGS"
            return None
        qualified.sort(
            key=lambda config: (-cards[config.identity_hash or ""].score, config.identity_hash or "")
        )
        content = ("\n".join(config.raw_uri for config in qualified) + "\n").encode("utf-8")
        artifact_hash = hashlib.sha256(content).hexdigest()
        if self._stable_feed_matches(content):
            self.last_skip_reason = "NO_QUALIFIED_FEED_CHANGE"
            return None

        timestamp = datetime.now(UTC)
        snapshot_id = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{artifact_hash[:12]}"
        prefix = f"snapshots/{snapshot_id}"
        protocol_content = {
            protocol: (
                "\n".join(
                    config.raw_uri for config in qualified if config.protocol.value == protocol
                )
                + "\n"
            ).encode("utf-8")
            for protocol in sorted({config.protocol.value for config in qualified})
        }
        manifest = self._manifest(
            snapshot_id, timestamp, artifact_hash, qualified, cards, source_errors or {}
        )
        manifest_content = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")

        # First write a complete, immutable archive. A failed run cannot change a
        # consumer-facing stable URL because the switch happens only afterwards.
        self.artifact_store.write_atomic(f"{prefix}/all.txt", content)
        self.artifact_store.write_atomic(f"{prefix}/all.base64", _b64(content))
        for protocol, payload in protocol_content.items():
            self.artifact_store.write_atomic(f"{prefix}/protocols/{protocol}.txt", payload)
            self.artifact_store.write_atomic(f"{prefix}/protocols/{protocol}.base64", _b64(payload))
        self.artifact_store.write_atomic(f"{prefix}/manifest.v1.json", manifest_content)

        # Strict stable paths stay separate from the high-coverage all feed.
        self.artifact_store.write_atomic("subscriptions/strict.txt", content)
        self.artifact_store.write_atomic("subscriptions/strict.base64", _b64(content))
        for protocol, payload in protocol_content.items():
            self.artifact_store.write_atomic(f"subscriptions/strict-{protocol}.txt", payload)
            self.artifact_store.write_atomic(f"subscriptions/strict-{protocol}.base64", _b64(payload))
        self.artifact_store.write_atomic("subscriptions/strict.manifest.v1.json", manifest_content)
        self.artifact_store.write_atomic("strict-latest.txt", f"{snapshot_id}\n".encode("utf-8"))
        self.artifact_store.switch_latest(snapshot_id)
        return PublicationSnapshot(
            snapshot_id=snapshot_id,
            created_at=timestamp,
            policy_version=self.policy_version,
            config_count=len(qualified),
            artifact_hash=artifact_hash,
        )

    def _stable_feed_matches(self, content: bytes) -> bool:
        read_bytes = getattr(self.artifact_store, "read_bytes", None)
        if not callable(read_bytes):
            return False
        previous = read_bytes("subscriptions/strict.txt")
        return previous == content

    def _manifest(
        self,
        snapshot_id: str,
        timestamp: datetime,
        artifact_hash: str,
        qualified: list[CanonicalConfig],
        cards: dict[str, ScoreCard],
        source_errors: dict[str, str],
    ) -> dict[str, object]:
        protocols = sorted({config.protocol.value for config in qualified})
        return {
            "schema_version": 1,
            "snapshot_id": snapshot_id,
            "created_at": timestamp.isoformat(),
            "policy_version": self.policy_version,
            "artifact_hash": artifact_hash,
            "qualified_count": len(qualified),
            "by_protocol": {
                protocol: sum(1 for config in qualified if config.protocol.value == protocol)
                for protocol in protocols
            },
            "score": {
                "minimum": min(cards[config.identity_hash or ""].score for config in qualified),
                "maximum": max(cards[config.identity_hash or ""].score for config in qualified),
            },
            "source_errors": source_errors,
            "notice": "Results are time- and vantage-specific; no availability guarantee is implied.",
        }


def _b64(content: bytes) -> bytes:
    return base64.b64encode(content)
