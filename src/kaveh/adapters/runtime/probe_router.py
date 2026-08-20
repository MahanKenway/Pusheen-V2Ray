"""Protocol-aware dispatch for end-to-end validation runtimes."""

from __future__ import annotations

from kaveh.adapters.runtime.singbox_adapter import SingBoxEndToEndProbe
from kaveh.adapters.runtime.xray_adapter import XrayEndToEndProbe
from kaveh.config.settings import RuntimeSettings
from kaveh.domain.models import CanonicalConfig, ProbeResult, Protocol


class ProtocolRuntimeProbe:
    """Route TUIC to sing-box and Xray-supported protocols to Xray."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self.xray = XrayEndToEndProbe(settings)
        self.singbox = SingBoxEndToEndProbe(settings)

    def run(self, config: CanonicalConfig) -> ProbeResult:
        if config.protocol in {Protocol.TUIC, Protocol.NAIVE}:
            return self.singbox.run(config)
        return self.xray.run(config)
