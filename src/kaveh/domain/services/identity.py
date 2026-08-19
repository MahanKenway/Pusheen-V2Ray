"""Stable, privacy-aware identities for canonical configurations."""

from __future__ import annotations

import hashlib
import json

from kaveh.domain.models import CanonicalConfig, Transport


def _transport_payload(transport: Transport) -> dict[str, object]:
    return {
        "network": transport.network,
        "security": transport.security,
        "server_name": transport.server_name,
        "path": transport.path,
        "service_name": transport.service_name,
        "extra": dict(sorted(transport.extra.items())),
    }


def identity_payload(config: CanonicalConfig) -> dict[str, object]:
    """Return fields that change a connection's operational identity.

    Labels and sources deliberately do not participate in identity; they are
    observations of the same connection, not separate connections.
    """

    return {
        "protocol": config.protocol.value,
        "host": config.host.strip().lower(),
        "port": config.port,
        "credential": config.credential,
        "transport": _transport_payload(config.transport),
    }


def config_identity(config: CanonicalConfig) -> str:
    """Return a SHA-256 identity hash for dedupe and history joins."""

    serialized = json.dumps(
        identity_payload(config), separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def with_identity(config: CanonicalConfig) -> CanonicalConfig:
    """Return the config with its identity populated."""

    from dataclasses import replace

    return replace(config, identity_hash=config_identity(config))
