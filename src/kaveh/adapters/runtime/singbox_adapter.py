"""Pinned sing-box runtime adapter for TUIC and Naive end-to-end validation.

TUIC and NaiveProxy are deliberately isolated from Xray because Project X does not provide these proxy implementations. This adapter follows the same evidence contract as
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
    """Build narrowly-scoped, documented sing-box probe configurations."""

    def build(self, config: CanonicalConfig, socks_port: int) -> dict[str, Any]:
        if not config.identity_hash:
            raise SingBoxBuildError("Configuration identity is required")
        if config.protocol is Protocol.TUIC:
            outbound = self._build_tuic(config)
        elif config.protocol is Protocol.NAIVE:
            outbound = self._build_naive(config)
        else:
            raise SingBoxBuildError("Sing-box adapter does not support this protocol")
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

    def _tls(self, config: CanonicalConfig) -> dict[str, Any]:
        tls: dict[str, Any] = {"enabled": True}
        if config.transport.server_name:
            tls["server_name"] = config.transport.server_name
        if config.transport.extra.get("ech"):
            tls["ech"] = {"enabled": True, "config": [config.transport.extra["ech"]]}
        if config.transport.extra.get("alpn"):
            alpn = [value.strip() for value in config.transport.extra["alpn"].split(",") if value.strip()]
            if not alpn or len(alpn) > 8:
                raise SingBoxBuildError("Invalid TLS ALPN list")
            tls["alpn"] = alpn
        return tls

    def _build_tuic(self, config: CanonicalConfig) -> dict[str, Any]:
        user_uuid, separator, password = config.credential.partition(":")
        if not separator or not password:
            raise SingBoxBuildError("TUIC requires uuid and password")
        try:
            uuid.UUID(user_uuid)
        except ValueError as exc:
            raise SingBoxBuildError("TUIC requires a valid UUID") from exc
        outbound: dict[str, Any] = {
            "type": "tuic",
            "tag": "candidate",
            "server": config.host,
            "server_port": config.port,
            "uuid": user_uuid,
            "password": password,
            "tls": self._tls(config),
        }
        congestion = config.transport.extra.get("congestion_control")
        if congestion:
            if congestion not in {"cubic", "new_reno", "bbr"}:
                raise SingBoxBuildError("Unsupported TUIC congestion control")
            outbound["congestion_control"] = congestion
        for field in ("udp_relay_mode", "network", "heartbeat"):
            if config.transport.extra.get(field):
                outbound[field] = config.transport.extra[field]
        for field in ("udp_over_stream", "zero_rtt_handshake"):
            if config.transport.extra.get(field) == "true":
                outbound[field] = True
        if outbound.get("udp_relay_mode") and outbound.get("udp_over_stream"):
            raise SingBoxBuildError("TUIC udp_relay_mode conflicts with udp_over_stream")
        return outbound

    def _build_naive(self, config: CanonicalConfig) -> dict[str, Any]:
        username, separator, password = config.credential.partition(":")
        if not separator or not username or not password:
            raise SingBoxBuildError("Naive requires username and password")
        if config.transport.extra.get("insecure"):
            raise SingBoxBuildError("Naive insecure TLS is not allowed")
        outbound: dict[str, Any] = {
            "type": "naive",
            "tag": "candidate",
            "server": config.host,
            "server_port": config.port,
            "username": username,
            "password": password,
            "tls": self._tls(config),
        }
        if config.transport.extra.get("quic") == "true":
            outbound["quic"] = True
        congestion = config.transport.extra.get("quic_congestion_control")
        if congestion:
            if congestion not in {"bbr", "bbr2", "cubic", "reno"}:
                raise SingBoxBuildError("Unsupported Naive QUIC congestion control")
            outbound["quic_congestion_control"] = congestion
        if config.transport.extra.get("insecure_concurrency"):
            try:
                concurrency = int(config.transport.extra["insecure_concurrency"])
            except ValueError as exc:
                raise SingBoxBuildError("Invalid Naive insecure concurrency") from exc
            if not 0 <= concurrency <= 4:
                raise SingBoxBuildError("Naive insecure concurrency is outside policy")
            outbound["insecure_concurrency"] = concurrency
        return outbound


class SingBoxEndToEndProbe:
    """Run one TUIC or Naive candidate through a disposable sing-box SOCKS listener."""

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
