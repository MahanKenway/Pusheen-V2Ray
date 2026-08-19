"""Typed domain models for the Kaveh quality pipeline.

The domain layer intentionally contains no HTTP, database, process, or framework code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Mapping


class Protocol(str, Enum):
    """Protocols supported by the initial Kaveh release."""

    VLESS = "vless"
    VMESS = "vmess"
    TROJAN = "trojan"
    SHADOWSOCKS = "ss"


class ValidationState(str, Enum):
    """Lifecycle of a canonical configuration."""

    DISCOVERED = "discovered"
    PARSED = "parsed"
    POLICY_ACCEPTED = "policy_accepted"
    QUEUED = "queued"
    REACHABLE = "reachable"
    E2E_VERIFIED = "e2e_verified"
    QUALIFIED = "qualified"
    PUBLISHED = "published"
    RETRY_SCHEDULED = "retry_scheduled"
    REJECTED = "rejected"
    STALE = "stale"
    RETIRED = "retired"


class ProbeStage(str, Enum):
    """Ordered stages of validation."""

    SCHEMA = "schema"
    REACHABILITY = "reachability"
    RUNTIME_BUILD = "runtime_build"
    END_TO_END = "end_to_end"


class ProbeOutcome(str, Enum):
    """Machine-readable result of a validation stage."""

    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class Source:
    """A reviewable upstream subscription source."""

    source_id: str
    url: str
    enabled: bool = True
    trust_weight: float = 0.5
    allowed_protocols: frozenset[Protocol] = field(
        default_factory=lambda: frozenset(Protocol)
    )
    max_bytes: int = 2_000_000
    max_entries: int = 500


@dataclass(frozen=True)
class Transport:
    """Connection fields that materially affect proxy behavior."""

    network: str = "tcp"
    security: str = "none"
    server_name: str | None = None
    path: str | None = None
    service_name: str | None = None
    extra: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalConfig:
    """A normalized proxy definition used throughout the pipeline.

    ``credential`` and ``raw_uri`` are operational data. Callers must use
    ``redacted_summary`` for logs, diagnostics, and public manifests.
    """

    protocol: Protocol
    host: str
    port: int
    credential: str
    transport: Transport = field(default_factory=Transport)
    label: str | None = None
    raw_uri: str = ""
    source_id: str | None = None
    identity_hash: str | None = None

    def redacted_summary(self) -> str:
        return f"{self.protocol.value}://***@{self.host}:{self.port}"


@dataclass(frozen=True)
class ParseFailure:
    """A safe, structured parse failure that never contains a raw URI."""

    source_id: str
    code: str
    detail: str


@dataclass(frozen=True)
class ProbeResult:
    """Result of one deterministic validation stage."""

    identity_hash: str
    stage: ProbeStage
    outcome: ProbeOutcome
    observed_at: datetime
    latency_ms: int | None = None
    error_code: str | None = None
    vantage_id: str = "default"

    @classmethod
    def passed(
        cls,
        identity_hash: str,
        stage: ProbeStage,
        latency_ms: int | None = None,
        vantage_id: str = "default",
    ) -> "ProbeResult":
        return cls(
            identity_hash=identity_hash,
            stage=stage,
            outcome=ProbeOutcome.PASS,
            observed_at=datetime.now(UTC),
            latency_ms=latency_ms,
            vantage_id=vantage_id,
        )

    @classmethod
    def failed(
        cls,
        identity_hash: str,
        stage: ProbeStage,
        error_code: str,
        vantage_id: str = "default",
    ) -> "ProbeResult":
        return cls(
            identity_hash=identity_hash,
            stage=stage,
            outcome=ProbeOutcome.FAIL,
            observed_at=datetime.now(UTC),
            error_code=error_code,
            vantage_id=vantage_id,
        )


@dataclass(frozen=True)
class HealthWindow:
    """Aggregate quality evidence for a configuration in one time window."""

    identity_hash: str
    sample_count: int
    success_count: int
    median_latency_ms: int | None
    last_success_at: datetime | None

    @property
    def success_rate(self) -> float:
        if not self.sample_count:
            return 0.0
        return self.success_count / self.sample_count


@dataclass(frozen=True)
class ScoreCard:
    """A reproducible quality score and its human-readable explanation."""

    identity_hash: str
    score: int
    policy_version: str
    explanation: Mapping[str, int]
    qualified: bool


@dataclass(frozen=True)
class PublicationSnapshot:
    """Metadata for an immutable feed publication."""

    snapshot_id: str
    created_at: datetime
    policy_version: str
    config_count: int
    artifact_hash: str


@dataclass(frozen=True)
class RunSummary:
    """Safe aggregate result of a pipeline run."""

    run_id: str
    discovered_count: int
    parsed_count: int
    duplicate_count: int
    rejected_count: int
    qualified_count: int
    published_snapshot_id: str | None
