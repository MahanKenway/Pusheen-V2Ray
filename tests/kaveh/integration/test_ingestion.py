from __future__ import annotations

import base64
import json
import unittest

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.application.commands.ingest_sources import IngestSources
from kaveh.domain.models import Protocol, Source, SourceFormat
from kaveh.infrastructure.persistence.in_memory import InMemoryConfigRepository


class FakeSourceClient:
    def __init__(self, content: str) -> None:
        self.content = content

    def fetch(self, source: Source) -> str:
        return self.content


class IngestionTests(unittest.TestCase):
    def test_base64_hysteria2_container_is_normalized(self) -> None:
        uri = "hysteria2://secret@hy.example:8443?sni=cdn.example#sample"
        content = base64.b64encode((uri + "\n").encode()).decode()
        repo = InMemoryConfigRepository()
        source = Source(
            "hysteria-fixture",
            "https://example.com/hysteria2.txt",
            allowed_protocols=frozenset({Protocol.HYSTERIA2}),
        )
        report = IngestSources(FakeSourceClient(content), ParserRegistry(), repo).run([source])
        self.assertEqual(report.parsed_count, 1)
        self.assertEqual(report.rejected_count, 0)
        self.assertEqual(repo.all()[0].protocol, Protocol.HYSTERIA2)

    def test_json_profiles_are_ingested_only_under_explicit_protocol_policy(self) -> None:
        content = json.dumps(
            {
                "version": 1,
                "profiles": [
                    {
                        "protocol": "tuic",
                        "server": "tuic.example",
                        "server_port": 443,
                        "uuid": "00000000-0000-0000-0000-000000000001",
                        "password": "secret",
                        "tls": {"server_name": "cdn.example"},
                        "congestion_control": "bbr",
                    },
                    {
                        "protocol": "naive",
                        "server": "naive.example",
                        "server_port": 443,
                        "username": "user",
                        "password": "secret",
                        "tls": {"server_name": "cdn.example"},
                        "quic": True,
                    },
                ],
            }
        )
        repo = InMemoryConfigRepository()
        source = Source(
            "profile-fixture",
            "https://example.com/profiles.json",
            allowed_protocols=frozenset({Protocol.TUIC}),
            format=SourceFormat.JSON_PROFILES,
        )
        report = IngestSources(FakeSourceClient(content), ParserRegistry(), repo).run([source])
        self.assertEqual(report.discovered_count, 2)
        self.assertEqual(report.parsed_count, 1)
        self.assertEqual(report.rejected_count, 1)
        self.assertEqual(repo.all()[0].protocol, Protocol.TUIC)
        self.assertEqual(repo.all()[0].transport.extra["congestion_control"], "bbr")

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
