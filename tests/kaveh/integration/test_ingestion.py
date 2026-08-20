from __future__ import annotations

import base64
import unittest

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.application.commands.ingest_sources import IngestSources
from kaveh.domain.models import Source
from kaveh.infrastructure.persistence.in_memory import InMemoryConfigRepository


class FakeSourceClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def fetch(self, source: Source) -> str:
        return self.content


class IngestionTests(unittest.TestCase):
    def test_base64_container_is_normalized_and_deduplicated(self) -> None:
        uri = "trojan://secret@example.com:443?security=tls#sample"
        content = base64.b64encode(f"{uri}\n{uri}\ninvalid\n".encode()).decode()
        repo = InMemoryConfigRepository()
        report = IngestSources(
            FakeSourceClient(content), ParserRegistry(), repo
        ).run([Source("fixture", "https://example.com/sub")])
        self.assertEqual(report.discovered_count, 2)
        self.assertEqual(report.parsed_count, 1)
        self.assertEqual(report.duplicate_count, 1)
        self.assertEqual(report.rejected_count, 0)
        self.assertEqual(len(repo.all()), 1)
        stats = report.source_stats["fixture"]
        self.assertEqual(stats.discovered_count, 2)
        self.assertEqual(stats.accepted_count, 2)
        self.assertIsNone(stats.error_code)


if __name__ == "__main__":
    unittest.main()
