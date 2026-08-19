"""Offline schema validation for canonical configurations."""

from __future__ import annotations

from kaveh.domain.models import CanonicalConfig, ProbeResult, ProbeStage


class SchemaProbe:
    """Reject impossible configuration shapes before any network activity."""

    allowed_networks = frozenset({"tcp", "ws", "grpc", "httpupgrade", "h2", "kcp", "quic"})
    allowed_security = frozenset({"none", "tls", "reality", "xtls"})

    def run(self, config: CanonicalConfig) -> ProbeResult:
        if not config.identity_hash:
            return ProbeResult.failed("unknown", ProbeStage.SCHEMA, "MISSING_IDENTITY")
        if not config.host or len(config.host) > 253:
            return ProbeResult.failed(config.identity_hash, ProbeStage.SCHEMA, "INVALID_HOST")
        if not 1 <= config.port <= 65535:
            return ProbeResult.failed(config.identity_hash, ProbeStage.SCHEMA, "INVALID_PORT")
        if not config.credential:
            return ProbeResult.failed(config.identity_hash, ProbeStage.SCHEMA, "MISSING_CREDENTIAL")
        if config.transport.network.lower() not in self.allowed_networks:
            return ProbeResult.failed(config.identity_hash, ProbeStage.SCHEMA, "UNSUPPORTED_NETWORK")
        if config.transport.security.lower() not in self.allowed_security:
            return ProbeResult.failed(config.identity_hash, ProbeStage.SCHEMA, "UNSUPPORTED_SECURITY")
        if config.transport.security.lower() == "reality" and not config.transport.server_name:
            return ProbeResult.failed(config.identity_hash, ProbeStage.SCHEMA, "REALITY_SNI_REQUIRED")
        return ProbeResult.passed(config.identity_hash, ProbeStage.SCHEMA)
