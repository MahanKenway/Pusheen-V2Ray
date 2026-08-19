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
class IngestionReport:
    discovered_count: int
    parsed_count: int
    duplicate_count: int
    rejected_count: int
    source_errors: dict[str, str] = field(default_factory=dict)
    rejection_codes: dict[str, int] = field(default_factory=dict)


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

        for source in sources:
            if not source.enabled:
                continue
            try:
                content = self.source_client.fetch(source)
            except SourceFetchError as exc:
                source_errors[source.source_id] = exc.code
                continue
            for raw_uri in normalize_lines(content):
                discovered += 1
                try:
                    config = self.parser_registry.parse(raw_uri, source_id=source.source_id)
                    if config.protocol not in source.allowed_protocols:
                        raise ParseError(
                            "PROTOCOL_NOT_ALLOWED",
                            "Source policy does not permit this protocol",
                        )
                except ParseError as exc:
                    rejected += 1
                    rejection_codes[exc.code] = rejection_codes.get(exc.code, 0) + 1
                    continue
                if self.repository.upsert(config):
                    parsed += 1
                else:
                    duplicates += 1

        return IngestionReport(
            discovered_count=discovered,
            parsed_count=parsed,
            duplicate_count=duplicates,
            rejected_count=rejected,
            source_errors=source_errors,
            rejection_codes=rejection_codes,
        )
