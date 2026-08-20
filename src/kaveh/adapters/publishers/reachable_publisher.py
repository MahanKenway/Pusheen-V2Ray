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
    """Publish a transparent TCP-reachable tier, separate from strict evidence.

    Input order is retained deliberately: the repository orders current reachable
    evidence by the best observed TCP latency, so ``reachable-fast`` is a useful
    compact subset while protocol-specific files remain directly consumable.
    """

    tier = "tcp-reachable-v3"
    fast_limit = 50
    primary_protocol_order = ("vless", "trojan", "vmess", "ss")

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store

    def publish(
        self,
        configs: Iterable[CanonicalConfig],
        source_errors: dict[str, str] | None = None,
    ) -> ReachablePublishReport:
        reachable = _deduplicate_preserving_order(configs)
        if not reachable:
            return ReachablePublishReport(False, 0, reason="NO_RECENT_REACHABLE_CONFIGS")

        # The primary feed favors broadly compatible VLESS first, then Trojan,
        # while the reachable and fast variants retain evidence/latency ordering.
        selected = _prioritize_protocols(reachable, self.primary_protocol_order)
        content = _content(selected)
        artifact_hash = hashlib.sha256(content).hexdigest()
        read_bytes = getattr(self.artifact_store, "read_bytes", None)
        if callable(read_bytes) and read_bytes("subscriptions/all.txt") == content:
            return ReachablePublishReport(
                False,
                len(selected),
                reason="NO_REACHABLE_FEED_CHANGE",
            )

        timestamp = datetime.now(UTC)
        snapshot_id = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{artifact_hash[:12]}"
        fast = reachable[: self.fast_limit]
        protocol_configs = {
            protocol: [config for config in reachable if config.protocol.value == protocol]
            for protocol in sorted({config.protocol.value for config in reachable})
        }
        manifest = {
            "schema_version": 3,
            "tier": self.tier,
            "snapshot_id": snapshot_id,
            "created_at": timestamp.isoformat(),
            "artifact_hash": artifact_hash,
            "reachable_count": len(selected),
            "fast_count": len(fast),
            "ordering": "primary: VLESS, Trojan, VMess, Shadowsocks; within each protocol: best observed TCP latency and recent evidence",
            "primary_protocol_order": list(self.primary_protocol_order),
            "by_protocol": {protocol: len(items) for protocol, items in protocol_configs.items()},
            "source_errors": source_errors or {},
            "notice": "TCP-reachable from the validator origin; not an end-to-end availability guarantee.",
        }
        manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
        snapshot_root = f"snapshots/reachable/{snapshot_id}"

        self._write_feed(f"{snapshot_root}/all", selected)
        self._write_feed(f"{snapshot_root}/fast", fast)
        for protocol, items in protocol_configs.items():
            self._write_feed(f"{snapshot_root}/protocols/{protocol}", items)
        self.artifact_store.write_atomic(f"{snapshot_root}/manifest.v1.json", manifest_bytes)

        # ``all`` is the primary high-coverage feed. It has the same bounded,
        # recent TCP evidence as reachable, while strict keeps its own URL.
        self._write_feed("subscriptions/all", selected)
        self._write_feed("subscriptions/reachable", reachable)
        self._write_feed("subscriptions/reachable-fast", fast)
        for protocol, items in protocol_configs.items():
            self._write_feed(f"subscriptions/all-{protocol}", items)
            self._write_feed(f"subscriptions/reachable-{protocol}", items)
        self.artifact_store.write_atomic("subscriptions/all.manifest.v1.json", manifest_bytes)
        self.artifact_store.write_atomic("subscriptions/reachable.manifest.v1.json", manifest_bytes)
        self.artifact_store.write_atomic("reachable-latest.txt", f"{snapshot_id}\n".encode("utf-8"))
        return ReachablePublishReport(True, len(selected), snapshot_id=snapshot_id)

    def _write_feed(self, stem: str, configs: Iterable[CanonicalConfig]) -> None:
        content = _content(configs)
        self.artifact_store.write_atomic(f"{stem}.txt", content)
        self.artifact_store.write_atomic(f"{stem}.base64", base64.b64encode(content))


def _deduplicate_preserving_order(configs: Iterable[CanonicalConfig]) -> list[CanonicalConfig]:
    seen: set[str] = set()
    selected: list[CanonicalConfig] = []
    for config in configs:
        if not config.identity_hash or config.identity_hash in seen:
            continue
        seen.add(config.identity_hash)
        selected.append(config)
    return selected


def _prioritize_protocols(
    configs: Iterable[CanonicalConfig], protocol_order: tuple[str, ...]
) -> list[CanonicalConfig]:
    priority = {protocol: index for index, protocol in enumerate(protocol_order)}
    indexed = list(enumerate(configs))
    return [
        config
        for _, config in sorted(
            indexed,
            key=lambda item: (priority.get(item[1].protocol.value, len(priority)), item[0]),
        )
    ]


def _content(configs: Iterable[CanonicalConfig]) -> bytes:
    values = [config.raw_uri for config in configs]
    return (("\n".join(values) + "\n") if values else "").encode("utf-8")
