from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from kaveh.adapters.protocols.registry import ParserRegistry
from kaveh.adapters.runtime.xray_adapter import XrayConfigBuilder


@unittest.skipUnless(os.getenv("XRAY_TEST_BINARY"), "XRAY_TEST_BINARY is not configured")
class XrayRuntimeTests(unittest.TestCase):
    def test_generated_config_is_accepted_by_xray(self) -> None:
        binary = Path(os.environ["XRAY_TEST_BINARY"])
        self.assertTrue(binary.is_file())
        config = ParserRegistry().parse(
            "vless://00000000-0000-0000-0000-000000000001@example.com:443"
            "?type=ws&security=tls&sni=example.com&path=%2Fsocket#fixture"
        )
        generated = XrayConfigBuilder().build(config, 39001)
        with tempfile.TemporaryDirectory() as workspace:
            config_path = Path(workspace) / "config.json"
            config_path.write_text(json.dumps(generated), encoding="utf-8")
            completed = subprocess.run(
                [str(binary), "run", "-test", "-c", str(config_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
