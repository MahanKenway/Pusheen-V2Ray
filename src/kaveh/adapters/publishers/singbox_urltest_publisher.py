"""Client-side sing-box URLTest profile for the outage-diverse tier."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from kaveh.domain.models import CanonicalConfig, Protocol
from kaveh.domain.ports import ArtifactStore


@dataclass(frozen=True)
class SingBoxUrlTestPublishReport:
    published: bool
    count: int
    artifact_hash: str | None = None
    reason: str | None = None
    rejected_count: int = 0


class SingBoxUrlTestPublisher:
    """Build a schema-checkable, local-only URLTest profile from outage members.

    The profile is an opt-in client artifact. It does not promote sing-box's
    locally observed health test to pipeline evidence and it never installs a
    direct outbound fallback.
    """

    profile_path = "profiles/outage-singbox.json"
    metadata_path = "profiles/outage-singbox.meta.v1.json"
    probe_url = "https://www.gstatic.com/generate_204"
    compatible_protocols = frozenset({Protocol.VLESS, Protocol.VMESS, Protocol.TROJAN})

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store

    def publish(self, configs: Iterable[CanonicalConfig]) -> SingBoxUrlTestPublishReport:
        outbounds: list[dict[str, Any]] = []
        rejected: Counter[str] = Counter()
        for config in configs:
            try:
                outbound = self._build_outbound(config)
            except SingBoxProfileBuildError as exc:
                rejected[str(exc)] += 1
                continue
            outbounds.append(outbound)
        if not outbounds:
            return SingBoxUrlTestPublishReport(
                False, 0, reason="NO_SINGBOX_COMPATIBLE_OUTAGE_CONFIGS", rejected_count=sum(rejected.values())
            )

        tags = [str(item["tag"]) for item in outbounds]
        profile = {
            "log": {"disabled": True},
            "inbounds": [
                {
                    "type": "socks",
                    "tag": "outage-local-socks",
                    "listen": "127.0.0.1",
                    "listen_port": 10809,
                    "users": [],
                }
            ],
            "outbounds": outbounds
            + [
                {
                    "type": "urltest",
                    "tag": "outage-auto",
                    "outbounds": tags,
                    "url": self.probe_url,
                    "interval": "10m",
                    "tolerance": 200,
                    "idle_timeout": "30m",
                    "interrupt_exist_connections": False,
                },
                {"type": "block", "tag": "blocked"},
            ],
            "route": {
                "rules": [
                    {"inbound": ["outage-local-socks"], "outbound": "outage-auto"}
                ],
                "final": "blocked",
            },
        }
        content = (json.dumps(profile, sort_keys=True, indent=2) + "\n").encode("utf-8")
        artifact_hash = hashlib.sha256(content).hexdigest()
        read_bytes = getattr(self.artifact_store, "read_bytes", None)
        if callable(read_bytes) and read_bytes(self.profile_path) == content:
            return SingBoxUrlTestPublishReport(
                False,
                len(outbounds),
                artifact_hash=artifact_hash,
                reason="NO_SINGBOX_URLTEST_PROFILE_CHANGE",
                rejected_count=sum(rejected.values()),
            )
        metadata = {
            "schema_version": 1,
            "profile_path": self.profile_path,
            "artifact_hash": artifact_hash,
            "outbound_count": len(outbounds),
            "rejected_count": sum(rejected.values()),
            "rejected_by_reason": dict(sorted(rejected.items())),
            "selection": "outage-diverse TCP-evidence members only",
            "runtime": "sing-box >= 1.13.19",
            "local_behavior": (
                "URLTest probes from the client network every 10m with 200ms tolerance; "
                "no direct fallback is present."
            ),
            "notice": (
                "Local URLTest observations are not pipeline evidence and do not guarantee "
                "availability from another network."
            ),
        }
        self.artifact_store.write_atomic(self.profile_path, content)
        self.artifact_store.write_atomic(
            self.metadata_path, (json.dumps(metadata, sort_keys=True, indent=2) + "\n").encode("utf-8")
        )
        return SingBoxUrlTestPublishReport(
            True, len(outbounds), artifact_hash=artifact_hash, rejected_count=sum(rejected.values())
        )

    def _build_outbound(self, config: CanonicalConfig) -> dict[str, Any]:
        if not config.identity_hash:
            raise SingBoxProfileBuildError("IDENTITY_MISSING")
        if config.protocol not in self.compatible_protocols:
            raise SingBoxProfileBuildError("PROTOCOL_UNSUPPORTED")
        transport = config.transport
        if transport.network not in {"tcp", "ws"}:
            raise SingBoxProfileBuildError("TRANSPORT_UNSUPPORTED")
        if transport.security not in {"none", "tls"}:
            raise SingBoxProfileBuildError("SECURITY_UNSUPPORTED")
        if transport.extra.get("insecure", "").lower() in {"1", "true", "yes"}:
            raise SingBoxProfileBuildError("INSECURE_TLS_FORBIDDEN")

        outbound: dict[str, Any] = {
            "type": config.protocol.value,
            "tag": f"outage-{config.identity_hash[:16]}",
            "server": config.host,
            "server_port": config.port,
            "network": "tcp",
        }
        if config.protocol is Protocol.VLESS:
            outbound["uuid"] = config.credential
            flow = transport.extra.get("flow")
            if flow:
                outbound["flow"] = flow
        elif config.protocol is Protocol.VMESS:
            outbound["uuid"] = config.credential
            outbound["security"] = transport.extra.get("scy", "auto")
            outbound["alter_id"] = _integer_or_default(transport.extra.get("aid"), 0)
        else:
            outbound["password"] = config.credential

        if transport.security == "tls":
            tls: dict[str, Any] = {"enabled": True}
            if transport.server_name:
                tls["server_name"] = transport.server_name
            outbound["tls"] = tls
        if transport.network == "ws":
            websocket: dict[str, Any] = {"type": "ws", "path": transport.path or "/"}
            # Canonical transport retains a single server_name field. Supplying it
            # as the WS host header preserves common IP+host share URI behavior;
            # the binary schema-check remains mandatory before publication.
            if transport.server_name:
                websocket["headers"] = {"Host": transport.server_name}
            outbound["transport"] = websocket
        return outbound


class SingBoxProfileBuildError(ValueError):
    pass


def _integer_or_default(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default
