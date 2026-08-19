"""Command-line interface for Kaveh pipeline operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.adapters.publishers.snapshot_publisher import SnapshotPublisher
from kaveh.adapters.runtime.xray_adapter import XrayEndToEndProbe
from kaveh.application.commands.ingest_sources import IngestSources
from kaveh.application.commands.publish_snapshot import PublishSnapshot
from kaveh.application.commands.validate_batch import ValidateBatch
from kaveh.config.settings import RuntimeSettings
from kaveh.config.source_registry import load_sources
from kaveh.domain.services.qualification import QualificationPolicy
from kaveh.infrastructure.http.http_source_client import BoundedHttpsSourceClient
from kaveh.infrastructure.persistence.in_memory import InMemoryConfigRepository
from kaveh.infrastructure.persistence.postgres import (
    PostgresConfigRepository,
    PostgresDatabase,
    PostgresValidationHistory,
)
from kaveh.infrastructure.probes.schema_probe import SchemaProbe
from kaveh.infrastructure.probes.supervisor import ValidationSupervisor
from kaveh.infrastructure.probes.tcp_probe import TcpReachabilityProbe
from kaveh.infrastructure.storage.filesystem_store import FileSystemArtifactStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaveh",
        description="Kaveh quality-first proxy feed pipeline",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    ingest = subcommands.add_parser("ingest", help="fetch, normalize, parse, and deduplicate sources")
    ingest.add_argument(
        "--registry",
        type=Path,
        default=Path("configs/sources/registry.v1.json"),
        help="path to a reviewed source registry",
    )

    migrate = subcommands.add_parser("migrate", help="apply pending PostgreSQL migrations")
    migrate.add_argument(
        "--migrations-dir",
        type=Path,
        default=Path("migrations"),
        help="directory containing ordered SQL migrations",
    )

    validate = subcommands.add_parser(
        "validate",
        help="ingest reviewed sources, run isolated Xray end-to-end probes, and persist evidence",
    )
    validate.add_argument(
        "--registry",
        type=Path,
        default=Path("configs/sources/registry.v1.json"),
        help="path to a reviewed source registry",
    )
    validate.add_argument(
        "--limit",
        type=int,
        default=25,
        help="maximum number of stored candidates to probe in one run",
    )
    validate.add_argument(
        "--publish-root",
        type=Path,
        default=Path("public/generated"),
        help="artifact root used for immutable snapshots",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "migrate":
        settings = RuntimeSettings.from_environment()
        applied = PostgresDatabase(settings.require_database_url()).migrate(args.migrations_dir)
        print(json.dumps({"applied": list(applied), "count": len(applied)}))
        return 0
    if args.command == "ingest":
        return _run_ingest(args.registry)
    if args.command == "validate":
        return _run_validate(args.registry, args.limit, args.publish_root)
    return 2


def _run_ingest(registry_path: Path) -> int:
    sources = load_sources(registry_path)
    repository = InMemoryConfigRepository()
    report = IngestSources(
        BoundedHttpsSourceClient(), ParserRegistry(), repository
    ).run(sources)
    print(
        json.dumps(
            {
                "discovered": report.discovered_count,
                "parsed": report.parsed_count,
                "duplicates": report.duplicate_count,
                "rejected": report.rejected_count,
                "source_errors": report.source_errors,
                "rejection_codes": report.rejection_codes,
            },
            sort_keys=True,
        )
    )
    return 0


def _run_validate(registry_path: Path, limit: int, publish_root: Path) -> int:
    if limit < 1:
        raise ValueError("--limit must be at least 1")
    settings = RuntimeSettings.from_environment()
    database = PostgresDatabase(settings.require_database_url())
    database.migrate("migrations")
    sources = load_sources(registry_path)
    repository = PostgresConfigRepository(database)
    ingestion = IngestSources(
        BoundedHttpsSourceClient(), ParserRegistry(), repository
    ).run(sources)

    history = PostgresValidationHistory(database)
    policy = QualificationPolicy()
    history.start_run(policy.version, settings.vantage_id)
    try:
        candidates = repository.all()[:limit]
        supervisor = ValidationSupervisor(
            SchemaProbe(),
            TcpReachabilityProbe(),
            end_to_end_runner=XrayEndToEndProbe(settings),
        )
        validation = ValidateBatch(
            _LimitedRepository(candidates), supervisor, history, policy, sources
        ).run()
        publication_configs, publication_cards, publication_mode = _publication_inputs(
            candidates, validation.scorecards, repository, history, policy, sources
        )
        publication = PublishSnapshot(
            SnapshotPublisher(FileSystemArtifactStore(publish_root), policy.version)
        ).run(publication_configs, publication_cards, ingestion.source_errors)
        history.finish_run()
    except Exception:
        history.finish_run(status="failed", error_code="VALIDATION_RUN_FAILED")
        raise

    print(
        json.dumps(
            {
                "ingestion": {
                    "discovered": ingestion.discovered_count,
                    "parsed": ingestion.parsed_count,
                    "duplicates": ingestion.duplicate_count,
                    "rejected": ingestion.rejected_count,
                    "source_errors": ingestion.source_errors,
                },
                "validation": {
                    "candidates": len(candidates),
                    "validated": validation.validated_count,
                    "end_to_end_verified": validation.end_to_end_verified_count,
                    "qualified": validation.qualified_count,
                },
                "publication": {
                    "published": publication.published,
                    "snapshot_id": publication.snapshot.snapshot_id if publication.snapshot else None,
                    "reason": publication.reason,
                    "mode": publication_mode,
                },
            },
            sort_keys=True,
        )
    )
    return 0


def _publication_inputs(candidates, scorecards, repository, history, policy, sources):  # type: ignore[no-untyped-def]
    """Choose current evidence first, then only fresh persisted qualification.

    A scheduled runner can have path-specific reachability failures. A failed
    round must not replace a live feed with an empty one when a configuration
    still has qualifying end-to-end evidence within the active policy window.
    """

    current_cards = tuple(scorecards)
    if any(card.qualified for card in current_cards):
        return candidates, current_cards, "current_run"

    recently_qualified = getattr(repository, "recently_qualified", None)
    if not callable(recently_qualified):
        return candidates, current_cards, "current_run"
    historical_configs = tuple(recently_qualified(policy.max_staleness_hours))
    if not historical_configs:
        return candidates, current_cards, "current_run"

    source_weights = {source.source_id: source.trust_weight for source in sources}
    historical_cards = tuple(
        policy.score(
            history.health_window(config.identity_hash or ""),
            source_weights.get(config.source_id or "", 0.5),
        )
        for config in historical_configs
        if config.identity_hash
    )
    if not any(card.qualified for card in historical_cards):
        return candidates, current_cards, "current_run"
    return historical_configs, historical_cards, "fresh_history"


class _LimitedRepository:
    """Readonly repository view used to cap one validation run's work."""

    def __init__(self, configs):  # type: ignore[no-untyped-def]
        self._configs = tuple(configs)

    def upsert(self, config):  # type: ignore[no-untyped-def]
        raise RuntimeError("Validation view is read-only")

    def get(self, identity_hash: str):  # type: ignore[no-untyped-def]
        return next((item for item in self._configs if item.identity_hash == identity_hash), None)

    def all(self):  # type: ignore[no-untyped-def]
        return self._configs


if __name__ == "__main__":
    raise SystemExit(main())
