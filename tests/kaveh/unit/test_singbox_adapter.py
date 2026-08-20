from __future__ import annotations

import unittest

from kaveh.adapters.runtime.singbox_adapter import SingBoxConfigBuilder
from kaveh.domain.models import CanonicalConfig, Protocol, Transport
from kaveh.domain.services.identity import with_identity


class SingBoxAdapterTests(unittest.TestCase):
    def test_naive_builds_documented_outbound(self) -> None:
        config = with_identity(
            CanonicalConfig(
                protocol=Protocol.NAIVE,
                host="naive.example",
                port=443,
                credential="user:secret",
                transport=Transport(
                    server_name="cdn.example",
                    extra={"quic": "true", "quic_congestion_control": "bbr2"},
                ),
                raw_uri="naive-profile",
            )
        )
        built = SingBoxConfigBuilder().build(config, 39004)
        outbound = built["outbounds"][0]
        self.assertEqual(outbound["type"], "naive")
        self.assertEqual(outbound["username"], "user")
        self.assertEqual(outbound["password"], "secret")
        self.assertTrue(outbound["quic"])
        self.assertEqual(outbound["quic_congestion_control"], "bbr2")
        self.assertEqual(outbound["tls"]["server_name"], "cdn.example")

    def test_tuic_builds_local_socks_and_documented_outbound(self) -> None:
        config = with_identity(
            CanonicalConfig(
                protocol=Protocol.TUIC,
                host="tuic.example",
                port=443,
                credential="00000000-0000-0000-0000-000000000001:secret",
                transport=Transport(
                    server_name="cdn.example",
                    extra={
                        "congestion_control": "bbr",
                        "udp_relay_mode": "native",
                        "heartbeat": "10s",
                        "zero_rtt_handshake": "true",
                    },
                ),
                raw_uri="tuic-profile",
            )
        )
        built = SingBoxConfigBuilder().build(config, 39004)
        self.assertEqual(built["inbounds"][0]["type"], "socks")
        self.assertEqual(built["inbounds"][0]["listen_port"], 39004)
        outbound = built["outbounds"][0]
        self.assertEqual(outbound["type"], "tuic")
        self.assertEqual(outbound["server"], "tuic.example")
        self.assertEqual(outbound["server_port"], 443)
        self.assertEqual(outbound["uuid"], "00000000-0000-0000-0000-000000000001")
        self.assertEqual(outbound["password"], "secret")
        self.assertEqual(outbound["congestion_control"], "bbr")
        self.assertEqual(outbound["udp_relay_mode"], "native")
        self.assertEqual(outbound["heartbeat"], "10s")
        self.assertTrue(outbound["zero_rtt_handshake"])
        self.assertTrue(outbound["tls"]["enabled"])
        self.assertEqual(outbound["tls"]["server_name"], "cdn.example")


if __name__ == "__main__":
    unittest.main()
