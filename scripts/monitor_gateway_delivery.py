#!/usr/bin/env python3
"""Measure public Gateway delivery from sampled Globalping probes.

The monitor intentionally observes only public Pusheen delivery artifacts.  It
never connects to proxy endpoints, and it writes only country-level HTTP result
summaries, timing, and SLO state.  Raw measurement bodies, headers, resolved
addresses, configuration URIs, and credentials are discarded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_ROOT = "https://api.globalping.io/v1/measurements"
DEFAULT_GATEWAY = "https://pusheen-feed-gateway.mahankenway.workers.dev"
TARGETS = (("health", "/health"), ("outage_feed", "/outage.txt"))
LOCATIONS = ("IR", "DE", "SG", "US")
PUBLICATION_STALE_SECONDS = 35 * 60
KV_MIRROR_STALE_SECONDS = 45 * 60


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pusheen public delivery monitor")
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--max-wait-seconds", type=float, default=45.0)
    args = parser.parse_args(argv)
    if args.poll_seconds <= 0 or args.max_wait_seconds <= 0:
        raise ValueError("poll and wait values must be positive")

    root = args.root.resolve()
    gateway = args.gateway.rstrip("/")
    previous = _read_json(root / "monitoring" / "delivery-status.v1.json") or {}
    measurements = [
        _measure_target(gateway, label, path, args.poll_seconds, args.max_wait_seconds)
        for label, path in TARGETS
    ]
    now = datetime.now(UTC)
    delivery = _build_delivery_report(gateway, now, measurements, previous)
    slo = _build_slo_report(root, gateway, now, delivery)
    _write_json(root / "monitoring" / "delivery-status.v1.json", delivery)
    _write_json(root / "monitoring" / "slo-status.v1.json", slo)
    _update_public_status(root / "status.json", delivery, slo)
    print(json.dumps({"delivery": delivery["summary"], "slo": slo["summary"]}, sort_keys=True))
    return 0


def _measure_target(
    gateway: str,
    label: str,
    path: str,
    poll_seconds: float,
    max_wait_seconds: float,
) -> dict[str, Any]:
    host = gateway.removeprefix("https://").removeprefix("http://").split("/", 1)[0]
    payload = {
        "type": "http",
        "target": host,
        "locations": [{"country": country, "limit": 1} for country in LOCATIONS],
        "measurementOptions": {
            "protocol": "HTTPS",
            "request": {"method": "GET", "path": path},
        },
        "timeout": min(30, int(max_wait_seconds)),
    }
    created = _request_json("POST", API_ROOT, payload)
    measurement_id = str(created.get("id") or "")
    if not measurement_id:
        raise RuntimeError("GLOBALPING_MEASUREMENT_ID_MISSING")
    deadline = time.monotonic() + max_wait_seconds
    document: dict[str, Any] = {}
    while time.monotonic() < deadline:
        document = _request_json("GET", f"{API_ROOT}/{measurement_id}")
        if document.get("status") != "in-progress":
            break
        time.sleep(poll_seconds)
    if document.get("status") == "in-progress":
        raise RuntimeError("GLOBALPING_MEASUREMENT_TIMEOUT")
    return {
        "target": label,
        "path": path,
        "measurement_id": measurement_id,
        "requested_locations": list(LOCATIONS),
        "results": [_public_result(item) for item in document.get("results", [])],
    }


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        method=method,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=35) as response:  # noqa: S310 - fixed HTTPS endpoints
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("GLOBALPING_API_UNAVAILABLE") from exc


def _public_result(item: dict[str, Any]) -> dict[str, Any]:
    probe = item.get("probe") or {}
    result = item.get("result") or {}
    timings = result.get("timings") or {}
    return {
        "country": probe.get("country"),
        "status": result.get("status"),
        "http_status": _optional_int(result.get("statusCode")),
        "total_ms": _optional_int(timings.get("total")),
        "failure_source": result.get("failureSource"),
    }


def _build_delivery_report(
    gateway: str,
    now: datetime,
    measurements: list[dict[str, Any]],
    previous: dict[str, Any],
) -> dict[str, Any]:
    all_results = [result for item in measurements for result in item["results"]]
    iran_results = [result for result in all_results if result.get("country") == "IR"]
    iran_delivery = _iran_delivery_state(iran_results)
    any_5xx = any((result.get("http_status") or 0) >= 500 for result in all_results)
    prior_streak = int((previous.get("summary") or {}).get("gateway_5xx_streak") or 0)
    streak = prior_streak + 1 if any_5xx else 0
    return {
        "schema_version": 1,
        "updated_at": now.isoformat(),
        "gateway": gateway,
        "scope": "public Gateway delivery only; proxy endpoints inside feeds are never measured",
        "measurements": measurements,
        "summary": {
            "iran_delivery": iran_delivery,
            "sampled_probe_count": len(all_results),
            "successful_http_200_count": sum(1 for result in all_results if result.get("http_status") == 200),
            "failed_probe_count": sum(1 for result in all_results if result.get("status") != "finished" or (result.get("http_status") or 0) >= 400),
            "gateway_5xx_streak": streak,
        },
    }


def _iran_delivery_state(results: list[dict[str, Any]]) -> str:
    if not results:
        return "not_measured"
    if all(result.get("status") == "finished" and result.get("http_status") == 200 for result in results):
        return "reachable_from_sampled_probe"
    return "failed_from_sampled_probe"


def _build_slo_report(root: Path, gateway: str, now: datetime, delivery: dict[str, Any]) -> dict[str, Any]:
    status = _read_json(root / "status.json") or {}
    pointer = _read_json(root / "releases" / "current-release.json") or {}
    checks: dict[str, dict[str, Any]] = {}
    alerts: list[dict[str, str]] = []

    publication_timestamp = pointer.get("updated_at") or status.get("updated_at")
    age_seconds = _age_seconds(publication_timestamp, now)
    freshness_ok = age_seconds is not None and age_seconds <= PUBLICATION_STALE_SECONDS
    checks["publication_freshness"] = {
        "status": "pass" if freshness_ok else "fail",
        "age_seconds": age_seconds,
        "threshold_seconds": PUBLICATION_STALE_SECONDS,
        "observed_at": publication_timestamp,
    }
    if not freshness_ok:
        alerts.append({"code": "PUBLICATION_STALE", "severity": "warning", "message": "Publication is older than 35 minutes."})

    streak = int((delivery.get("summary") or {}).get("gateway_5xx_streak") or 0)
    gateway_ok = streak < 2
    checks["gateway_delivery"] = {
        "status": "pass" if gateway_ok else "fail",
        "consecutive_5xx_runs": streak,
        "threshold_runs": 2,
    }
    if not gateway_ok:
        alerts.append({"code": "GATEWAY_5XX_STREAK", "severity": "critical", "message": "Gateway returned 5xx from sampled probes in two consecutive runs."})

    mirror = _fetch_gateway_health(gateway).get("mirror") or {}
    mirror_age = _optional_int(mirror.get("critical_oldest_age_seconds"))
    mirror_ok = mirror_age is not None and mirror_age <= KV_MIRROR_STALE_SECONDS
    checks["kv_mirror_age"] = {
        "status": "pass" if mirror_ok else "warning",
        "age_seconds": mirror_age,
        "threshold_seconds": KV_MIRROR_STALE_SECONDS,
        "reason": None if mirror_age is not None else "not_observable",
    }
    if mirror_age is not None and not mirror_ok:
        alerts.append({"code": "KV_MIRROR_STALE", "severity": "warning", "message": "Critical KV mirror age is over 45 minutes."})

    strict_count = _optional_int(((status.get("feeds") or {}).get("strict") or {}).get("count"))
    manifest_ok = _manifest_hash_matches(root, pointer)
    strict_ok = strict_count is not None and strict_count > 0 and manifest_ok
    checks["strict_feed"] = {
        "status": "pass" if strict_ok else "fail",
        "count": strict_count,
        "manifest_hash_matches": manifest_ok,
    }
    if not strict_ok:
        alerts.append({"code": "STRICT_FEED_OR_MANIFEST", "severity": "critical", "message": "Strict feed is empty or current manifest integrity does not match."})

    sources = status.get("sources") or {}
    total_sources = _optional_int(sources.get("total")) or 0
    quarantined = _optional_int(sources.get("quarantined")) or 0
    source_ok = total_sources == 0 or quarantined * 2 <= total_sources
    checks["source_health"] = {
        "status": "pass" if source_ok else "warning",
        "total": total_sources,
        "quarantined": quarantined,
    }
    if not source_ok:
        alerts.append({"code": "SOURCE_QUARANTINE_MAJORITY", "severity": "warning", "message": "More than half of sources are quarantined."})

    return {
        "schema_version": 1,
        "updated_at": now.isoformat(),
        "scope": "public-safe delivery SLO; not a proxy endpoint availability claim",
        "checks": checks,
        "alerts": alerts,
        "summary": {
            "status": "healthy" if not alerts else "degraded",
            "alert_count": len(alerts),
        },
    }


def _fetch_gateway_health(gateway: str) -> dict[str, Any]:
    request = Request(f"{gateway}/health", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:  # noqa: S310 - configured HTTPS gateway
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return {}


def _manifest_hash_matches(root: Path, pointer: dict[str, Any]) -> bool:
    relative_path = pointer.get("manifest_path")
    expected_hash = pointer.get("manifest_sha256")
    if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
        return False
    manifest = root / relative_path
    if not manifest.is_file() or root not in manifest.resolve().parents:
        return False
    return hashlib.sha256(manifest.read_bytes()).hexdigest() == expected_hash


def _age_seconds(value: object, now: datetime) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if observed.tzinfo is None:
        return None
    return max(0, int((now - observed.astimezone(UTC)).total_seconds()))


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _update_public_status(path: Path, delivery: dict[str, Any], slo: dict[str, Any]) -> None:
    status = _read_json(path) or {}
    status["delivery_monitor"] = delivery["summary"]
    status["slo"] = slo["summary"]
    _write_json(path, status)


if __name__ == "__main__":
    raise SystemExit(main())
