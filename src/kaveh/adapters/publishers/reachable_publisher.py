"""Publisher for the broader TCP-reachable subscription tier."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from kaveh.domain.models import CanonicalConfig
from kaveh.domain.ports import ArtifactStore


@dataclass(frozen=True)
class ReachablePublishReport:
    published: bool
    count: int
    snapshot_id: str | None = None
    reason: str | None = None


class ReachableFeedPublisher:
    """Publish recently TCP-reachable configs under a separate, explicit tier.

    This tier retains source review, parsing, deduplication, schema validation,
    and a recent TCP reachability pass. Unlike the strict tier it does not claim
    that the approved HTTPS probe completed through each configuration.
    """

    tier = "tcp-reachable-v1"

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store

    def publish(
        self,
        configs: Iterable[CanonicalConfig],
        source_errors: dict[str, str] | None = None,
    ) -> ReachablePublishReport:
        unique = {config.identity_hash: config for config in configs if config.identity_hash}
        selected = sorted(unique.values(), key=lambda config: config.identity_hash or "")
        if not selected:
            return ReachablePublishReport(False, 0, reason="NO_RECENT_REACHABLE_CONFIGS")

        content = ("\n".join(config.raw_uri for config in selected) + "\n").encode("utf-8")
        artifact_hash = hashlib.sha256(content).hexdigest()
        read_bytes = getattr(self.artifact_store, "read_bytes", None)
        if callable(read_bytes) and read_bytes("subscriptions/reachable.txt") == content:
            return ReachablePublishReport(
                False,
                len(selected),
                reason="NO_REACHABLE_FEED_CHANGE",
            )

        timestamp = datetime.now(UTC)
        snapshot_id = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{artifact_hash[:12]}"
        manifest = {
            "schema_version": 1,
            "tier": self.tier,
            "snapshot_id": snapshot_id,
            "created_at": timestamp.isoformat(),
            "artifact_hash": artifact_hash,
            "reachable_count": len(selected),
            "by_protocol": {
                protocol: sum(1 for config in selected if config.protocol.value == protocol)
                for protocol in sorted({config.protocol.value for config in selected})
            },
            "source_errors": source_errors or {},
            "notice": "TCP-reachable from the validator origin; not an end-to-end availability guarantee.",
        }
        manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
        encoded = base64.b64encode(content)
        snapshot_root = f"snapshots/reachable/{snapshot_id}"
        self.artifact_store.write_atomic(f"{snapshot_root}/all.txt", content)
        self.artifact_store.write_atomic(f"{snapshot_root}/all.base64", encoded)
        self.artifact_store.write_atomic(f"{snapshot_root}/manifest.v1.json", manifest_bytes)
        self.artifact_store.write_atomic("subscriptions/reachable.txt", content)
        self.artifact_store.write_atomic("subscriptions/reachable.base64", encoded)
        self.artifact_store.write_atomic("subscriptions/reachable.manifest.v1.json", manifest_bytes)
        self.artifact_store.write_atomic("reachable-latest.txt", f"{snapshot_id}\n".encode("utf-8"))
        return ReachablePublishReport(True, len(selected), snapshot_id=snapshot_id)
