from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.adapters.publishers.singbox_urltest_publisher import SingBoxUrlTestPublisher
from kaveh.domain.models import CanonicalConfig, Protocol, Transport
from kaveh.domain.services.identity import with_identity
from kaveh.infrastructure.storage.filesystem_store import FileSystemArtifactStore


class SingBoxUrlTestPublisherTests(unittest.TestCase):
    def test_publishes_local_urltest_profile_without_direct_fallback(self) -> None:
        configs = [
            ParserRegistry().parse(
                "vless://00000000-0000-0000-0000-000000000001@vless.example:443?type=ws&security=tls&sni=cdn.example&path=%2Fws#vless"
            ),
            with_identity(
                CanonicalConfig(
                    protocol=Protocol.VMESS,
                    host="vmess.example",
                    port=80,
                    credential="00000000-0000-0000-0000-000000000002",
                    transport=Transport(network="ws", security="none", path="/socket"),
                    label="vmess",
                    raw_uri="vmess-fixture",
                )
            ),
            ParserRegistry().parse(
                "trojan://secret@trojan.example:443?type=ws&security=tls&sni=cdn.example&path=%2Ft#trojan"
            ),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = SingBoxUrlTestPublisher(FileSystemArtifactStore(root)).publish(configs)
            self.assertTrue(report.published)
            self.assertEqual(report.count, 3)
            profile = json.loads((root / "profiles" / "outage-singbox.json").read_text())
            auto = next(item for item in profile["outbounds"] if item["tag"] == "outage-auto")
            self.assertEqual(auto["type"], "urltest")
            self.assertEqual(auto["interval"], "10m")
            self.assertFalse(auto["interrupt_exist_connections"])
            self.assertNotIn("direct", {item["type"] for item in profile["outbounds"]})
            self.assertEqual(profile["route"]["final"], "blocked")
            self.assertTrue((root / "profiles" / "outage-singbox.meta.v1.json").exists())

    def test_rejects_reality_without_publishing_empty_profile(self) -> None:
        config = ParserRegistry().parse(
            "vless://00000000-0000-0000-0000-000000000001@vless.example:443?type=tcp&security=reality&sni=cdn.example&pbk=public-key#reality"
        )
        with tempfile.TemporaryDirectory() as temporary:
            report = SingBoxUrlTestPublisher(FileSystemArtifactStore(Path(temporary))).publish([config])
            self.assertFalse(report.published)
            self.assertEqual(report.reason, "NO_SINGBOX_COMPATIBLE_OUTAGE_CONFIGS")
            self.assertEqual(report.rejected_count, 1)


if __name__ == "__main__":
    unittest.main()
