"""Strict v1 JSON profile ingestion for protocols without stable share URIs.

The profile container is deliberately separate from URI subscriptions.  It is an
internal reviewed-source contract and its raw JSON is retained only for the
runtime adapter; it is never a client-facing subscription representation.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from kaveh.adapters.protocols.base import ParseError
from kaveh.domain.models import CanonicalConfig, Protocol, Transport
from kaveh.domain.services.identity import with_identity

_HOST = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")
_TUIC_CONGESTION = frozenset({"cubic", "new_reno", "bbr"})
_NAIVE_QUIC_CONGESTION = frozenset({"bbr", "bbr2", "cubic", "reno"})


@dataclass(frozen=True)
class StructuredProfileBatch:
    """A parsed profile set and safe per-item rejection codes."""

    configs: tuple[CanonicalConfig, ...]
    rejection_codes: tuple[str, ...]


def parse_json_profiles(content: str, source_id: str, max_entries: int) -> StructuredProfileBatch:
    """Parse the Kaveh v1 JSON profile container.

    Expected container: ``{"version": 1, "profiles": [{...}]}``.  Each
    profile must be an explicit ``tuic`` or ``naive`` object. TLS certificate
    verification is mandatory; an insecure profile is rejected rather than
    silently weakening the validator.
    """

    try:
        document = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ParseError("PROFILE_JSON_INVALID", "Profile source is not valid JSON") from exc
    if not isinstance(document, Mapping) or document.get("version") != 1:
        raise ParseError("PROFILE_SCHEMA_INVALID", "Profile source must use version 1")
    profiles = document.get("profiles")
    if not isinstance(profiles, list):
        raise ParseError("PROFILE_SCHEMA_INVALID", "Profile source must contain a profiles list")

    configs: list[CanonicalConfig] = []
    rejections: list[str] = []
    for profile in profiles[:max_entries]:
        try:
            configs.append(_parse_profile(profile, source_id))
        except ParseError as exc:
            rejections.append(exc.code)
    return StructuredProfileBatch(tuple(configs), tuple(rejections))


def _parse_profile(value: object, source_id: str) -> CanonicalConfig:
    if not isinstance(value, Mapping):
        raise ParseError("PROFILE_ENTRY_INVALID", "Profile entry must be an object")
    try:
        protocol = Protocol(str(value["protocol"]))
    except (KeyError, ValueError) as exc:
        raise ParseError("PROFILE_PROTOCOL_INVALID", "Profile protocol is unsupported") from exc
    if protocol not in {Protocol.TUIC, Protocol.NAIVE}:
        raise ParseError("PROFILE_PROTOCOL_INVALID", "Profile protocol is unsupported")

    host = _required_text(value, "server")
    if not _HOST.fullmatch(host) or ".." in host:
        raise ParseError("PROFILE_SERVER_INVALID", "Profile server is invalid")
    try:
        port = int(value["server_port"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ParseError("PROFILE_PORT_INVALID", "Profile server port is invalid") from exc
    if not 1 <= port <= 65535:
        raise ParseError("PROFILE_PORT_INVALID", "Profile server port is invalid")

    tls = value.get("tls")
    if not isinstance(tls, Mapping) or tls.get("insecure"):
        raise ParseError("PROFILE_TLS_INVALID", "Verified TLS configuration is required")
    server_name = tls.get("server_name")
    if server_name is not None and (not isinstance(server_name, str) or not _HOST.fullmatch(server_name)):
        raise ParseError("PROFILE_TLS_INVALID", "TLS server name is invalid")

    if protocol is Protocol.TUIC:
        credential, extra = _tuic_fields(value)
        network = extra.pop("network", "udp")
    else:
        credential, extra = _naive_fields(value)
        network = "udp" if extra.get("quic") == "true" else "tcp"

    raw_profile = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return with_identity(
        CanonicalConfig(
            protocol=protocol,
            host=host.lower(),
            port=port,
            credential=credential,
            transport=Transport(network=network, security="tls", server_name=server_name, extra=extra),
            label=_optional_text(value.get("label")),
            raw_uri=f"profile-json://{raw_profile}",
            source_id=source_id,
        )
    )


def _tuic_fields(value: Mapping[str, Any]) -> tuple[str, dict[str, str]]:
    raw_uuid = _required_text(value, "uuid")
    try:
        user_uuid = str(uuid.UUID(raw_uuid))
    except ValueError as exc:
        raise ParseError("PROFILE_TUIC_UUID_INVALID", "TUIC UUID is invalid") from exc
    password = _required_text(value, "password")
    extra = _permitted_text_fields(
        value,
        allowed={"congestion_control", "udp_relay_mode", "heartbeat", "network"},
    )
    if congestion := extra.get("congestion_control"):
        if congestion not in _TUIC_CONGESTION:
            raise ParseError("PROFILE_TUIC_CONGESTION_INVALID", "TUIC congestion control is invalid")
    if extra.get("udp_relay_mode") not in {None, "native", "quic"}:
        raise ParseError("PROFILE_TUIC_UDP_MODE_INVALID", "TUIC UDP relay mode is invalid")
    if extra.get("network") not in {None, "tcp", "udp"}:
        raise ParseError("PROFILE_TUIC_NETWORK_INVALID", "TUIC network is invalid")
    for name in ("udp_over_stream", "zero_rtt_handshake"):
        if name in value:
            if not isinstance(value[name], bool):
                raise ParseError("PROFILE_TUIC_BOOLEAN_INVALID", "TUIC Boolean field is invalid")
            extra[name] = str(value[name]).lower()
    if extra.get("udp_relay_mode") and extra.get("udp_over_stream") == "true":
        raise ParseError("PROFILE_TUIC_UDP_MODE_CONFLICT", "TUIC UDP settings conflict")
    return f"{user_uuid}:{password}", extra


def _naive_fields(value: Mapping[str, Any]) -> tuple[str, dict[str, str]]:
    username = _required_text(value, "username")
    password = _required_text(value, "password")
    extra = _permitted_text_fields(value, allowed={"quic_congestion_control", "insecure_concurrency"})
    if "quic" in value:
        if not isinstance(value["quic"], bool):
            raise ParseError("PROFILE_NAIVE_BOOLEAN_INVALID", "Naive QUIC field is invalid")
        extra["quic"] = str(value["quic"]).lower()
    if congestion := extra.get("quic_congestion_control"):
        if congestion not in _NAIVE_QUIC_CONGESTION:
            raise ParseError("PROFILE_NAIVE_CONGESTION_INVALID", "Naive QUIC congestion control is invalid")
    if raw_concurrency := extra.get("insecure_concurrency"):
        try:
            concurrency = int(raw_concurrency)
        except ValueError as exc:
            raise ParseError("PROFILE_NAIVE_CONCURRENCY_INVALID", "Naive concurrency is invalid") from exc
        if not 0 <= concurrency <= 4:
            raise ParseError("PROFILE_NAIVE_CONCURRENCY_INVALID", "Naive concurrency is outside policy")
    return f"{username}:{password}", extra


def _permitted_text_fields(value: Mapping[str, Any], allowed: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in allowed:
        if name not in value:
            continue
        field = value[name]
        if not isinstance(field, (str, int)) or isinstance(field, bool) or not str(field):
            raise ParseError("PROFILE_FIELD_INVALID", "Profile field is invalid")
        result[name] = str(field)
    return result


def _required_text(value: Mapping[str, Any], name: str) -> str:
    field = value.get(name)
    if not isinstance(field, str) or not field or len(field) > 1024:
        raise ParseError("PROFILE_FIELD_REQUIRED", "Required profile field is missing")
    return field


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 256:
        return None
    return value
