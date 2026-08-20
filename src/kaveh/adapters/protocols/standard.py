"""Parsers for VLESS and Trojan URI formats."""

from __future__ import annotations

from dataclasses import replace
import uuid
from urllib.parse import parse_qs, unquote, urlsplit

from kaveh.adapters.protocols.base import ParseError
from kaveh.domain.models import CanonicalConfig, Protocol, Transport
from kaveh.domain.services.identity import with_identity


class StandardUriParser:
    """Shared parser for URI schemes with credentials in userinfo."""

    def __init__(self, scheme: str, protocol: Protocol) -> None:
        self.scheme = scheme
        self.protocol = protocol

    def parse(self, raw_uri: str, source_id: str | None = None) -> CanonicalConfig:
        try:
            parsed = urlsplit(raw_uri)
            if parsed.scheme.lower() != self.scheme:
                raise ParseError("SCHEME_MISMATCH", "URI scheme does not match parser")
            if not parsed.hostname:
                raise ParseError("MISSING_HOST", "URI does not contain a host")
            if parsed.port is None:
                raise ParseError("MISSING_PORT", "URI does not contain a port")
            if not parsed.username:
                raise ParseError("MISSING_CREDENTIAL", "URI does not contain credentials")
        except ValueError as exc:
            raise ParseError("INVALID_URI", "URI authority or port is invalid") from exc

        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        known_keys = {
            "type",
            "security",
            "sni",
            "host",
            "path",
            "serviceName",
            "servicename",
        }
        transport = Transport(
            network=query.get("type", "tcp"),
            security=query.get("security", "none"),
            server_name=query.get("sni") or query.get("host"),
            path=query.get("path"),
            service_name=query.get("serviceName") or query.get("servicename"),
            extra={key: value for key, value in query.items() if key not in known_keys},
        )
        label = unquote(parsed.fragment) or None
        config = CanonicalConfig(
            protocol=self.protocol,
            host=parsed.hostname,
            port=parsed.port,
            credential=unquote(parsed.username),
            transport=transport,
            label=label,
            raw_uri=raw_uri.strip(),
            source_id=source_id,
        )
        return with_identity(config)


class VlessParser(StandardUriParser):
    def __init__(self) -> None:
        super().__init__("vless", Protocol.VLESS)


class TrojanParser(StandardUriParser):
    def __init__(self) -> None:
        super().__init__("trojan", Protocol.TROJAN)


class Hysteria2Parser:
    """Parse the official compact URI form for Hysteria 2.

    Realm and multi-port forms are intentionally rejected for now: both need a
    richer canonical model and an isolated runtime test before they can claim
    publishable end-to-end evidence.
    """

    def __init__(self, scheme: str = "hysteria2") -> None:
        self.scheme = scheme

    def parse(self, raw_uri: str, source_id: str | None = None) -> CanonicalConfig:
        try:
            parsed = urlsplit(raw_uri)
            if parsed.scheme.lower() != self.scheme:
                raise ParseError("SCHEME_MISMATCH", "URI scheme does not match parser")
            if not parsed.hostname:
                raise ParseError("MISSING_HOST", "URI does not contain a host")
            if not parsed.username:
                raise ParseError("MISSING_CREDENTIAL", "URI does not contain credentials")
            port = parsed.port or 443
        except ValueError as exc:
            raise ParseError("INVALID_URI", "URI authority or port is invalid") from exc

        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        known_keys = {"obfs", "obfs-password", "sni", "insecure", "pinSHA256", "ech"}
        transport = Transport(
            network="hysteria",
            security="tls",
            server_name=query.get("sni"),
            extra={key: value for key, value in query.items() if key not in known_keys}
            | {key: value for key, value in query.items() if key in known_keys},
        )
        config = CanonicalConfig(
            protocol=Protocol.HYSTERIA2,
            host=parsed.hostname,
            port=port,
            credential=unquote(parsed.username),
            transport=transport,
            label=unquote(parsed.fragment) or None,
            raw_uri=raw_uri.strip(),
            source_id=source_id,
        )
        return with_identity(config)


class TuicParser:
    """Parse the widely implemented TUIC v5 share-URI convention.

    The TUIC wire protocol has no normative share-URI specification.  This
    parser therefore accepts only the UUID+password v5 form used by multiple
    client implementations and rejects certificate-verification bypasses.
    """

    scheme = "tuic"

    def parse(self, raw_uri: str, source_id: str | None = None) -> CanonicalConfig:
        try:
            parsed = urlsplit(raw_uri)
            if parsed.scheme.lower() != "tuic":
                raise ParseError("SCHEME_MISMATCH", "URI scheme does not match parser")
            if not parsed.hostname or parsed.port is None:
                raise ParseError("MISSING_ENDPOINT", "TUIC URI requires host and port")
            if not parsed.username or parsed.password is None:
                raise ParseError("MISSING_CREDENTIAL", "TUIC URI requires UUID and password")
        except ValueError as exc:
            raise ParseError("INVALID_URI", "URI authority or port is invalid") from exc
        try:
            user_uuid = str(uuid.UUID(unquote(parsed.username)))
        except ValueError as exc:
            raise ParseError("TUIC_UUID_INVALID", "TUIC URI UUID is invalid") from exc
        password = unquote(parsed.password)
        if not password:
            raise ParseError("MISSING_CREDENTIAL", "TUIC password is empty")
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        if query.get("insecure", "").lower() in {"1", "true", "yes"}:
            raise ParseError("INSECURE_TLS_FORBIDDEN", "TUIC must verify TLS certificates")
        allowed = {
            "congestion_control",
            "udp_relay_mode",
            "udp_over_stream",
            "zero_rtt_handshake",
            "heartbeat",
            "network",
            "sni",
            "alpn",
            "ech",
        }
        extra = {key: value for key, value in query.items() if key in allowed and key not in {"sni", "alpn"}}
        if query.get("alpn"):
            extra["alpn"] = query["alpn"]
        config = CanonicalConfig(
            protocol=Protocol.TUIC,
            host=parsed.hostname,
            port=parsed.port,
            credential=f"{user_uuid}:{password}",
            transport=Transport(
                network=query.get("network", "udp"),
                security="tls",
                server_name=query.get("sni"),
                extra=extra,
            ),
            label=unquote(parsed.fragment) or None,
            raw_uri=raw_uri.strip(),
            source_id=source_id,
        )
        return with_identity(config)


class Hy2Parser(Hysteria2Parser):
    def __init__(self) -> None:
        super().__init__("hy2")
