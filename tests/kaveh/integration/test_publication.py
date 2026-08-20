from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.adapters.publishers.reachable_publisher import ReachableFeedPublisher
from kaveh.adapters.publishers.snapshot_publisher import SnapshotPublisher
from kaveh.adapters.publishers.status_publisher import StatusPublisher
from kaveh.domain.models import ScoreCard
from kaveh.infrastructure.storage.filesystem_store import FileSystemArtifactStore


class PublicationTests(unittest.TestCase):
    def test_publisher_writes_immutable_snapshot_and_latest_pointer(self) -> None:
        config = ParserRegistry().parse("trojan://secret@example.com:443?security=tls#sample")
        card = ScoreCard(
            identity_hash=config.identity_hash or "",
            score=92,
            policy_version="kaveh-standard-v1",
            explanation={"success": 50, "latency": 20, "freshness": 20, "source_trust": 2},
            qualified=True,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = SnapshotPublisher(
                FileSystemArtifactStore(root), "kaveh-standard-v1"
            ).publish([config], [card])
            self.assertIsNotNone(snapshot)
            assert snapshot is not None
            self.assertEqual((root / "latest.txt").read_text().strip(), snapshot.snapshot_id)
            manifest = root / "snapshots" / snapshot.snapshot_id / "manifest.v1.json"
            self.assertTrue(manifest.exists())
            self.assertNotIn("secret", manifest.read_text())
            self.assertEqual((root / "subscriptions" / "strict.txt").read_text(), config.raw_uri + "\n")
            self.assertTrue((root / "subscriptions" / "strict.base64").exists())
            self.assertTrue((root / "subscriptions" / "strict-trojan.base64").exists())

    def test_publisher_does_not_replace_latest_when_nothing_qualifies(self) -> None:
        config = ParserRegistry().parse("trojan://secret@example.com:443?security=tls#sample")
        card = ScoreCard(
            identity_hash=config.identity_hash or "",
            score=10,
            policy_version="kaveh-standard-v1",
            explanation={"success": 0, "latency": 0, "freshness": 0, "source_trust": 10},
            qualified=False,
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = SnapshotPublisher(
                FileSystemArtifactStore(root), "kaveh-standard-v1"
            ).publish([config], [card])
            self.assertIsNone(snapshot)
            self.assertFalse((root / "latest.txt").exists())

    def test_publisher_skips_unchanged_stable_feed(self) -> None:
        config = ParserRegistry().parse("trojan://secret@example.com:443?security=tls#sample")
        card = ScoreCard(
            identity_hash=config.identity_hash or "",
            score=92,
            policy_version="kaveh-standard-v1",
            explanation={"success": 50, "latency": 20, "freshness": 20, "source_trust": 2},
            qualified=True,
        )
        with tempfile.TemporaryDirectory() as temporary:
            publisher = SnapshotPublisher(FileSystemArtifactStore(Path(temporary)), "kaveh-standard-v1")
            self.assertIsNotNone(publisher.publish([config], [card]))
            self.assertIsNone(publisher.publish([config], [card]))
            self.assertEqual(publisher.last_skip_reason, "NO_QUALIFIED_FEED_CHANGE")

    def test_reachable_publisher_writes_separate_feed_and_skips_unchanged(self) -> None:
        config = ParserRegistry().parse("vless://secret@example.com:443?type=tcp&security=tls#sample")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            publisher = ReachableFeedPublisher(FileSystemArtifactStore(root))
            report = publisher.publish([config])
            self.assertTrue(report.published)
            self.assertEqual(report.count, 1)
            self.assertIsNotNone(report.snapshot_id)
            self.assertEqual(
                (root / "subscriptions" / "all.txt").read_text(),
                config.raw_uri + "\n",
            )
            self.assertTrue((root / "subscriptions" / "all.base64").exists())
            self.assertEqual(
                (root / "subscriptions" / "reachable.txt").read_text(),
                config.raw_uri + "\n",
            )
            self.assertTrue((root / "subscriptions" / "reachable.base64").exists())
            self.assertEqual(
                (root / "subscriptions" / "reachable-vless.txt").read_text(),
                config.raw_uri + "\n",
            )
            self.assertTrue((root / "subscriptions" / "reachable-fast.txt").exists())
            self.assertTrue((root / "subscriptions" / "reachable.manifest.v1.json").exists())
            self.assertTrue((root / "reachable-latest.txt").exists())
            self.assertFalse(publisher.publish([config]).published)

    def test_primary_feed_preserves_latency_order_and_writes_protocol_variants(self) -> None:
        trojan = ParserRegistry().parse("trojan://secret@trojan.example:443?security=tls#trojan")
        vless = ParserRegistry().parse("vless://secret@vless.example:443?type=tcp&security=tls#vless")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ReachableFeedPublisher(FileSystemArtifactStore(root)).publish([trojan, vless])
            self.assertEqual(
                (root / "subscriptions" / "all.txt").read_text().splitlines(),
                [trojan.raw_uri, vless.raw_uri],
            )
            self.assertEqual(
                (root / "subscriptions" / "reachable.txt").read_text().splitlines(),
                [trojan.raw_uri, vless.raw_uri],
            )
            self.assertEqual(
                (root / "subscriptions" / "all-trojan.txt").read_text(), trojan.raw_uri + "\n"
            )
            self.assertEqual(
                (root / "subscriptions" / "all-vless.txt").read_text(), vless.raw_uri + "\n"
            )

    def test_status_publisher_writes_public_safe_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            StatusPublisher(FileSystemArtifactStore(root)).publish(
                ingestion={"parsed": 12, "source_errors": {}},
                validation={"candidates": 10, "probe_endpoints": 2},
                strict_publication={"count": 7, "published": True},
                reachable_publication={"count": 34, "published": True},
                source_health=(
                    {
                        "source_id": "reviewed-source",
                        "enabled": True,
                        "quarantined": False,
                        "total_runs": 3,
                        "successful_runs": 3,
                        "consecutive_failures": 0,
                    },
                ),
                reachable_max_age_hours=72,
            )
            payload = json.loads((root / "status.json").read_text())
            self.assertEqual(payload["feeds"]["strict"]["count"], 7)
            self.assertEqual(payload["feeds"]["strict"]["path"], "subscriptions/strict.txt")
            self.assertEqual(payload["feeds"]["primary"]["path"], "subscriptions/all.txt")
            self.assertEqual(payload["feeds"]["primary"]["minimum_target"], 100)
            self.assertEqual(payload["feeds"]["balanced"]["max_evidence_age_hours"], 72)
            self.assertEqual(payload["sources"]["healthy"], 1)
            self.assertNotIn("vless://", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
