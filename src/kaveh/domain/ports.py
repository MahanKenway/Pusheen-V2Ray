"""Ports implemented by infrastructure adapters."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol as TypingProtocol

from kaveh.domain.models import CanonicalConfig, ProbeResult, Source


class SourceClient(TypingProtocol):
    def fetch(self, source: Source) -> str:
        """Fetch a source after enforcing its transport policy."""


class ConfigRepository(TypingProtocol):
    def upsert(self, config: CanonicalConfig) -> bool:
        """Store a canonical config; return True only if it is newly observed."""

    def get(self, identity_hash: str) -> CanonicalConfig | None:
        """Return a configuration by identity."""

    def all(self) -> Iterable[CanonicalConfig]:
        """Yield all stored configurations."""


class ProbeRunner(TypingProtocol):
    def run(self, config: CanonicalConfig) -> Iterable[ProbeResult]:
        """Run one or more deterministic validation stages."""


class ArtifactStore(TypingProtocol):
    def write_atomic(self, relative_path: str, content: bytes) -> str:
        """Write an artifact atomically and return its SHA-256 hash."""

    def switch_latest(self, snapshot_id: str) -> None:
        """Point the public latest reference to a fully written snapshot."""
