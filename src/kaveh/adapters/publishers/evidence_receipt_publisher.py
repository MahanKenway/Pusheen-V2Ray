"""Credential-free evidence receipts for public subscription tiers."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from kaveh.domain.models import CanonicalConfig
from kaveh.domain.ports import ArtifactStore


@dataclass(frozen=True)
class EvidenceReceiptPublishReport:
    published: bool
    count: int
    artifact_hash: str | None = None
    reason: str | None = None


class EvidenceReceiptPublisher:
    """Publish safe inclusion receipts without URI hosts or credentials.

    The input configs are selected from a repository query whose contract is
    recent successful TCP reachability. Receipts intentionally describe that
    contract and the validator vantage, rather than falsely claiming an
    end-to-end or Iran-located measurement.
    """

    schema_version = 1

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store

    def publish(
        self,
        configs: Iterable[CanonicalConfig],
        *,
        tier: str,
        evidence: str,
        vantage_id: str,
        max_evidence_age_hours: int,
    ) -> EvidenceReceiptPublishReport:
        receipts = [self._receipt(config) for config in configs if config.identity_hash]
        document = {
            "schema_version": self.schema_version,
            "tier": tier,
            "created_at": datetime.now(UTC).isoformat(),
            "evidence": evidence,
            "vantage_id": vantage_id,
            "max_evidence_age_hours": max_evidence_age_hours,
            "count": len(receipts),
            "by_protocol": dict(sorted(Counter(item["protocol"] for item in receipts).items())),
            "receipts": receipts,
            "notice": (
                "A receipt records why the item is eligible for this tier at publication time. "
                "It does not disclose hostnames, credentials, raw URIs, or guarantee availability from another network."
            ),
        }
        content = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode("utf-8")
        artifact_hash = hashlib.sha256(content).hexdigest()
        read_bytes = getattr(self.artifact_store, "read_bytes", None)
        if callable(read_bytes):
            existing = read_bytes("subscriptions/resilient.receipts.v1.json")
            if existing and _equivalent_except_created_at(existing, document):
                return EvidenceReceiptPublishReport(
                    False, len(receipts), reason="NO_EVIDENCE_RECEIPT_CHANGE"
                )
        self.artifact_store.write_atomic("subscriptions/resilient.receipts.v1.json", content)
        return EvidenceReceiptPublishReport(True, len(receipts), artifact_hash=artifact_hash)

    @staticmethod
    def _receipt(config: CanonicalConfig) -> dict[str, str]:
        transport = config.transport
        identity = config.identity_hash or ""
        return {
            "id": identity[:16],
            "protocol": config.protocol.value,
            "transport_family": ":".join(
                (config.protocol.value, transport.network or "unknown", transport.security or "none")
            ),
            "latest_source_id": config.source_id or "unknown",
            "inclusion": "selected from recent TCP-reachability evidence after resilient anti-concentration policy",
        }


def _equivalent_except_created_at(existing: bytes, next_document: dict[str, object]) -> bool:
    try:
        previous = json.loads(existing.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    candidate = dict(next_document)
    candidate.pop("created_at", None)
    previous.pop("created_at", None)
    return previous == candidate
