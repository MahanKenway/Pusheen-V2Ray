"""Bounded HTTPS fetcher for reviewed source registry entries."""

from __future__ import annotations

import ipaddress
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
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise SourceFetchError(f"SOURCE_HTTP_{status}")
                content_type = response.headers.get_content_type()
                if content_type not in {"text/plain", "application/octet-stream", "text/html", "application/json"}:
                    raise SourceFetchError("SOURCE_CONTENT_TYPE_REJECTED")
                body = response.read(source.max_bytes + 1)
        except HTTPError as exc:
            raise SourceFetchError(f"SOURCE_HTTP_{exc.code}") from exc
        except URLError as exc:
            raise SourceFetchError("SOURCE_UNREACHABLE") from exc
        if len(body) > source.max_bytes:
            raise SourceFetchError("SOURCE_TOO_LARGE")
        try:
            return body.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SourceFetchError("SOURCE_NON_UTF8") from exc

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
