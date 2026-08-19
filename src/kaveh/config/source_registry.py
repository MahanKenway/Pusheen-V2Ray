"""Versioned, reviewable source registry loading."""

from __future__ import annotations

import json
from pathlib import Path

from kaveh.domain.models import Protocol, Source


class SourceRegistryError(ValueError):
    pass


def load_sources(path: str | Path) -> tuple[Source, ...]:
    """Load a v1 source registry without embedding source URLs in code."""

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceRegistryError("Registry cannot be loaded") from exc
    if data.get("version") != 1 or not isinstance(data.get("sources"), list):
        raise SourceRegistryError("Registry must contain version 1 and sources")

    sources: list[Source] = []
    seen_ids: set[str] = set()
    for item in data["sources"]:
        try:
            source_id = str(item["id"])
            if source_id in seen_ids:
                raise SourceRegistryError("Source ids must be unique")
            allowed = frozenset(Protocol(value) for value in item.get("allowed_protocols", []))
            sources.append(
                Source(
                    source_id=source_id,
                    url=str(item["url"]),
                    enabled=bool(item.get("enabled", True)),
                    trust_weight=float(item.get("trust_weight", 0.5)),
                    allowed_protocols=allowed or frozenset(Protocol),
                    max_bytes=int(item.get("max_bytes", 2_000_000)),
                )
            )
            seen_ids.add(source_id)
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceRegistryError("Source entry is invalid") from exc
    return tuple(sources)
