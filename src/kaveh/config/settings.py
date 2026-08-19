"""Environment-backed runtime settings for Kaveh services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class SettingsError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimeSettings:
    database_url: str | None
    xray_binary: Path | None
    probe_url: str | None
    xray_startup_timeout_seconds: float
    xray_probe_timeout_seconds: float
    xray_work_root: Path
    vantage_id: str

    @classmethod
    def from_environment(cls) -> "RuntimeSettings":
        database_url = os.getenv("KAVEH_DATABASE_URL")
        xray_binary = os.getenv("XRAY_BINARY")
        probe_url = os.getenv("KAVEH_PROBE_URL")
        if probe_url:
            parsed = urlsplit(probe_url)
            if parsed.scheme != "https" or not parsed.hostname:
                raise SettingsError("KAVEH_PROBE_URL must be an absolute HTTPS URL")
        return cls(
            database_url=database_url,
            xray_binary=Path(xray_binary) if xray_binary else None,
            probe_url=probe_url,
            xray_startup_timeout_seconds=float(os.getenv("XRAY_STARTUP_TIMEOUT_SECONDS", "5")),
            xray_probe_timeout_seconds=float(os.getenv("XRAY_PROBE_TIMEOUT_SECONDS", "8")),
            xray_work_root=Path(os.getenv("XRAY_WORK_ROOT", ".artifacts/xray")),
            vantage_id=os.getenv("KAVEH_VANTAGE_ID", "default"),
        )

    def require_database_url(self) -> str:
        if not self.database_url:
            raise SettingsError("KAVEH_DATABASE_URL is required for PostgreSQL persistence")
        return self.database_url

    def require_xray_runtime(self) -> tuple[Path, str]:
        if not self.xray_binary:
            raise SettingsError("XRAY_BINARY is required for end-to-end validation")
        if not self.probe_url:
            raise SettingsError("KAVEH_PROBE_URL is required for end-to-end validation")
        return self.xray_binary, self.probe_url
