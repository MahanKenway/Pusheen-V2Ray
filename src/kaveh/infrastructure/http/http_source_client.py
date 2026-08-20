"""Bounded HTTPS fetcher for reviewed source registry entries."""

from __future__ import annotations

import ipaddress
from queue import Empty, Queue
from threading import Thread
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from kaveh.domain.models import Source


class SourceFetchError(RuntimeError):
    """Safe error for source fetch failures; raw response bodies are not retained."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class BoundedHttpsSourceClient:
    """Fetch reviewed HTTPS sources with conservative resource limits."""

    def __init__(self, timeout_seconds: float = 15.0, user_agent: str = "KavehFeed/0.1") -> None:
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self._opener = build_opener(_NoRedirect())

    def fetch(self, source: Source) -> str:
        parsed = urlsplit(source.url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise SourceFetchError("SOURCE_URL_NOT_HTTPS")
        self._reject_direct_private_host(parsed.hostname)
        request = Request(source.url, headers={"User-Agent": self.user_agent})
        body = self._fetch_with_deadline(request, source.max_bytes)
        if len(body) > source.max_bytes:
            raise SourceFetchError("SOURCE_TOO_LARGE")
        try:
            return body.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SourceFetchError("SOURCE_NON_UTF8") from exc

    def _fetch_with_deadline(self, request: Request, max_bytes: int) -> bytes:
        """Bound the complete fetch, including system DNS resolution.

        ``urllib``'s socket timeout does not reliably bound a stalled system
        resolver. The daemon worker means a bad source can never hold the
        scheduled publisher past its budget. A timed-out source is rejected and
        contributes no configurations to the candidate pool.
        """

        result_queue: Queue[tuple[str, object]] = Queue(maxsize=1)

        def fetch() -> None:
            try:
                with self._opener.open(request, timeout=self.timeout_seconds) as response:
                    status = getattr(response, "status", 200)
                    if status != 200:
                        raise SourceFetchError(f"SOURCE_HTTP_{status}")
                    content_type = response.headers.get_content_type()
                    if content_type not in {"text/plain", "application/octet-stream", "text/html", "application/json"}:
                        raise SourceFetchError("SOURCE_CONTENT_TYPE_REJECTED")
                    body = response.read(max_bytes + 1)
            except HTTPError as exc:
                result_queue.put(("error", SourceFetchError(f"SOURCE_HTTP_{exc.code}")))
                return
            except URLError:
                result_queue.put(("error", SourceFetchError("SOURCE_UNREACHABLE")))
                return
            except SourceFetchError as exc:
                result_queue.put(("error", exc))
                return
            result_queue.put(("body", body))

        worker = Thread(target=fetch, name="kaveh-source-fetch", daemon=True)
        worker.start()
        try:
            outcome, value = result_queue.get(timeout=self.timeout_seconds)
        except Empty as exc:
            raise SourceFetchError("SOURCE_FETCH_TIMEOUT") from exc
        if outcome == "error":
            raise value  # type: ignore[misc]
        return value  # type: ignore[return-value]

    @staticmethod
    def _reject_direct_private_host(host: str) -> None:
        """Reject literal private/loopback addresses in a registry URL.

        DNS rebinding controls require deployment-level egress restrictions too;
        this guard is intentionally one layer, not a complete SSRF defense.
        """

        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return
        if address.is_private or address.is_loopback or address.is_link_local:
            raise SourceFetchError("SOURCE_PRIVATE_ADDRESS_REJECTED")
