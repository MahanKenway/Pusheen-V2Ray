"""Publisher for a public-safe operational status document."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Mapping

from kaveh.domain.ports import ArtifactStore


class StatusPublisher:
    """Write ``status.json`` without configuration URIs, hosts, or credentials."""

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store

    def publish(
        self,
        *,
        ingestion: Mapping[str, Any],
        validation: Mapping[str, Any],
        strict_publication: Mapping[str, Any],
        reachable_publication: Mapping[str, Any],
        resilient_publication: Mapping[str, Any],
        source_health: tuple[dict[str, Any], ...],
        reachable_max_age_hours: int,
        outage_publication: Mapping[str, Any] | None = None,
    ) -> None:
        sources = [_public_source_health(item) for item in source_health]
        existing = _existing_operational_status(self.artifact_store)
        document = {
            "schema_version": 1,
            "updated_at": datetime.now(UTC).isoformat(),
            "service": "Pusheen V2Ray quality-first subscription pipeline",
            "feeds": {
                "primary": {
                    **dict(reachable_publication),
                    "path": "subscriptions/all.txt",
                    "evidence": "recent TCP reachability only",
                    "max_evidence_age_hours": reachable_max_age_hours,
                    "minimum_target": 100,
                },
                "strict": {
                    **dict(strict_publication),
                    "path": "subscriptions/strict.txt",
                    "evidence": "end-to-end HTTPS probe through Xray",
                },
                "balanced": {
                    **dict(reachable_publication),
                    "evidence": "recent TCP reachability only",
                    "max_evidence_age_hours": reachable_max_age_hours,
                    "variants": ["reachable", "reachable-fast", "reachable-vless", "reachable-vmess", "reachable-trojan", "reachable-ss"],
                },
                "resilient": {
                    **dict(resilient_publication),
                    "path": "subscriptions/resilient.txt",
                    "evidence": "recent TCP reachability with source, protocol, endpoint, and transport anti-concentration",
                    "max_evidence_age_hours": reachable_max_age_hours,
                    "selection_notice": "This is a common-mode-risk reduction policy, not an Iran-availability or end-to-end guarantee.",
                },
                **(
                    {
                        "outage_diverse": {
                            **dict(outage_publication),
                            "path": "subscriptions/outage.txt",
                            "evidence": "recent TCP reachability with tighter source, protocol, endpoint, and transport concentration caps",
                            "max_evidence_age_hours": reachable_max_age_hours,
                            "selection_notice": "Designed to reduce shared failure modes; not evidence from inside Iran and not a shutdown-availability guarantee.",
                        }
                    }
                    if outage_publication is not None
                    else {}
                ),
            },
            "ingestion": dict(ingestion),
            "validation": dict(validation),
            "sources": {
                "total": len(sources),
                "healthy": sum(1 for item in sources if item["enabled"] and not item["quarantined"]),
                "quarantined": sum(1 for item in sources if item["quarantined"]),
                "items": sources,
            },
            **existing,
            "notice": "Evidence is time- and validator-origin-specific; availability is not guaranteed.",
        }
        content = (json.dumps(document, sort_keys=True, indent=2, default=_json_default) + "\n").encode("utf-8")
        self.artifact_store.write_atomic("status.json", content)


def _existing_operational_status(artifact_store: ArtifactStore) -> dict[str, Any]:
    """Preserve public delivery telemetry written by the independent monitor."""

    read_bytes = getattr(artifact_store, "read_bytes", None)
    if not callable(read_bytes):
        return {}
    try:
        current = json.loads(read_bytes("status.json") or b"{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(current, dict):
        return {}
    return {
        key: current[key]
        for key in ("delivery_monitor", "slo")
        if isinstance(current.get(key), dict)
    }


def _public_source_health(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_id": item["source_id"],
        "enabled": bool(item["enabled"]),
        "quarantined": bool(item.get("quarantined")),
        "quarantine_until": item.get("quarantine_until"),
        "total_runs": int(item.get("total_runs") or 0),
        "successful_runs": int(item.get("successful_runs") or 0),
        "consecutive_failures": int(item.get("consecutive_failures") or 0),
        "last_discovered_count": int(item.get("last_discovered_count") or 0),
        "last_accepted_count": int(item.get("last_accepted_count") or 0),
        "last_error_code": item.get("last_error_code"),
        "last_checked_at": item.get("last_checked_at"),
    }


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Unsupported status value: {type(value).__name__}")
