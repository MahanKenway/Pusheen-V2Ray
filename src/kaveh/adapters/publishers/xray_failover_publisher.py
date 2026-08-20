"""Validated Xray client profile with local least-ping failover.

The profile contains only the already evidence-backed members selected for the
resilient feed. Xray's local Observatory continues measurements on the user's
network and the routing balancer chooses the lowest observed latency. A block
fallback is deliberate: a failed proxy pool must not silently leak traffic
through a direct outbound.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from kaveh.adapters.runtime.xray_adapter import XrayBuildError, XrayConfigBuilder
from kaveh.domain.models import CanonicalConfig
from kaveh.domain.ports import ArtifactStore


@dataclass(frozen=True)
class XrayFailoverPublishReport:
    published: bool
    count: int
    artifact_hash: str | None = None
    reason: str | None = None


class XrayFailoverPublisher:
    """Publish a schema-ready local SOCKS Xray profile for resilient members."""

    profile_path = "profiles/resilient-xray.json"
    metadata_path = "profiles/resilient-xray.meta.v1.json"
    probe_url = "https://connectivitycheck.gstatic.com/generate_204"

    def __init__(self, artifact_store: ArtifactStore, builder: XrayConfigBuilder | None = None) -> None:
        self.artifact_store = artifact_store
        self.builder = builder or XrayConfigBuilder()

    def publish(self, configs: Iterable[CanonicalConfig]) -> XrayFailoverPublishReport:
        outbounds: list[dict[str, object]] = []
        rejected = 0
        for config in configs:
            if not config.identity_hash:
                rejected += 1
                continue
            try:
                tag = f"resilient-{config.identity_hash[:16]}"
                outbounds.append(self.builder.build_outbound(config, tag))
            except XrayBuildError:
                rejected += 1
        if not outbounds:
            return XrayFailoverPublishReport(False, 0, reason="NO_XRAY_COMPATIBLE_RESILIENT_CONFIGS")

        profile = {
            "version": {"min": "26.3.27"},
            "log": {"loglevel": "warning"},
            "inbounds": [
                {
                    "tag": "resilient-local-socks",
                    "listen": "127.0.0.1",
                    "port": 10808,
                    "protocol": "socks",
                    "settings": {"auth": "noauth", "udp": True},
                }
            ],
            "outbounds": outbounds + [{"tag": "blocked", "protocol": "blackhole", "settings": {}}],
            "observatory": {
                "subjectSelector": ["resilient-"],
                "probeUrl": self.probe_url,
                "probeInterval": "5m",
                "enableConcurrency": True,
            },
            "routing": {
                "domainStrategy": "AsIs",
                "rules": [
                    {
                        "type": "field",
                        "inboundTag": ["resilient-local-socks"],
                        "balancerTag": "resilient-auto",
                    }
                ],
                "balancers": [
                    {
                        "tag": "resilient-auto",
                        "selector": ["resilient-"],
                        "fallbackTag": "blocked",
                        "strategy": {"type": "leastPing"},
                    }
                ],
            },
        }
        content = (json.dumps(profile, sort_keys=True, indent=2) + "\n").encode("utf-8")
        artifact_hash = hashlib.sha256(content).hexdigest()
        read_bytes = getattr(self.artifact_store, "read_bytes", None)
        if callable(read_bytes) and read_bytes(self.profile_path) == content:
            return XrayFailoverPublishReport(
                False, len(outbounds), artifact_hash=artifact_hash, reason="NO_FAILOVER_PROFILE_CHANGE"
            )

        metadata = {
            "schema_version": 1,
            "profile_path": self.profile_path,
            "artifact_hash": artifact_hash,
            "outbound_count": len(outbounds),
            "rejected_count": rejected,
            "selection": "resilient TCP-evidence members only",
            "runtime": "Xray Core >= 26.3.27",
            "local_behavior": "leastPing via Observatory every 5m; blocked fallback prevents direct traffic escape",
            "notice": "The local client retests from its own network; upstream publication evidence is not an availability guarantee.",
        }
        self.artifact_store.write_atomic(self.profile_path, content)
        self.artifact_store.write_atomic(
            self.metadata_path, (json.dumps(metadata, sort_keys=True, indent=2) + "\n").encode("utf-8")
        )
        return XrayFailoverPublishReport(True, len(outbounds), artifact_hash=artifact_hash)
