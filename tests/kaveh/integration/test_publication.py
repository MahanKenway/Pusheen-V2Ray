from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.adapters.publishers.snapshot_publisher import SnapshotPublisher
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
            self.assertEqual((root / "subscriptions" / "all.txt").read_text(), config.raw_uri + "\n")
            self.assertTrue((root / "subscriptions" / "all.base64").exists())
            self.assertTrue((root / "subscriptions" / "trojan.base64").exists())

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


if __name__ == "__main__":
    unittest.main()
