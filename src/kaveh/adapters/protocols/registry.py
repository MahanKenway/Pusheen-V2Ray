"""Registry that dispatches supported URI schemes to typed parsers."""

from __future__ import annotations

from kaveh.adapters.protocols.base import ConfigParser, ParseError
from kaveh.adapters.protocols.encoded import ShadowsocksParser, VmessParser
from kaveh.adapters.protocols.standard import Hy2Parser, Hysteria2Parser, TrojanParser, TuicParser, VlessParser
from kaveh.domain.models import CanonicalConfig


class ParserRegistry:
    """Single extension point for protocol support."""

    def __init__(self, parsers: list[ConfigParser] | None = None) -> None:
        active = parsers or [
            VlessParser(),
            VmessParser(),
            TrojanParser(),
            ShadowsocksParser(),
            Hysteria2Parser(),
            Hy2Parser(),
            TuicParser(),
        ]
        self._parsers = {parser.scheme: parser for parser in active}

    @property
    def schemes(self) -> frozenset[str]:
        return frozenset(self._parsers)

    def parse(self, raw_uri: str, source_id: str | None = None) -> CanonicalConfig:
        scheme = raw_uri.partition("://")[0].lower()
        parser = self._parsers.get(scheme)
        if parser is None:
            raise ParseError("UNSUPPORTED_PROTOCOL", "URI protocol is not enabled")
        return parser.parse(raw_uri, source_id=source_id)
