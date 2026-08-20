"""Xray runtime adapter for isolated end-to-end probes.

The adapter builds a one-use local SOCKS inbound and a single proxy outbound.
It never writes credentials to logs and always uses a temporary workspace.
"""

from __future__ import annotations

import json
import socket
import subprocess
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

import httpx

from kaveh.config.settings import RuntimeSettings, SettingsError
from kaveh.domain.models import CanonicalConfig, ProbeResult, ProbeStage, Protocol


class XrayBuildError(ValueError):
    pass


class XrayConfigBuilder:
    """Convert a CanonicalConfig into the narrow Xray config needed for a probe."""

    def build(self, config: CanonicalConfig, socks_port: int) -> dict[str, Any]:
        if not config.identity_hash:
            raise XrayBuildError("Configuration identity is required")
        proxy_outbound = self.build_outbound(config, "candidate")
        return {
            "log": {"loglevel": "warning"},
            "inbounds": [
                {
                    "tag": "probe-socks",
                    "listen": "127.0.0.1",
                    "port": socks_port,
                    "protocol": "socks",
                    "settings": {"auth": "noauth", "udp": False},
                }
            ],
            "outbounds": [
                proxy_outbound,
                {"tag": "blocked", "protocol": "blackhole", "settings": {}},
            ],
            "routing": {
                "domainStrategy": "AsIs",
                "rules": [
                    {"type": "field", "inboundTag": ["probe-socks"], "outboundTag": "candidate"}
                ],
            },
        }

    def build_outbound(self, config: CanonicalConfig, tag: str) -> dict[str, Any]:
        """Build one client outbound for a validated local runtime profile."""

        if not config.identity_hash:
            raise XrayBuildError("Configuration identity is required")
        return {
            "tag": tag,
            "protocol": "hysteria" if config.protocol is Protocol.HYSTERIA2 else config.protocol.value,
            "settings": self._outbound_settings(config),
            "streamSettings": self._stream_settings(config),
        }

    def _outbound_settings(self, config: CanonicalConfig) -> dict[str, Any]:
        server = {"address": config.host, "port": config.port}
        if config.protocol is Protocol.VLESS:
            user = {"id": config.credential, "encryption": config.transport.extra.get("encryption", "none")}
            flow = config.transport.extra.get("flow")
            if flow:
                user["flow"] = flow
            server["users"] = [user]
            return {"vnext": [server]}
        if config.protocol is Protocol.VMESS:
            server["users"] = [
                {
                    "id": config.credential,
                    "alterId": _int_or_default(config.transport.extra.get("aid"), 0),
                    "security": config.transport.extra.get("scy", "auto"),
                }
            ]
            return {"vnext": [server]}
        if config.protocol is Protocol.TROJAN:
            server["password"] = config.credential
            return {"servers": [server]}
        if config.protocol is Protocol.SHADOWSOCKS:
            method, separator, password = config.credential.partition(":")
            if not separator or not method or not password:
                raise XrayBuildError("Shadowsocks requires method and password")
            server["method"] = method
            server["password"] = password
            return {"servers": [server]}
        if config.protocol is Protocol.HYSTERIA2:
            return {"version": 2, "address": config.host, "port": config.port}
        raise XrayBuildError("Protocol is not enabled in the Xray adapter")

    def _stream_settings(self, config: CanonicalConfig) -> dict[str, Any]:
        transport = config.transport
        if config.protocol is Protocol.HYSTERIA2:
            unsupported = {
                key
                for key in ("obfs", "obfs-password")
                if transport.extra.get(key)
            }
            if unsupported:
                raise XrayBuildError("Unsupported Hysteria2 URI option")
            settings: dict[str, Any] = {
                "method": "hysteria",
                "security": "tls",
                "hysteriaSettings": {"version": 2, "auth": config.credential},
            }
            tls_settings = _tls_settings(transport.server_name)
            if transport.extra.get("insecure") == "1":
                tls_settings["allowInsecure"] = True
            if transport.extra.get("pinSHA256"):
                tls_settings["pinnedPeerCertSha256"] = transport.extra["pinSHA256"]
            if transport.extra.get("ech"):
                tls_settings["echConfigList"] = transport.extra["ech"]
            settings["tlsSettings"] = tls_settings
            return settings
        settings: dict[str, Any] = {
            "network": transport.network,
            "security": transport.security,
        }
        if transport.network == "ws":
            settings["wsSettings"] = {"path": transport.path or "/"}
        elif transport.network == "grpc":
            settings["grpcSettings"] = {"serviceName": transport.service_name or ""}
        elif transport.network == "httpupgrade":
            settings["httpupgradeSettings"] = {"path": transport.path or "/"}
        elif transport.network == "h2":
            settings["httpSettings"] = {"path": transport.path or "/"}

        if transport.security in {"tls", "xtls"}:
            settings["tlsSettings"] = _tls_settings(transport.server_name)
        elif transport.security == "reality":
            settings["realitySettings"] = _reality_settings(config)
        return settings


class XrayEndToEndProbe:
    """Launch Xray in a temporary workspace, then probe through local SOCKS.

    The caller must provide an explicit HTTPS `KAVEH_PROBE_URL`. No config is
    treated as qualified unless the request succeeds through the temporary
    local SOCKS listener.
    """

    def __init__(self, settings: RuntimeSettings, builder: XrayConfigBuilder | None = None) -> None:
        self.settings = settings
        self.builder = builder or XrayConfigBuilder()

    def run(self, config: CanonicalConfig) -> ProbeResult:
        identity = config.identity_hash or "unknown"
        try:
            binary, probe_urls = self.settings.require_xray_runtime()
        except SettingsError:
            return ProbeResult.failed(identity, ProbeStage.END_TO_END, "XRAY_RUNTIME_NOT_CONFIGURED", self.settings.vantage_id)
        if not binary.is_file() or not binary.exists():
            return ProbeResult.failed(identity, ProbeStage.END_TO_END, "XRAY_BINARY_NOT_FOUND", self.settings.vantage_id)
        try:
            socks_port = _reserve_local_port()
            runtime_config = self.builder.build(config, socks_port)
        except XrayBuildError:
            return ProbeResult.failed(identity, ProbeStage.RUNTIME_BUILD, "XRAY_CONFIG_BUILD_FAILED", self.settings.vantage_id)

        self.settings.xray_work_root.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="probe-", dir=self.settings.xray_work_root) as workspace:
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
                    return ProbeResult.failed(identity, ProbeStage.RUNTIME_BUILD, "XRAY_STARTUP_FAILED", self.settings.vantage_id)
                probe_statuses = []
                for probe_url in probe_urls:
                    try:
                        status = _probe_via_socks(
                            probe_url, socks_port, self.settings.xray_probe_timeout_seconds
                        )
                        probe_statuses.append(status)
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
                    "ALL_E2E_PROBES_FAILED" if not probe_statuses else "PROBE_STATUS_INVALID",
                    self.settings.vantage_id,
                )
            except (OSError, httpx.HTTPError, TimeoutError):
                return ProbeResult.failed(identity, ProbeStage.END_TO_END, "E2E_PROBE_FAILED", self.settings.vantage_id)
            finally:
                _terminate(process)


def _tls_settings(server_name: str | None) -> dict[str, Any]:
    settings: dict[str, Any] = {"allowInsecure": False}
    if server_name:
        settings["serverName"] = server_name
    return settings


def _reality_settings(config: CanonicalConfig) -> dict[str, Any]:
    extra = config.transport.extra
    public_key = extra.get("pbk")
    if not public_key or not config.transport.server_name:
        raise XrayBuildError("Reality requires server name and public key")
    settings: dict[str, Any] = {
        "serverName": config.transport.server_name,
        "publicKey": public_key,
        "fingerprint": extra.get("fp", "chrome"),
    }
    if extra.get("sid"):
        settings["shortId"] = extra["sid"]
    if extra.get("spx"):
        settings["spiderX"] = extra["spx"]
    return settings


def _int_or_default(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_listener(process: subprocess.Popen[bytes], port: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        with suppress(OSError):
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return True
        time.sleep(0.1)
    return False


def _probe_via_socks(url: str, port: int, timeout_seconds: float) -> int:
    proxy_url = f"socks5://127.0.0.1:{port}"
    with httpx.Client(
        proxy=proxy_url,
        timeout=httpx.Timeout(timeout_seconds),
        follow_redirects=False,
        headers={"User-Agent": "KavehProbe/0.1"},
    ) as client:
        response = client.head(url)
        return int(response.status_code)


def _terminate(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        with suppress(subprocess.TimeoutExpired):
            process.wait(timeout=2)
