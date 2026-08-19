"""Protocol parser contract and safe parse errors."""

from __future__ import annotations

from typing import Protocol

from kaveh.domain.models import CanonicalConfig


class ParseError(ValueError):
    """Raised for malformed or unsupported input without echoing raw secrets."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ConfigParser(Protocol):
    scheme: str

    def parse(self, raw_uri: str, source_id: str | None = None) -> CanonicalConfig:
        """Convert one supported URI into a typed canonical configuration."""
