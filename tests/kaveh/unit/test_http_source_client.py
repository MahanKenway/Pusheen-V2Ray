from __future__ import annotations

import time
import unittest

from kaveh.domain.models import Source
from kaveh.infrastructure.http.http_source_client import BoundedHttpsSourceClient, SourceFetchError


class _StalledOpener:
    def open(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        time.sleep(0.2)
        raise AssertionError("unreachable")


class BoundedHttpsSourceClientTests(unittest.TestCase):
    def test_stalled_fetch_returns_explicit_timeout_within_deadline(self) -> None:
        client = BoundedHttpsSourceClient(timeout_seconds=0.02)
        client._opener = _StalledOpener()  # type: ignore[assignment]
        source = Source("slow-source", "https://example.com/sub")

        started = time.perf_counter()
        with self.assertRaisesRegex(SourceFetchError, "SOURCE_FETCH_TIMEOUT"):
            client.fetch(source)

        self.assertLess(time.perf_counter() - started, 0.1)


if __name__ == "__main__":
    unittest.main()
