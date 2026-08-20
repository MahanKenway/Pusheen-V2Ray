"""Pinned sing-box runtime adapter for TUIC end-to-end validation.

TUIC is deliberately isolated from Xray because Project X does not provide a
TUIC proxy implementation. This adapter follows the same evidence contract as
Xray: a transient local SOCKS listener must successfully proxy an approved
HTTPS request before an end-to-end pass is recorded.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx

from kaveh.adapters.runtime.xray_adapter import _probe_via_socks, _reserve_local_port, _terminate, _wait_for_listener
from kaveh.config.settings import RuntimeSettings, SettingsError
from kaveh.domain.models import CanonicalConfig, ProbeResult, ProbeStage, Protocol


class SingBoxBuildError(ValueError):
    pass


class SingBoxConfigBuilder:
    """Build the narrow sing-box configuration required to probe a TUIC URI."""

    def build(self, config: CanonicalConfig, socks_port: int) -> dict[str, Any]:
        if config.protocol is not Protocol.TUIC:
            raise SingBoxBuildError("Sing-box adapter only supports TUIC")
        if not config.identity_hash:
            raise SingBoxBuildError("Configuration identity is required")
        user_uuid, separator, password = config.credential.partition(":")
        if not separator or not password:
            raise SingBoxBuildError("TUIC requires uuid and password")
        try:
            uuid.UUID(user_uuid)
        except ValueError as exc:
            raise SingBoxBuildError("TUIC requires a valid UUID") from exc

        tls: dict[str, Any] = {"enabled": True}
        if config.transport.server_name:
            tls["server_name"] = config.transport.server_name
        outbound: dict[str, Any] = {
            "type": "tuic",
            "tag": "candidate",
            "server": config.host,
            "server_port": config.port,
            "uuid": user_uuid,
            "password": password,
            "tls": tls,
        }
        congestion = config.transport.extra.get("congestion_control")
        if congestion:
            if congestion not in {"cubic", "new_reno", "bbr"}:
                raise SingBoxBuildError("Unsupported TUIC congestion control")
            outbound["congestion_control"] = congestion
        return {
            "log": {"disabled": True},
            "inbounds": [
                {
                    "type": "socks",
                    "tag": "probe-socks",
                    "listen": "127.0.0.1",
                    "listen_port": socks_port,
                }
            ],
            "outbounds": [outbound, {"type": "block", "tag": "block"}],
            "route": {"rules": [{"inbound": ["probe-socks"], "outbound": "candidate"}]},
        }


class SingBoxEndToEndProbe:
    """Run one TUIC candidate through a disposable sing-box SOCKS listener."""

    def __init__(self, settings: RuntimeSettings, builder: SingBoxConfigBuilder | None = None) -> None:
        self.settings = settings
        self.builder = builder or SingBoxConfigBuilder()

    def run(self, config: CanonicalConfig) -> ProbeResult:
        identity = config.identity_hash or "unknown"
        try:
            binary, probe_urls = self.settings.require_singbox_runtime()
        except SettingsError:
            return ProbeResult.failed(identity, ProbeStage.END_TO_END, "SINGBOX_RUNTIME_NOT_CONFIGURED", self.settings.vantage_id)
        if not binary.is_file() or not binary.exists():
            return ProbeResult.failed(identity, ProbeStage.END_TO_END, "SINGBOX_BINARY_NOT_FOUND", self.settings.vantage_id)
        try:
            socks_port = _reserve_local_port()
            runtime_config = self.builder.build(config, socks_port)
        except SingBoxBuildError:
            return ProbeResult.failed(identity, ProbeStage.RUNTIME_BUILD, "SINGBOX_CONFIG_BUILD_FAILED", self.settings.vantage_id)

        work_root = self.settings.xray_work_root.parent / "singbox"
        work_root.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="probe-", dir=work_root) as workspace:
            config_path = Path(workspace) / "config.json"
            config_path.write_text(json.dumps(runtime_config), encoding="utf-8")
            process: subprocess.Popen[bytes] | None = None
            try:
                process = subprocess.Popen(
                    [str(binary), "run", "-c", str(config_path)],
                    cwd=workspace,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                if not _wait_for_listener(process, socks_port, self.settings.xray_startup_timeout_seconds):
                    return ProbeResult.failed(identity, ProbeStage.RUNTIME_BUILD, "SINGBOX_STARTUP_FAILED", self.settings.vantage_id)
                statuses: list[int] = []
                for probe_url in probe_urls:
                    try:
                        status = _probe_via_socks(probe_url, socks_port, self.settings.xray_probe_timeout_seconds)
                        statuses.append(status)
                        if 200 <= status < 300:
                            return ProbeResult.passed(
                                identity,
                                ProbeStage.END_TO_END,
                                latency_ms=int((time.perf_counter() - started) * 1000),
                                vantage_id=self.settings.vantage_id,
                            )
                    except (httpx.HTTPError, TimeoutError):
                        continue
                return ProbeResult.failed(
                    identity,
                    ProbeStage.END_TO_END,
                    "ALL_E2E_PROBES_FAILED" if not statuses else "PROBE_STATUS_INVALID",
                    self.settings.vantage_id,
                )
            except (OSError, httpx.HTTPError, TimeoutError):
                return ProbeResult.failed(identity, ProbeStage.END_TO_END, "SINGBOX_E2E_PROBE_FAILED", self.settings.vantage_id)
            finally:
                _terminate(process)
