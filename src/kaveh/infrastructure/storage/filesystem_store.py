"""Filesystem artifact store with atomic snapshot pointers."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


class FileSystemArtifactStore:
    """Writes immutable artifacts below one root without direct latest rewrites."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_atomic(self, relative_path: str, content: bytes) -> str:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_bytes(content)
        os.replace(temporary, target)
        return hashlib.sha256(content).hexdigest()

    def read_bytes(self, relative_path: str) -> bytes | None:
        target = self.root / relative_path
        try:
            return target.read_bytes()
        except FileNotFoundError:
            return None

    def switch_latest(self, snapshot_id: str) -> None:
        payload = (snapshot_id + "\n").encode("utf-8")
        self.write_atomic("latest.txt", payload)
