"""PostgreSQL persistence adapters for Kaveh.

This module stores raw URIs only because the publisher needs them to construct
feeds. Callers must never log query values or database exceptions containing
raw rows.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from kaveh.domain.models import (
    CanonicalConfig,
    HealthWindow,
    ProbeOutcome,
    ProbeResult,
    ProbeStage,
    Protocol,
    ScoreCard,
    Source,
    Transport,
    ValidationState,
)


class MigrationError(RuntimeError):
    pass


class PostgresDatabase:
    """Small transaction boundary around psycopg connections."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def transaction(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.transaction():
                yield connection

    def migrate(self, migrations_dir: str | Path) -> tuple[str, ...]:
        """Apply SQL migrations exactly once, in lexical filename order."""

        migrations_path = Path(migrations_dir)
        files = sorted(migrations_path.glob("*.sql"))
        if not files:
            raise MigrationError("No SQL migrations were found")
        applied: list[str] = []
        with self.transaction() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS kaveh_schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            for migration in files:
                version = migration.name
                row = connection.execute(
                    "SELECT 1 FROM kaveh_schema_migrations WHERE version = %s",
                    (version,),
                ).fetchone()
                if row:
                    continue
                try:
                    connection.execute(migration.read_text(encoding="utf-8"))
                    connection.execute(
                        "INSERT INTO kaveh_schema_migrations (version) VALUES (%s)",
                        (version,),
                    )
                except (OSError, psycopg.Error) as exc:
                    raise MigrationError(f"Migration {version} could not be applied") from exc
                applied.append(version)
        return tuple(applied)


class PostgresConfigRepository:
    """Persists canonical identities and source observations."""

    def __init__(self, database: PostgresDatabase) -> None:
        self.database = database

    def upsert_source(self, source: Source) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO sources (source_id, url, enabled, trust_weight, allowed_protocols, max_bytes)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_id) DO UPDATE SET
                    url = EXCLUDED.url,
                    enabled = EXCLUDED.enabled,
                    trust_weight = EXCLUDED.trust_weight,
                    allowed_protocols = EXCLUDED.allowed_protocols,
                    max_bytes = EXCLUDED.max_bytes,
                    updated_at = NOW()
                """,
                (
                    source.source_id,
                    source.url,
                    source.enabled,
                    source.trust_weight,
                    Jsonb(sorted(protocol.value for protocol in source.allowed_protocols)),
                    source.max_bytes,
                ),
            )

    def upsert(self, config: CanonicalConfig) -> bool:
        if not config.identity_hash:
            raise ValueError("CanonicalConfig must have an identity hash")
        transport = _transport_json(config.transport)
        with self.database.transaction() as connection:
            exists = connection.execute(
                "SELECT 1 FROM configs WHERE identity_hash = %s",
                (config.identity_hash,),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO configs (
                    identity_hash, protocol, host, port, credential, transport, label, raw_uri
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (identity_hash) DO UPDATE SET
                    label = EXCLUDED.label,
                    raw_uri = EXCLUDED.raw_uri,
                    last_seen_at = NOW()
                """,
                (
                    config.identity_hash,
                    config.protocol.value,
                    config.host,
                    config.port,
                    config.credential,
                    Jsonb(transport),
                    config.label,
                    config.raw_uri,
                ),
            )
            if config.source_id:
                raw_hash = hashlib.sha256(config.raw_uri.encode("utf-8")).hexdigest()
                connection.execute(
                    """
                    INSERT INTO config_observations (identity_hash, source_id, raw_hash)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (identity_hash, source_id) DO UPDATE SET
                        raw_hash = EXCLUDED.raw_hash,
                        last_seen_at = NOW()
                    """,
                    (config.identity_hash, config.source_id, raw_hash),
                )
            return exists is None

    def get(self, identity_hash: str) -> CanonicalConfig | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT c.*, observation.source_id
                FROM configs c
                LEFT JOIN LATERAL (
                    SELECT source_id FROM config_observations
                    WHERE identity_hash = c.identity_hash
                    ORDER BY last_seen_at DESC LIMIT 1
                ) AS observation ON TRUE
                WHERE c.identity_hash = %s
                """,
                (identity_hash,),
            ).fetchone()
        return _config_from_row(row) if row else None

    def all(self) -> tuple[CanonicalConfig, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT c.*, observation.source_id
                FROM configs AS c
                JOIN LATERAL (
                    SELECT o.source_id
                    FROM config_observations AS o
                    JOIN sources AS s ON s.source_id = o.source_id
                    WHERE o.identity_hash = c.identity_hash AND s.enabled
                    ORDER BY o.last_seen_at DESC LIMIT 1
                ) AS observation ON TRUE
                LEFT JOIN config_status AS status ON status.identity_hash = c.identity_hash
                ORDER BY status.last_checked_at ASC NULLS FIRST, c.last_seen_at DESC
                """
            ).fetchall()
        return tuple(_config_from_row(row) for row in rows)

    def recently_reachable(self, max_age_hours: int) -> tuple[CanonicalConfig, ...]:
        """Return active-source configs with recent successful TCP reachability."""

        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT c.*, observation.source_id, reachable.last_success_at
                FROM configs AS c
                JOIN LATERAL (
                    SELECT o.source_id
                    FROM config_observations AS o
                    JOIN sources AS s ON s.source_id = o.source_id
                    WHERE o.identity_hash = c.identity_hash AND s.enabled
                    ORDER BY o.last_seen_at DESC LIMIT 1
                ) AS observation ON TRUE
                JOIN LATERAL (
                    SELECT MAX(p.observed_at) AS last_success_at
                    FROM probe_results AS p
                    WHERE p.identity_hash = c.identity_hash
                      AND p.stage = 'reachability'
                      AND p.outcome = 'pass'
                ) AS reachable ON reachable.last_success_at IS NOT NULL
                WHERE reachable.last_success_at >= NOW() - (%s * INTERVAL '1 hour')
                ORDER BY reachable.last_success_at DESC, c.identity_hash
                """,
                (max_age_hours,),
            ).fetchall()
        return tuple(_config_from_row(row) for row in rows)

    def recently_qualified(self, max_age_hours: int) -> tuple[CanonicalConfig, ...]:
        """Return configurations with fresh persisted qualification evidence.

        This is deliberately bounded by the policy's freshness window. It lets a
        transient runner-specific failure preserve a previously verified public
        feed without treating stale evidence as publishable.
        """

        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT c.*, observation.source_id
                FROM configs AS c
                JOIN config_status AS status ON status.identity_hash = c.identity_hash
                LEFT JOIN LATERAL (
                    SELECT source_id FROM config_observations
                    WHERE identity_hash = c.identity_hash
                    ORDER BY last_seen_at DESC LIMIT 1
                ) AS observation ON TRUE
                WHERE status.state = 'qualified'
                  AND status.last_e2e_success_at >= NOW() - (%s * INTERVAL '1 hour')
                ORDER BY status.score DESC NULLS LAST, status.last_e2e_success_at DESC
                """,
                (max_age_hours,),
            ).fetchall()
        return tuple(_config_from_row(row) for row in rows)


class PostgresValidationHistory:
    """Stores append-only probe evidence and a materialized current status."""

    def __init__(self, database: PostgresDatabase) -> None:
        self.database = database
        self._active_run_id: uuid.UUID | None = None

    def start_run(self, policy_version: str, vantage_id: str) -> uuid.UUID:
        run_id = uuid.uuid4()
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO validation_runs (run_id, policy_version, vantage_id, status)
                VALUES (%s, %s, %s, 'running')
                """,
                (run_id, policy_version, vantage_id),
            )
        self._active_run_id = run_id
        return run_id

    def finish_run(self, status: str = "completed", error_code: str | None = None) -> None:
        if not self._active_run_id:
            return
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE validation_runs
                SET finished_at = NOW(), status = %s, error_code = %s
                WHERE run_id = %s
                """,
                (status, error_code, self._active_run_id),
            )
        self._active_run_id = None

    def append(self, results: Iterable[ProbeResult]) -> None:
        values = tuple(results)
        if not values:
            return
        with self.database.transaction() as connection:
            for result in values:
                connection.execute(
                    """
                    INSERT INTO probe_results (
                        run_id, identity_hash, stage, outcome, latency_ms,
                        error_code, vantage_id, observed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        self._active_run_id,
                        result.identity_hash,
                        result.stage.value,
                        result.outcome.value,
                        result.latency_ms,
                        result.error_code,
                        result.vantage_id,
                        result.observed_at,
                    ),
                )
                state = _state_for_result(result)
                connection.execute(
                    """
                    INSERT INTO config_status (
                        identity_hash, state, last_stage, last_outcome, last_error_code,
                        last_checked_at, last_e2e_success_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (identity_hash) DO UPDATE SET
                        state = EXCLUDED.state,
                        last_stage = EXCLUDED.last_stage,
                        last_outcome = EXCLUDED.last_outcome,
                        last_error_code = EXCLUDED.last_error_code,
                        last_checked_at = EXCLUDED.last_checked_at,
                        last_e2e_success_at = COALESCE(
                            EXCLUDED.last_e2e_success_at, config_status.last_e2e_success_at
                        ),
                        updated_at = NOW()
                    """,
                    (
                        result.identity_hash,
                        state.value,
                        result.stage.value,
                        result.outcome.value,
                        result.error_code,
                        result.observed_at,
                        result.observed_at
                        if result.stage is ProbeStage.END_TO_END
                        and result.outcome is ProbeOutcome.PASS
                        else None,
                    ),
                )

    def health_window(self, identity_hash: str) -> HealthWindow:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT outcome, latency_ms, observed_at
                FROM probe_results
                WHERE identity_hash = %s AND stage = 'end_to_end'
                ORDER BY observed_at DESC
                LIMIT 20
                """,
                (identity_hash,),
            ).fetchall()
        successes = [row for row in rows if row["outcome"] == ProbeOutcome.PASS.value]
        latencies = [row["latency_ms"] for row in successes if row["latency_ms"] is not None]
        return HealthWindow(
            identity_hash=identity_hash,
            sample_count=len(rows),
            success_count=len(successes),
            median_latency_ms=int(median(latencies)) if latencies else None,
            last_success_at=max((row["observed_at"] for row in successes), default=None),
        )

    def save_scorecard(self, scorecard: ScoreCard) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO scorecards (identity_hash, policy_version, score, qualified, explanation)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    scorecard.identity_hash,
                    scorecard.policy_version,
                    scorecard.score,
                    scorecard.qualified,
                    Jsonb(dict(scorecard.explanation)),
                ),
            )
            connection.execute(
                """
                UPDATE config_status
                SET state = %s, score = %s, policy_version = %s, updated_at = NOW()
                WHERE identity_hash = %s
                """,
                (
                    ValidationState.QUALIFIED.value
                    if scorecard.qualified
                    else ValidationState.E2E_VERIFIED.value,
                    scorecard.score,
                    scorecard.policy_version,
                    scorecard.identity_hash,
                ),
            )


def _transport_json(transport: Transport) -> dict[str, Any]:
    return {
        "network": transport.network,
        "security": transport.security,
        "server_name": transport.server_name,
        "path": transport.path,
        "service_name": transport.service_name,
        "extra": dict(transport.extra),
    }


def _config_from_row(row: dict[str, Any]) -> CanonicalConfig:
    transport_data = row["transport"]
    if isinstance(transport_data, str):
        transport_data = json.loads(transport_data)
    return CanonicalConfig(
        protocol=Protocol(row["protocol"]),
        host=row["host"],
        port=row["port"],
        credential=row["credential"],
        transport=Transport(
            network=transport_data.get("network", "tcp"),
            security=transport_data.get("security", "none"),
            server_name=transport_data.get("server_name"),
            path=transport_data.get("path"),
            service_name=transport_data.get("service_name"),
            extra=transport_data.get("extra", {}),
        ),
        label=row["label"],
        raw_uri=row["raw_uri"],
        source_id=row.get("source_id"),
        identity_hash=row["identity_hash"],
    )


def _state_for_result(result: ProbeResult) -> ValidationState:
    if result.outcome is ProbeOutcome.FAIL:
        return (
            ValidationState.REJECTED
            if result.stage is ProbeStage.SCHEMA
            else ValidationState.RETRY_SCHEDULED
        )
    return {
        ProbeStage.SCHEMA: ValidationState.POLICY_ACCEPTED,
        ProbeStage.REACHABILITY: ValidationState.REACHABLE,
        ProbeStage.RUNTIME_BUILD: ValidationState.REACHABLE,
        ProbeStage.END_TO_END: ValidationState.E2E_VERIFIED,
    }[result.stage]
