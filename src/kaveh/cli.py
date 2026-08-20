"""Command-line interface for Kaveh pipeline operations."""

from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.adapters.publishers.evidence_receipt_publisher import EvidenceReceiptPublisher
from kaveh.adapters.publishers.reachable_publisher import ReachableFeedPublisher
from kaveh.adapters.publishers.resilient_publisher import (
    OutageDiverseFeedPublisher,
    ResilientFeedPublisher,
)
from kaveh.adapters.publishers.snapshot_publisher import SnapshotPublisher
from kaveh.adapters.publishers.status_publisher import StatusPublisher
from kaveh.adapters.publishers.xray_failover_publisher import XrayFailoverPublisher
from kaveh.adapters.runtime.probe_router import ProtocolRuntimeProbe
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
        default=Path("."),
        help="repository root that contains stable subscriptions/ and snapshots/ paths",
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


REACHABLE_MAX_AGE_HOURS = 72
REACHABLE_FEED_LIMIT = 250


def _run_validate(registry_path: Path, limit: int, publish_root: Path) -> int:
    if limit < 1:
        raise ValueError("--limit must be at least 1")
    settings = RuntimeSettings.from_environment()
    started = time.perf_counter()
    database = PostgresDatabase(settings.require_database_url())
    database.migrate("migrations")
    _log_validation_progress("database_ready", started)
    sources = load_sources(registry_path)
    repository = PostgresConfigRepository(database)

    # Register the reviewed registry first, then skip only temporally quarantined
    # sources. Quarantine state is evidence-driven and never edits the registry.
    for source in sources:
        repository.upsert_source(source)
    active_sources = tuple(
        source for source in sources if not repository.is_source_quarantined(source.source_id)
    )
    ingestion = IngestSources(
        BoundedHttpsSourceClient(), ParserRegistry(), repository
    ).run(active_sources)
    repository.record_source_health(ingestion.source_stats)
    _log_validation_progress("ingestion_complete", started)

    history = PostgresValidationHistory(database)
    policy = QualificationPolicy()
    history.start_run(policy.version, settings.vantage_id)
    try:
        # all() prioritizes never-probed then least-recently-probed candidates.
        candidates = repository.all()[:limit]
        _log_validation_progress("candidates_selected", started, count=len(candidates))
        supervisor = ValidationSupervisor(
            SchemaProbe(),
            TcpReachabilityProbe(),
            end_to_end_runner=ProtocolRuntimeProbe(settings),
        )
        validation = ValidateBatch(
            _LimitedRepository(candidates),
            supervisor,
            history,
            policy,
            active_sources,
            max_workers=settings.validation_workers,
        ).run()
        _log_validation_progress("runtime_validation_complete", started, count=validation.validated_count)
        publication_configs, publication_cards, publication_mode = _publication_inputs(
            candidates, validation.scorecards, repository, history, policy, active_sources
        )
        artifact_store = FileSystemArtifactStore(publish_root)
        _migrate_legacy_strict_feed(artifact_store)
        publication = PublishSnapshot(
            SnapshotPublisher(artifact_store, policy.version)
        ).run(publication_configs, publication_cards, ingestion.source_errors)
        reachable_inputs = _reachable_publication_inputs(repository)
        reachable_publication = ReachableFeedPublisher(artifact_store).publish(
            reachable_inputs, ingestion.source_errors
        )
        resilient_publisher = ResilientFeedPublisher(artifact_store)
        resilient_inputs = resilient_publisher.select(reachable_inputs)
        resilient_publication = resilient_publisher.publish(
            reachable_inputs, ingestion.source_errors
        )
        resilient_receipts = EvidenceReceiptPublisher(artifact_store).publish(
            resilient_inputs,
            tier="tcp-reachable-diverse-v1",
            evidence="recent successful TCP reachability",
            vantage_id=settings.vantage_id,
            max_evidence_age_hours=REACHABLE_MAX_AGE_HOURS,
        )
        failover_profile = XrayFailoverPublisher(artifact_store).publish(resilient_inputs)
        outage_publisher = OutageDiverseFeedPublisher(artifact_store)
        outage_inputs = outage_publisher.select(reachable_inputs)
        outage_publication = outage_publisher.publish(reachable_inputs, ingestion.source_errors)
        outage_receipts = EvidenceReceiptPublisher(artifact_store).publish(
            outage_inputs,
            tier="tcp-reachable-outage-diverse-v1",
            evidence="recent successful TCP reachability with tighter anti-concentration policy",
            vantage_id=settings.vantage_id,
            max_evidence_age_hours=REACHABLE_MAX_AGE_HOURS,
            artifact_name="outage",
            inclusion=(
                "selected from recent TCP-reachability evidence after tighter source, "
                "protocol, endpoint, and transport anti-concentration policy"
            ),
        )
        StatusPublisher(artifact_store).publish(
            ingestion={
                "discovered": ingestion.discovered_count,
                "parsed": ingestion.parsed_count,
                "duplicates": ingestion.duplicate_count,
                "rejected": ingestion.rejected_count,
                "source_errors": ingestion.source_errors,
            },
            validation={
                "candidates": len(candidates),
                "validated": validation.validated_count,
                "end_to_end_verified": validation.end_to_end_verified_count,
                "qualified": validation.qualified_count,
                "probe_endpoints": len(settings.probe_urls),
                "validation_workers": settings.validation_workers,
            },
            strict_publication={
                "published": publication.published,
                "count": (
                    publication.snapshot.config_count
                    if publication.snapshot
                    else _active_feed_count(artifact_store, "subscriptions/strict.txt")
                ),
                "snapshot_id": publication.snapshot.snapshot_id if publication.snapshot else None,
                "reason": publication.reason,
                "mode": publication_mode,
            },
            reachable_publication={
                "published": reachable_publication.published,
                "count": reachable_publication.count,
                "snapshot_id": reachable_publication.snapshot_id,
                "reason": reachable_publication.reason,
            },
            resilient_publication={
                "published": resilient_publication.published,
                "count": resilient_publication.count,
                "snapshot_id": resilient_publication.snapshot_id,
                "reason": resilient_publication.reason,
                "receipt_count": resilient_receipts.count,
                "receipt_published": resilient_receipts.published,
                "receipt_reason": resilient_receipts.reason,
                "receipt_path": "subscriptions/resilient.receipts.v1.json",
                "failover_profile": {
                    "path": "profiles/resilient-xray.json",
                    "published": failover_profile.published,
                    "count": failover_profile.count,
                    "reason": failover_profile.reason,
                    "artifact_hash": failover_profile.artifact_hash,
                },
            },
            source_health=repository.source_health_snapshot(),
            reachable_max_age_hours=REACHABLE_MAX_AGE_HOURS,
            outage_publication={
                "published": outage_publication.published,
                "count": outage_publication.count,
                "snapshot_id": outage_publication.snapshot_id,
                "reason": outage_publication.reason,
                "receipt_count": outage_receipts.count,
                "receipt_published": outage_receipts.published,
                "receipt_reason": outage_receipts.reason,
                "receipt_path": "subscriptions/outage.receipts.v1.json",
            },
        )
        history.finish_run()
        _log_validation_progress("publication_complete", started)
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
                    "probe_endpoints": len(settings.probe_urls),
                "validation_workers": settings.validation_workers,
                },
                "publication": {
                    "published": publication.published,
                    "snapshot_id": publication.snapshot.snapshot_id if publication.snapshot else None,
                    "reason": publication.reason,
                    "mode": publication_mode,
                },
                "reachable_publication": {
                    "published": reachable_publication.published,
                    "count": reachable_publication.count,
                    "snapshot_id": reachable_publication.snapshot_id,
                    "reason": reachable_publication.reason,
                },
                "outage_publication": {
                    "published": outage_publication.published,
                    "count": outage_publication.count,
                    "snapshot_id": outage_publication.snapshot_id,
                    "reason": outage_publication.reason,
                    "receipt_count": outage_receipts.count,
                    "receipt_published": outage_receipts.published,
                    "receipt_reason": outage_receipts.reason,
                },
                "resilient_publication": {
                    "published": resilient_publication.published,
                    "count": resilient_publication.count,
                    "snapshot_id": resilient_publication.snapshot_id,
                    "reason": resilient_publication.reason,
                    "receipt_count": resilient_receipts.count,
                    "receipt_published": resilient_receipts.published,
                    "receipt_reason": resilient_receipts.reason,
                    "failover_profile": {
                        "path": "profiles/resilient-xray.json",
                        "published": failover_profile.published,
                        "count": failover_profile.count,
                        "reason": failover_profile.reason,
                        "artifact_hash": failover_profile.artifact_hash,
                    },
                },
            },
            sort_keys=True,
        )
    )
    return 0


def _log_validation_progress(event: str, started: float, **details: object) -> None:
    """Emit credential-safe, line-buffered timing telemetry for CI diagnostics."""

    payload: dict[str, object] = {
        "event": event,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    payload.update(details)
    print(json.dumps({"validation_progress": payload}, sort_keys=True), flush=True)


def _migrate_legacy_strict_feed(artifact_store) -> None:  # type: ignore[no-untyped-def]
    """Preserve the former strict all feed before its high-coverage replacement."""

    read_bytes = getattr(artifact_store, "read_bytes", None)
    if not callable(read_bytes) or read_bytes("subscriptions/strict.txt"):
        return
    legacy_content = read_bytes("subscriptions/all.txt")
    if not legacy_content:
        return
    artifact_store.write_atomic("subscriptions/strict.txt", legacy_content)
    artifact_store.write_atomic("subscriptions/strict.base64", base64.b64encode(legacy_content))
    legacy_manifest = read_bytes("subscriptions/manifest.v1.json")
    if legacy_manifest:
        artifact_store.write_atomic("subscriptions/strict.manifest.v1.json", legacy_manifest)


def _active_feed_count(artifact_store, relative_path: str) -> int:  # type: ignore[no-untyped-def]
    """Count active stable-feed entries without exposing their URI contents."""

    read_bytes = getattr(artifact_store, "read_bytes", None)
    if not callable(read_bytes):
        return 0
    content = read_bytes(relative_path)
    if not content:
        return 0
    return sum(1 for line in content.decode("utf-8").splitlines() if line.strip())


def _reachable_publication_inputs(repository):  # type: ignore[no-untyped-def]
    """Return a broader, bounded TCP-reachable tier without weakening strict."""

    recently_reachable = getattr(repository, "recently_reachable", None)
    if not callable(recently_reachable):
        return ()
    return tuple(recently_reachable(REACHABLE_MAX_AGE_HOURS))[:REACHABLE_FEED_LIMIT]


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
    source_weights = {source.source_id: source.trust_weight for source in sources}
    historical_configs = tuple(
        config
        for config in recently_qualified(policy.max_staleness_hours)
        if config.source_id in source_weights
    )
    if not historical_configs:
        return candidates, current_cards, "current_run"

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
