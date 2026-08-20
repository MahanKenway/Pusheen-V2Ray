"""Publisher for a diversity-aware TCP-reachable continuity feed.

The resilient feed does not claim Iran availability or stronger validation than the
reachable tier. It uses the same current TCP evidence, then deliberately limits
common-mode concentration by direct source, endpoint, protocol, and transport
family. This produces a smaller fallback list that is less likely to fail all at
once when one upstream, port family, or transport is disrupted.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from kaveh.adapters.publishers.reachable_publisher import (
    _content,
    _deduplicate_preserving_order,
    _is_client_share_uri,
)
from kaveh.domain.models import CanonicalConfig
from kaveh.domain.ports import ArtifactStore


@dataclass(frozen=True)
class ResilientPublishReport:
    """Safe publication metadata for the diversity-aware fallback tier."""

    published: bool
    count: int
    snapshot_id: str | None = None
    reason: str | None = None


class ResilientFeedPublisher:
    """Publish a bounded fallback feed with anti-concentration policy.

    Input must already be ordered by the repository's evidence ranking. Selection
    preserves that priority unless accepting an entry would exceed a documented
    concentration limit. No config is included without the same recent TCP
    reachability evidence required by the reachable tier.
    """

    tier = "tcp-reachable-diverse-v1"
    limit = 60
    max_source_share = 0.50
    max_protocol_share = 0.70
    max_transport_family_share = 0.50

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store

    def publish(
        self,
        configs: Iterable[CanonicalConfig],
        source_errors: dict[str, str] | None = None,
    ) -> ResilientPublishReport:
        reachable = _deduplicate_preserving_order(
            config for config in configs if _is_client_share_uri(config)
        )
        selected = self.select(reachable)
        if not selected:
            return ResilientPublishReport(False, 0, reason="NO_DIVERSE_REACHABLE_CONFIGS")

        content = _content(selected)
        artifact_hash = hashlib.sha256(content).hexdigest()
        read_bytes = getattr(self.artifact_store, "read_bytes", None)
        if callable(read_bytes) and read_bytes("subscriptions/resilient.txt") == content:
            return ResilientPublishReport(
                False,
                len(selected),
                reason="NO_RESILIENT_FEED_CHANGE",
            )

        timestamp = datetime.now(UTC)
        snapshot_id = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{artifact_hash[:12]}"
        manifest = {
            "schema_version": 1,
            "tier": self.tier,
            "snapshot_id": snapshot_id,
            "created_at": timestamp.isoformat(),
            "artifact_hash": artifact_hash,
            "reachable_count": len(reachable),
            "selected_count": len(selected),
            "selection": {
                "input_order": "repository stability score then latest successful TCP latency",
                "endpoint_limit": 1,
                "max_source_share": self.max_source_share,
                "max_protocol_share": self.max_protocol_share,
                "max_transport_family_share": self.max_transport_family_share,
            },
            "by_protocol": _distribution(selected, lambda item: item.protocol.value),
            "by_source": _distribution(selected, lambda item: item.source_id or "unknown"),
            "by_transport_family": _distribution(selected, _transport_family),
            "source_errors": source_errors or {},
            "notice": (
                "Recent TCP-reachability evidence from the validator origin with "
                "anti-concentration selection; not an end-to-end or Iran-availability guarantee."
            ),
        }
        manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
        snapshot_root = f"snapshots/resilient/{snapshot_id}"
        self._write_feed(f"{snapshot_root}/configs", selected)
        self.artifact_store.write_atomic(f"{snapshot_root}/manifest.v1.json", manifest_bytes)
        self._write_feed("subscriptions/resilient", selected)
        self.artifact_store.write_atomic("subscriptions/resilient.manifest.v1.json", manifest_bytes)
        self.artifact_store.write_atomic("resilient-latest.txt", f"{snapshot_id}\n".encode("utf-8"))
        return ResilientPublishReport(True, len(selected), snapshot_id=snapshot_id)

    def select(self, configs: Iterable[CanonicalConfig]) -> list[CanonicalConfig]:
        """Return the deterministic, evidence-backed anti-concentration selection."""

        return self._select(configs)

    def _select(self, configs: Iterable[CanonicalConfig]) -> list[CanonicalConfig]:
        selected: list[CanonicalConfig] = []
        seen_endpoints: set[tuple[str, int]] = set()
        source_counts: Counter[str] = Counter()
        protocol_counts: Counter[str] = Counter()
        transport_counts: Counter[str] = Counter()
        source_cap = _cap(self.limit, self.max_source_share)
        protocol_cap = _cap(self.limit, self.max_protocol_share)
        transport_cap = _cap(self.limit, self.max_transport_family_share)

        for config in configs:
            if len(selected) >= self.limit:
                break
            endpoint = (config.host.lower(), config.port)
            source = config.source_id or "unknown"
            protocol = config.protocol.value
            transport = _transport_family(config)
            if endpoint in seen_endpoints:
                continue
            if source_counts[source] >= source_cap:
                continue
            if protocol_counts[protocol] >= protocol_cap:
                continue
            if transport_counts[transport] >= transport_cap:
                continue
            selected.append(config)
            seen_endpoints.add(endpoint)
            source_counts[source] += 1
            protocol_counts[protocol] += 1
            transport_counts[transport] += 1
        return selected

    def _write_feed(self, stem: str, configs: Iterable[CanonicalConfig]) -> None:
        content = _content(configs)
        self.artifact_store.write_atomic(f"{stem}.txt", content)
        self.artifact_store.write_atomic(f"{stem}.base64", base64.b64encode(content))


def _cap(limit: int, share: float) -> int:
    return max(1, math.ceil(limit * share))


def _transport_family(config: CanonicalConfig) -> str:
    return ":".join(
        (
            config.protocol.value,
            config.transport.network or "unknown",
            config.transport.security or "none",
        )
    )


def _distribution(
    configs: Iterable[CanonicalConfig],
    key,
) -> dict[str, int]:
    return dict(sorted(Counter(key(config) for config in configs).items()))
