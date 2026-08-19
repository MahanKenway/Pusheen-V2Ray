from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kaveh.config.source_registry import SourceRegistryError, load_sources


class SourceRegistryTests(unittest.TestCase):
    def _write_registry(self, source: dict[str, object]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "registry.json"
        path.write_text(json.dumps({"version": 1, "sources": [source]}), encoding="utf-8")
        return path

    @staticmethod
    def _source(**overrides: object) -> dict[str, object]:
        source: dict[str, object] = {
            "id": "reviewed-source",
            "url": "https://example.test/subscription.txt",
            "trust_weight": 0.75,
            "allowed_protocols": ["vless", "trojan"],
            "max_bytes": 250_000,
        }
        source.update(overrides)
        return source

    def test_accepts_bounded_https_source(self) -> None:
        sources = load_sources(self._write_registry(self._source()))

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source_id, "reviewed-source")
        self.assertEqual(sources[0].trust_weight, 0.75)
        self.assertEqual(sources[0].max_bytes, 250_000)

    def test_rejects_insecure_url(self) -> None:
        with self.assertRaisesRegex(SourceRegistryError, "HTTPS"):
            load_sources(self._write_registry(self._source(url="http://example.test/list.txt")))

    def test_rejects_url_credentials(self) -> None:
        with self.assertRaisesRegex(SourceRegistryError, "credentials"):
            load_sources(
                self._write_registry(self._source(url="https://user:pass@example.test/list.txt"))
            )

    def test_rejects_invalid_source_id(self) -> None:
        with self.assertRaisesRegex(SourceRegistryError, "lowercase slug"):
            load_sources(self._write_registry(self._source(id="Review_Source")))

    def test_rejects_weight_above_one(self) -> None:
        with self.assertRaisesRegex(SourceRegistryError, "between 0 and 1"):
            load_sources(self._write_registry(self._source(trust_weight=1.01)))

    def test_rejects_max_bytes_above_budget(self) -> None:
        with self.assertRaisesRegex(SourceRegistryError, "between 1 and 2000000"):
            load_sources(self._write_registry(self._source(max_bytes=2_000_001)))


if __name__ == "__main__":
    unittest.main()
