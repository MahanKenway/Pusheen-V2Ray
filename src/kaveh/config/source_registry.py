"""Versioned, reviewable source registry loading."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from urllib.parse import urlparse

from kaveh.domain.models import Protocol, Source


class SourceRegistryError(ValueError):
    pass


_SOURCE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_MAX_SOURCE_BYTES = 2_000_000


def _validated_source_id(value: object) -> str:
    source_id = str(value)
    if not _SOURCE_ID.fullmatch(source_id):
        raise SourceRegistryError("Source id must be a lowercase slug of at most 64 characters")
    return source_id


def _validated_https_url(value: object) -> str:
    url = str(value)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SourceRegistryError("Source URL must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise SourceRegistryError("Source URL must not include credentials")
    return url


def _validated_weight(value: object) -> float:
    weight = float(value)
    if not math.isfinite(weight) or not 0.0 <= weight <= 1.0:
        raise SourceRegistryError("Source trust weight must be between 0 and 1")
    return weight


def _validated_max_bytes(value: object) -> int:
    if isinstance(value, bool):
        raise SourceRegistryError("Source max_bytes must be an integer")
    max_bytes = int(value)
    if not 1 <= max_bytes <= _MAX_SOURCE_BYTES:
        raise SourceRegistryError(
            f"Source max_bytes must be between 1 and {_MAX_SOURCE_BYTES}"
        )
    return max_bytes


def load_sources(path: str | Path) -> tuple[Source, ...]:
    """Load a bounded, HTTPS-only v1 source registry."""

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
            source_id = _validated_source_id(item["id"])
            if source_id in seen_ids:
                raise SourceRegistryError("Source ids must be unique")
            allowed = frozenset(Protocol(value) for value in item.get("allowed_protocols", []))
            sources.append(
                Source(
                    source_id=source_id,
                    url=_validated_https_url(item["url"]),
                    enabled=bool(item.get("enabled", True)),
                    trust_weight=_validated_weight(item.get("trust_weight", 0.5)),
                    allowed_protocols=allowed or frozenset(Protocol),
                    max_bytes=_validated_max_bytes(item.get("max_bytes", _MAX_SOURCE_BYTES)),
                )
            )
            seen_ids.add(source_id)
        except SourceRegistryError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise SourceRegistryError("Source entry is invalid") from exc
    return tuple(sources)
