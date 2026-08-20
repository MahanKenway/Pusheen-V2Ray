from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.adapters.runtime.xray_adapter import XrayConfigBuilder, XrayEndToEndProbe
from kaveh.config.settings import RuntimeSettings
from kaveh.domain.models import ProbeStage


class XrayAdapterTests(unittest.TestCase):
    def test_reality_vless_builds_local_socks_and_reality_outbound(self) -> None:
        config = ParserRegistry().parse(
            "vless://00000000-0000-0000-0000-000000000001@edge.example:443"
            "?type=grpc&security=reality&sni=cdn.example&pbk=public-key&sid=abcd"
            "&fp=chrome&serviceName=api#fixture"
        )
        built = XrayConfigBuilder().build(config, 39001)
        self.assertEqual(built["inbounds"][0]["listen"], "127.0.0.1")
        self.assertEqual(built["inbounds"][0]["port"], 39001)
        outbound = built["outbounds"][0]
        self.assertEqual(outbound["protocol"], "vless")
        self.assertEqual(outbound["streamSettings"]["network"], "grpc")
        self.assertEqual(outbound["streamSettings"]["realitySettings"]["publicKey"], "public-key")
        self.assertEqual(outbound["streamSettings"]["realitySettings"]["shortId"], "abcd")

    def test_hysteria2_builds_documented_outbound_and_transport(self) -> None:
        config = ParserRegistry().parse(
            "hysteria2://secret@hy.example:8443?sni=cdn.example&insecure=1&pinSHA256=abcd#fixture"
        )
        built = XrayConfigBuilder().build(config, 39002)
        outbound = built["outbounds"][0]
        self.assertEqual(outbound["protocol"], "hysteria")
        self.assertEqual(outbound["settings"], {"version": 2, "address": "hy.example", "port": 8443})
        self.assertEqual(outbound["streamSettings"]["method"], "hysteria")
        self.assertEqual(outbound["streamSettings"]["hysteriaSettings"]["auth"], "secret")
        self.assertEqual(outbound["streamSettings"]["tlsSettings"]["serverName"], "cdn.example")
        self.assertTrue(outbound["streamSettings"]["tlsSettings"]["allowInsecure"])
        self.assertEqual(outbound["streamSettings"]["tlsSettings"]["pinnedPeerCertSha256"], "abcd")

    def test_runner_returns_safe_configuration_error_without_runtime(self) -> None:
        config = ParserRegistry().parse("trojan://secret@example.com:443?security=tls")
        settings = RuntimeSettings(
            database_url=None,
            xray_binary=None,
            probe_url=None,
            xray_startup_timeout_seconds=1,
            xray_probe_timeout_seconds=1,
            xray_work_root=Path(tempfile.gettempdir()),
            vantage_id="test",
        )
        result = XrayEndToEndProbe(settings).run(config)
        self.assertEqual(result.stage, ProbeStage.END_TO_END)
        self.assertEqual(result.error_code, "XRAY_RUNTIME_NOT_CONFIGURED")
        self.assertNotIn("secret", result.error_code or "")


if __name__ == "__main__":
    unittest.main()
