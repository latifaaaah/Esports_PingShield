"""Bounded authorized TCP, DNS and verified HTTPS probes from this host only."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import http.client
import ipaddress
import logging
import math
import socket
import ssl
import statistics
import time

import dns.exception
import dns.resolver
import pandas as pd

from settings import Endpoint, Settings

LOG = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Sample:
    success: bool
    duration_ms: float | None = None
    error: str | None = None
    tcp_success: bool | None = None
    http_status: int | None = None
    resolver: str | None = None
    address: str | None = None
    timestamp: str = field(default_factory=utc_now)


def resolve(host: str, timeout: float, resolver_ip: str | None = None) -> tuple[str, str | None]:
    """Resolve IPv4 then IPv6 within one overall deadline; IP literals bypass DNS."""
    try:
        return str(ipaddress.ip_address(host)), None
    except ValueError:
        pass
    resolver = dns.resolver.Resolver()
    if resolver_ip:
        resolver.nameservers = [resolver_ip]
    resolver.timeout = timeout
    deadline = time.monotonic() + timeout
    for kind in ("A", "AAAA"):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise dns.exception.Timeout()
        try:
            answer = resolver.resolve(host, kind, lifetime=remaining, search=False)
            return str(answer[0]), str(answer.nameserver)
        except dns.resolver.NoAnswer:
            continue
    raise dns.resolver.NoAnswer()


def connect_ip(address: str, port: int, timeout: float) -> socket.socket:
    """Avoid a second implicit/unbounded hostname lookup in socket.create_connection."""
    family = socket.AF_INET6 if ipaddress.ip_address(address).version == 6 else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((address, port))
        return sock
    except BaseException:
        sock.close()
        raise


def error_category(exc: Exception) -> str:
    if isinstance(exc, (TimeoutError, dns.exception.Timeout)):
        return "timeout"
    if isinstance(exc, ConnectionRefusedError):
        return "refused"
    if isinstance(exc, dns.resolver.NXDOMAIN):
        return "nxdomain"
    if isinstance(exc, dns.resolver.NoNameservers):
        return "dns_resolver_error"
    if isinstance(exc, dns.resolver.NoAnswer):
        return "dns_no_answer"
    if isinstance(exc, ssl.SSLCertVerificationError):
        return "tls_verification"
    if isinstance(exc, ssl.SSLError):
        return "tls_error"
    if isinstance(exc, PermissionError):
        return "permission"
    if isinstance(exc, http.client.HTTPException):
        return "http_protocol"
    if isinstance(exc, OSError):
        return "connectivity"
    return "collector_error"


def probe(endpoint: Endpoint, timeout: float) -> Sample:
    """DNS time includes DNS query; TCP excludes DNS; HTTPS excludes DNS, includes TLS/headers.

    HTTPS sends HEAD, reads headers only, verifies hostname/certificate, and never follows
    redirects. A 3xx is recorded as an unvalidated redirect rather than final health.
    """
    tcp_success = None
    try:
        if endpoint.method == "dns":
            start = time.perf_counter()
            address, resolver = resolve(endpoint.host, timeout, endpoint.resolver)
            return Sample(True, (time.perf_counter() - start) * 1000, resolver=resolver, address=address)
        address, resolver = resolve(endpoint.host, timeout)
        start = time.perf_counter()
        if endpoint.method == "tcp":
            with connect_ip(address, endpoint.port, timeout):
                pass
            return Sample(
                True,
                (time.perf_counter() - start) * 1000,
                tcp_success=True,
                resolver=resolver,
                address=address,
            )
        connection = http.client.HTTPSConnection(
            endpoint.host, endpoint.port, timeout=timeout, context=ssl.create_default_context()
        )
        try:
            sock = connect_ip(address, endpoint.port, timeout)
            tcp_success = True
            # Ensure certificate/TLS failures cannot leak the raw socket.
            try:
                connection.sock = connection._context.wrap_socket(sock, server_hostname=endpoint.host)
            except BaseException:
                sock.close()
                raise
            connection.request(
                "HEAD",
                endpoint.path,
                headers={"User-Agent": "PingShield/3 local-monitor", "Connection": "close"},
            )
            response = connection.getresponse()
            code = response.status
            if 200 <= code < 300:
                return Sample(
                    True,
                    (time.perf_counter() - start) * 1000,
                    tcp_success=True,
                    http_status=code,
                    resolver=resolver,
                    address=address,
                )
            return Sample(
                False,
                error="http_redirect" if 300 <= code < 400 else "http_error",
                tcp_success=True,
                http_status=code,
                resolver=resolver,
                address=address,
            )
        finally:
            connection.close()
    except Exception as exc:
        return Sample(False, error=error_category(exc), tcp_success=tcp_success)


def summarize(samples: list[Sample]) -> dict:
    values = [
        s.duration_ms
        for s in samples
        if s.success and s.duration_ms is not None and math.isfinite(s.duration_ms) and s.duration_ms >= 0
    ]
    errors: dict[str, int] = {}
    for sample in samples:
        if not sample.success:
            key = sample.error or "unknown"
            errors[key] = errors.get(key, 0) + 1
    count = len(samples)
    return {
        "latency_ms": round(statistics.mean(values), 1) if values else None,
        "median_ms": round(statistics.median(values), 1) if values else None,
        "min_ms": round(min(values), 1) if values else None,
        "max_ms": round(max(values), 1) if values else None,
        # Nearest-rank p95 is intentionally unavailable for a small window.
        "p95_ms": round(sorted(values)[math.ceil(0.95 * len(values)) - 1], 1) if len(values) >= 20 else None,
        "jitter_ms": round(statistics.mean(abs(b - a) for a, b in zip(values, values[1:])), 1)
        if len(values) > 1
        else None,
        "raw_samples": [asdict(s) for s in samples],
        "sample_count": count,
        "success_count": len(values),
        "failure_rate_pct": round(100 * (count - len(values)) / count, 1) if count else None,
        "errors": errors,
        "timeout_count": errors.get("timeout", 0),
        "tcp_success": any(s.tcp_success is True for s in samples),
        "http_status": next((s.http_status for s in reversed(samples) if s.http_status), None),
        "resolver": next((s.resolver for s in reversed(samples) if s.resolver), None),
        "address": next((s.address for s in reversed(samples) if s.address), None),
    }


def measure_target(target: Endpoint, samples: int = 3, timeout: float = 1.5, cancel=None) -> dict:
    if not 1 <= samples <= 5 or not 0.1 <= timeout <= 3:
        raise ValueError("Invalid sample count or timeout")
    outcomes = []
    for _ in range(samples):
        if cancel is not None and cancel.is_set():
            break
        outcomes.append(probe(target, timeout))
    return {
        **target.__dict__,
        **summarize(outcomes),
        "timestamp": utc_now(),
        "mode": "live",
        "packet_loss_pct": None,
        "measurement_type": {
            "tcp": "TCP connect",
            "dns": "DNS resolution",
            "https": "HTTPS HEAD (TLS + headers)",
        }[target.method],
    }


def collect_all(settings: Settings | None = None, cancel=None) -> pd.DataFrame:
    settings = settings or Settings()

    def safe(endpoint: Endpoint) -> dict:
        try:
            return measure_target(endpoint, settings.samples, settings.timeout, cancel)
        except Exception:
            LOG.exception("Collector failed", extra={"endpoint_id": endpoint.id})
            return {
                **endpoint.__dict__,
                **summarize([Sample(False, error="collector_error")]),
                "timestamp": utc_now(),
                "mode": "live",
                "packet_loss_pct": None,
                "measurement_type": endpoint.method,
            }

    if not settings.endpoints:
        return pd.DataFrame()
    with ThreadPoolExecutor(max_workers=min(4, len(settings.endpoints)), thread_name_prefix="probe") as pool:
        return pd.DataFrame(list(pool.map(safe, settings.endpoints)))
