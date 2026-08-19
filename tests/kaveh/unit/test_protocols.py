from __future__ import annotations

import base64
import json
import unittest

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.domain.models import Protocol


class ProtocolParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = ParserRegistry()

    def test_vless_preserves_transport_and_identity(self) -> None:
        config = self.registry.parse(
            "vless://abc@example.com:443?type=grpc&security=reality&sni=cdn.example.com&serviceName=edge#Alpha",
            source_id="one",
        )
        self.assertEqual(config.protocol, Protocol.VLESS)
        self.assertEqual(config.transport.network, "grpc")
        self.assertEqual(config.transport.security, "reality")
        self.assertEqual(config.transport.server_name, "cdn.example.com")
        self.assertEqual(config.label, "Alpha")
        self.assertEqual(len(config.identity_hash or ""), 64)
        self.assertNotIn("abc", config.redacted_summary())

    def test_vmess_preserves_connection_fields(self) -> None:
        payload = {
            "v": "2",
            "ps": "sample",
            "add": "vm.example.com",
            "port": "443",
            "id": "00000000-0000-0000-0000-000000000001",
            "net": "ws",
            "tls": "tls",
            "sni": "cdn.example.com",
            "path": "/ws",
        }
        raw = "vmess://" + base64.b64encode(json.dumps(payload).encode()).decode()
        config = self.registry.parse(raw)
        self.assertEqual(config.protocol, Protocol.VMESS)
        self.assertEqual(config.host, "vm.example.com")
        self.assertEqual(config.transport.network, "ws")
        self.assertEqual(config.transport.path, "/ws")

    def test_identity_ignores_label_and_source(self) -> None:
        first = self.registry.parse("trojan://secret@example.com:443?security=tls#one", "a")
        second = self.registry.parse("trojan://secret@example.com:443?security=tls#two", "b")
        self.assertEqual(first.identity_hash, second.identity_hash)


if __name__ == "__main__":
    unittest.main()
