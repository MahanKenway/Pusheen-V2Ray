from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from kaveh.config.settings import RuntimeSettings, SettingsError


class PostgresFoundationTests(unittest.TestCase):
    def test_database_url_is_required_only_when_persistence_is_enabled(self) -> None:
        settings = RuntimeSettings(
            database_url=None,
            xray_binary=None,
            probe_url=None,
            xray_startup_timeout_seconds=5,
            xray_probe_timeout_seconds=8,
            xray_work_root=Path(".artifacts/xray"),
            vantage_id="default",
        )
        with self.assertRaises(SettingsError):
            settings.require_database_url()

    def test_initial_migration_defines_history_and_status_tables(self) -> None:
        migration = Path("migrations/001_initial.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS configs", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS probe_results", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS config_status", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS publication_snapshots", migration)


if __name__ == "__main__":
    unittest.main()
