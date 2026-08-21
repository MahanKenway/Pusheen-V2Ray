from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "monitor_gateway_delivery.py"
_SPEC = importlib.util.spec_from_file_location("gateway_delivery_monitor", _SCRIPT)
assert _SPEC and _SPEC.loader
monitor = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(monitor)


class GatewayDeliveryMonitorTests(unittest.TestCase):
    def test_public_result_discards_raw_response_content(self) -> None:
        summary = monitor._public_result(
            {
                "probe": {"country": "IR", "city": "Tehran", "network": "not-public"},
                "result": {
                    "status": "finished",
                    "statusCode": 200,
                    "timings": {"total": 123},
                    "rawBody": "credential-like-value",
                    "rawHeaders": "authorization: secret",
                    "resolvedAddress": "203.0.113.9",
                },
            }
        )

        self.assertEqual(
            {
                "country": "IR",
                "status": "finished",
                "http_status": 200,
                "total_ms": 123,
                "failure_source": None,
            },
            summary,
        )

    def test_iran_is_not_measured_without_available_probe(self) -> None:
        self.assertEqual("not_measured", monitor._iran_delivery_state([]))
        self.assertEqual(
            "reachable_from_sampled_probe",
            monitor._iran_delivery_state([{"status": "finished", "http_status": 200}]),
        )
        self.assertEqual(
            "failed_from_sampled_probe",
            monitor._iran_delivery_state([{"status": "finished", "http_status": 503}]),
        )


if __name__ == "__main__":
    unittest.main()
