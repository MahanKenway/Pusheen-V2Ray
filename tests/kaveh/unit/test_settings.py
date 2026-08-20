from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from kaveh.config.settings import RuntimeSettings, SettingsError


class RuntimeSettingsTests(unittest.TestCase):
    def test_probe_urls_are_unique_and_primary_first(self) -> None:
        settings = RuntimeSettings(
            database_url=None,
            xray_binary=Path("xray"),
            probe_url="https://primary.example/health",
            probe_fallback_url="https://fallback.example/trace",
            xray_startup_timeout_seconds=5,
            xray_probe_timeout_seconds=8,
            xray_work_root=Path(".artifacts/xray"),
            vantage_id="test",
        )
        self.assertEqual(
            settings.probe_urls,
            ("https://primary.example/health", "https://fallback.example/trace"),
        )

    def test_rejects_non_https_fallback_probe_url(self) -> None:
        environment = {"KAVEH_PROBE_FALLBACK_URL": "http://invalid.example"}
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(SettingsError):
                RuntimeSettings.from_environment()


if __name__ == "__main__":
    unittest.main()
