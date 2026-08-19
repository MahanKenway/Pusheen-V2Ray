"""Parsers for VMess and Shadowsocks URI formats."""

from __future__ import annotations

import base64
import json
from urllib.parse import unquote, urlsplit

from kaveh.adapters.protocols.base import ParseError
from kaveh.domain.models import CanonicalConfig, Protocol, Transport
from kaveh.domain.services.identity import with_identity


def decode_base64(value: str) -> str:
    """Decode padded or unpadded Base64 text as UTF-8."""

    try:
        padded = value.strip() + "=" * (-len(value.strip()) % 4)
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ParseError("INVALID_BASE64", "Encoded payload is invalid") from exc


class VmessParser:
    scheme = "vmess"

    def parse(self, raw_uri: str, source_id: str | None = None) -> CanonicalConfig:
        if not raw_uri.lower().startswith("vmess://"):
            raise ParseError("SCHEME_MISMATCH", "URI scheme does not match parser")
        try:
            payload = json.loads(decode_base64(raw_uri[8:]))
            host = str(payload["add"]).strip()
            port = int(payload["port"])
            credential = str(payload["id"]).strip()
        except KeyError as exc:
            raise ParseError("MISSING_FIELD", "VMess payload is missing a required field") from exc
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ParseError("INVALID_VMESS", "VMess payload is malformed") from exc
        if not host or not credential or not 1 <= port <= 65535:
            raise ParseError("INVALID_VMESS", "VMess endpoint or credential is invalid")
        transport = Transport(
            network=str(payload.get("net") or "tcp"),
            security=str(payload.get("tls") or "none"),
            server_name=str(payload.get("sni") or payload.get("host") or "") or None,
            path=str(payload.get("path") or "") or None,
            service_name=str(payload.get("serviceName") or "") or None,
            extra={
                key: str(value)
                for key, value in payload.items()
                if key
                not in {
                    "v", "ps", "add", "port", "id", "net", "type",
                    "host", "path", "tls", "sni", "alpn", "fp", "serviceName",
                }
                and value not in (None, "")
            },
        )
        config = CanonicalConfig(
            protocol=Protocol.VMESS,
            host=host,
            port=port,
            credential=credential,
            transport=transport,
            label=str(payload.get("ps") or "") or None,
            raw_uri=raw_uri.strip(),
            source_id=source_id,
        )
        return with_identity(config)


class ShadowsocksParser:
    scheme = "ss"

    def parse(self, raw_uri: str, source_id: str | None = None) -> CanonicalConfig:
        if not raw_uri.lower().startswith("ss://"):
            raise ParseError("SCHEME_MISMATCH", "URI scheme does not match parser")
        without_scheme = raw_uri[5:].strip()
        parsed = urlsplit(raw_uri)
        try:
            if parsed.hostname and parsed.port is not None and parsed.username:
                credential = unquote(parsed.username)
                host = parsed.hostname
                port = parsed.port
            else:
                decoded = decode_base64(without_scheme.split("#", 1)[0].split("?", 1)[0])
                parsed = urlsplit(f"ss://{decoded}")
                if not parsed.hostname or parsed.port is None or not parsed.username:
                    raise ParseError("INVALID_SHADOWSOCKS", "Shadowsocks URI is incomplete")
                credential = unquote(parsed.username)
                host = parsed.hostname
                port = parsed.port
        except ValueError as exc:
            raise ParseError("INVALID_SHADOWSOCKS", "Shadowsocks endpoint is invalid") from exc
        if ":" not in credential:
            raise ParseError("INVALID_SHADOWSOCKS", "Shadowsocks method and password are required")
        config = CanonicalConfig(
            protocol=Protocol.SHADOWSOCKS,
            host=host,
            port=port,
            credential=credential,
            transport=Transport(),
            label=unquote(parsed.fragment) or None,
            raw_uri=raw_uri.strip(),
            source_id=source_id,
        )
        return with_identity(config)
