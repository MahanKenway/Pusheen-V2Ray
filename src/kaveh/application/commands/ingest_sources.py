"""Ingestion use case: fetch, normalize, parse, and deduplicate sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from kaveh.adapters.protocols.base import ParseError
from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.adapters.subscriptions.lines import normalize_lines
from kaveh.domain.models import Source
from kaveh.domain.ports import ConfigRepository, SourceClient
from kaveh.infrastructure.http.http_source_client import SourceFetchError


@dataclass(frozen=True)
class SourceIngestionStats:
    """Safe per-source counts used for operational health, never raw URI logging."""

    discovered_count: int = 0
    parsed_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    error_code: str | None = None

    @property
    def accepted_count(self) -> int:
        return self.parsed_count + self.duplicate_count


@dataclass(frozen=True)
class IngestionReport:
    discovered_count: int
    parsed_count: int
    duplicate_count: int
    rejected_count: int
    source_errors: dict[str, str] = field(default_factory=dict)
    rejection_codes: dict[str, int] = field(default_factory=dict)
    source_stats: dict[str, SourceIngestionStats] = field(default_factory=dict)


class IngestSources:
    """The single application command that owns the ingress pipeline."""

    def __init__(
        self,
        source_client: SourceClient,
        parser_registry: ParserRegistry,
        repository: ConfigRepository,
    ) -> None:
        self.source_client = source_client
        self.parser_registry = parser_registry
        self.repository = repository

    def run(self, sources: Iterable[Source]) -> IngestionReport:
        discovered = parsed = duplicates = rejected = 0
        source_errors: dict[str, str] = {}
        rejection_codes: dict[str, int] = {}
        source_stats: dict[str, SourceIngestionStats] = {}

        for source in sources:
            register_source = getattr(self.repository, "upsert_source", None)
            if callable(register_source):
                register_source(source)
            if not source.enabled:
                continue
            source_discovered = source_parsed = source_duplicates = source_rejected = 0
            try:
                content = self.source_client.fetch(source)
            except SourceFetchError as exc:
                source_errors[source.source_id] = exc.code
                source_stats[source.source_id] = SourceIngestionStats(error_code=exc.code)
                continue
            for raw_uri in normalize_lines(content, max_lines=source.max_entries):
                discovered += 1
                source_discovered += 1
                try:
                    config = self.parser_registry.parse(raw_uri, source_id=source.source_id)
                    if config.protocol not in source.allowed_protocols:
                        raise ParseError(
                            "PROTOCOL_NOT_ALLOWED",
                            "Source policy does not permit this protocol",
                        )
                except ParseError as exc:
                    rejected += 1
                    source_rejected += 1
                    rejection_codes[exc.code] = rejection_codes.get(exc.code, 0) + 1
                    continue
                if self.repository.upsert(config):
                    parsed += 1
                    source_parsed += 1
                else:
                    duplicates += 1
                    source_duplicates += 1
            source_stats[source.source_id] = SourceIngestionStats(
                discovered_count=source_discovered,
                parsed_count=source_parsed,
                duplicate_count=source_duplicates,
                rejected_count=source_rejected,
            )

        return IngestionReport(
            discovered_count=discovered,
            parsed_count=parsed,
            duplicate_count=duplicates,
            rejected_count=rejected,
            source_errors=source_errors,
            rejection_codes=rejection_codes,
            source_stats=source_stats,
        )
