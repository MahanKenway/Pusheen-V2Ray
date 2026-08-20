"""Subscription container normalization for plain and Base64 line feeds."""

from __future__ import annotations

import re

from kaveh.adapters.protocols.encoded import decode_base64


_URI_LINE = re.compile(r"(?m)^\s*[A-Za-z][A-Za-z0-9+.-]*://")


def normalize_lines(content: str, max_lines: int = 20_000) -> list[str]:
    """Return normalized URI lines from plain text or a Base64 line container.

    This function deliberately does not validate protocols. It only unwraps a
    container, limits work, removes blank lines, and preserves raw URI text for
    a protocol-specific parser.
    """

    stripped = content.strip()
    if not stripped:
        return []
    if not _URI_LINE.search(stripped):
        try:
            decoded = decode_base64(stripped)
        except ValueError:
            decoded = stripped
        if _URI_LINE.search(decoded):
            stripped = decoded
    lines = [line.strip() for line in stripped.splitlines() if "://" in line]
    return lines[:max_lines]
