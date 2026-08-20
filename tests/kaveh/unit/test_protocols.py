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

    def test_hysteria2_parses_official_uri_and_alias(self) -> None:
        raw = "hysteria2://secret@hy.example:8443?sni=cdn.example#hy2"
        config = self.registry.parse(raw)
        alias = self.registry.parse("hy2://secret@hy.example:8443?sni=cdn.example#hy2")
        self.assertEqual(config.protocol, Protocol.HYSTERIA2)
        self.assertEqual(config.host, "hy.example")
        self.assertEqual(config.port, 8443)
        self.assertEqual(config.transport.network, "hysteria")
        self.assertEqual(config.transport.server_name, "cdn.example")
        self.assertEqual(alias.protocol, Protocol.HYSTERIA2)

    def test_tuic_v5_uri_preserves_runtime_fields_and_rejects_insecure_tls(self) -> None:
        raw = (
            "tuic://00000000-0000-0000-0000-000000000001:secret@tuic.example:443"
            "?congestion_control=bbr&udp_relay_mode=native&zero_rtt_handshake=true"
            "&sni=cdn.example&alpn=h3#TUIC-v5"
        )
        config = self.registry.parse(raw)
        self.assertEqual(config.protocol, Protocol.TUIC)
        self.assertEqual(config.transport.network, "udp")
        self.assertEqual(config.transport.security, "tls")
        self.assertEqual(config.transport.server_name, "cdn.example")
        self.assertEqual(config.transport.extra["congestion_control"], "bbr")
        self.assertEqual(config.transport.extra["alpn"], "h3")
        with self.assertRaisesRegex(Exception, "must verify TLS certificates"):
            self.registry.parse(
                "tuic://00000000-0000-0000-0000-000000000001:secret@tuic.example:443?insecure=1"
            )

    def test_identity_ignores_label_and_source(self) -> None:
        first = self.registry.parse("trojan://secret@example.com:443?security=tls#one", "a")
        second = self.registry.parse("trojan://secret@example.com:443?security=tls#two", "b")
        self.assertEqual(first.identity_hash, second.identity_hash)


if __name__ == "__main__":
    unittest.main()
