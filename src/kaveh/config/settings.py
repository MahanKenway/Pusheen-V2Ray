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
    probe_fallback_url: str | None = None
    validation_workers: int = 1

    @classmethod
    def from_environment(cls) -> "RuntimeSettings":
        database_url = os.getenv("KAVEH_DATABASE_URL")
        xray_binary = os.getenv("XRAY_BINARY")
        probe_url = os.getenv("KAVEH_PROBE_URL")
        probe_fallback_url = os.getenv("KAVEH_PROBE_FALLBACK_URL")
        for name, value in (
            ("KAVEH_PROBE_URL", probe_url),
            ("KAVEH_PROBE_FALLBACK_URL", probe_fallback_url),
        ):
            if value:
                parsed = urlsplit(value)
                if parsed.scheme != "https" or not parsed.hostname:
                    raise SettingsError(f"{name} must be an absolute HTTPS URL")
        validation_workers = int(os.getenv("KAVEH_VALIDATION_WORKERS", "1"))
        if validation_workers < 1 or validation_workers > 8:
            raise SettingsError("KAVEH_VALIDATION_WORKERS must be between 1 and 8")
        return cls(
            database_url=database_url,
            xray_binary=Path(xray_binary) if xray_binary else None,
            probe_url=probe_url,
            probe_fallback_url=probe_fallback_url,
            xray_startup_timeout_seconds=float(os.getenv("XRAY_STARTUP_TIMEOUT_SECONDS", "5")),
            xray_probe_timeout_seconds=float(os.getenv("XRAY_PROBE_TIMEOUT_SECONDS", "8")),
            xray_work_root=Path(os.getenv("XRAY_WORK_ROOT", ".artifacts/xray")),
            vantage_id=os.getenv("KAVEH_VANTAGE_ID", "default"),
            validation_workers=validation_workers,
        )

    @property
    def probe_urls(self) -> tuple[str, ...]:
        """Configured unique probe endpoints, primary first."""

        return tuple(dict.fromkeys(url for url in (self.probe_url, self.probe_fallback_url) if url))

    def require_database_url(self) -> str:
        if not self.database_url:
            raise SettingsError("KAVEH_DATABASE_URL is required for PostgreSQL persistence")
        return self.database_url

    def require_xray_runtime(self) -> tuple[Path, tuple[str, ...]]:
        if not self.xray_binary:
            raise SettingsError("XRAY_BINARY is required for end-to-end validation")
        if not self.probe_urls:
            raise SettingsError("KAVEH_PROBE_URL is required for end-to-end validation")
        return self.xray_binary, self.probe_urls
