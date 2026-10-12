"""Validated operator-owned allowlist and monitoring policies."""

from dataclasses import asdict, dataclass, field
import ipaddress
import json
import math
from pathlib import Path
import re


@dataclass(frozen=True)
class Endpoint:
    id: str
    host: str
    method: str = "tcp"
    port: int = 443
    zone: str = "External"
    provider: str = "custom"
    scope: str = "external"
    warn_ms: float = 150
    crit_ms: float = 300
    recover_ms: float = 120
    jitter_warn_ms: float = 50
    path: str = "/"
    resolver: str | None = None
    expected_service: bool = True

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.id):
            raise ValueError("Endpoint ID must contain 1–64 letters, digits, underscores or hyphens")
        validate_host(self.host)
        if self.method not in {"tcp", "dns", "https"}:
            raise ValueError("Supported methods: tcp, dns, https")
        if self.method == "dns":
            try:
                ipaddress.ip_address(self.host)
            except ValueError:
                pass
            else:
                raise ValueError("DNS checks require a query name, not an IP literal")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise ValueError("Port must be an integer in 1–65535")
        if self.scope not in {"local", "external"}:
            raise ValueError("Scope must be local or external")
        for value in (self.warn_ms, self.crit_ms, self.recover_ms, self.jitter_warn_ms):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError("Thresholds must be positive finite numbers")
        if not self.recover_ms <= self.warn_ms < self.crit_ms:
            raise ValueError("Require recovery <= warning < critical")
        if not self.path.startswith("/") or len(self.path) > 512 or any(ord(c) < 32 for c in self.path):
            raise ValueError("HTTPS path must be an absolute safe path")
        if self.resolver:
            ipaddress.ip_address(self.resolver)
        if not isinstance(self.expected_service, bool):
            raise ValueError("expected_service must be boolean")
        if not self.zone or len(self.zone) > 80 or not self.provider or len(self.provider) > 80:
            raise ValueError("Zone and provider must be nonempty and <=80 characters")


def validate_host(host: str) -> None:
    if not isinstance(host, str) or not host or len(host) > 253:
        raise ValueError("Invalid host")
    try:
        ipaddress.ip_address(host)
        return
    except ValueError:
        pass
    if not all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", s) for s in host.rstrip(".").split(".")
    ):
        raise ValueError("Host must be an IP or DNS name, not a URL, range or shell command")


def default_endpoints() -> tuple[Endpoint, ...]:
    return (
        Endpoint("GOOGLE-DNS", "8.8.8.8", port=53, provider="google", zone="IP Connectivity"),
        Endpoint("CLOUDFLARE-DNS", "1.1.1.1", port=53, provider="cloudflare", zone="IP Connectivity"),
        Endpoint(
            "SYSTEM-DNS",
            "example.com",
            method="dns",
            zone="DNS",
            provider="system",
            warn_ms=250,
            crit_ms=1000,
            recover_ms=200,
        ),
        Endpoint(
            "GOOGLE-WEB",
            "www.google.com",
            method="https",
            provider="google",
            zone="Web Services",
            warn_ms=500,
            crit_ms=1500,
            recover_ms=500,
        ),
        Endpoint(
            "CLOUDFLARE-WEB",
            "www.cloudflare.com",
            method="https",
            provider="cloudflare",
            zone="Web Services",
            warn_ms=500,
            crit_ms=1500,
            recover_ms=500,
        ),
    )


@dataclass(frozen=True)
class Settings:
    endpoints: tuple[Endpoint, ...] = field(default_factory=default_endpoints)
    samples: int = 3
    timeout: float = 1.5
    interval: float = 30
    failure_windows: int = 2
    recovery_windows: int = 2
    stale_seconds: float = 120
    retention_days: int = 30
    max_batches: int = 10000

    def __post_init__(self) -> None:
        if len(self.endpoints) > 20 or len({e.id for e in self.endpoints}) != len(self.endpoints):
            raise ValueError("Allowlist requires unique IDs and at most 20 endpoints")
        for name, lo, hi in [
            ("samples", 1, 5),
            ("failure_windows", 1, 10),
            ("recovery_windows", 1, 10),
            ("retention_days", 1, 365),
            ("max_batches", 10, 100000),
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
                raise ValueError(f"{name} must be an integer from {lo} to {hi}")
        for name, lo, hi in [("timeout", 0.1, 3), ("interval", 10, 3600), ("stale_seconds", 10, 7200)]:
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not lo <= value <= hi
            ):
                raise ValueError(f"{name} must be within {lo}–{hi}")
        if self.stale_seconds < self.interval:
            raise ValueError("stale_seconds must cover at least one interval")


def load_settings(path: str | Path = "settings.json") -> Settings:
    path = Path(path)
    if not path.exists():
        return Settings()
    if path.stat().st_size > 65536:
        raise ValueError("Configuration file exceeds 64 KiB")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object")
    if "endpoints" in data:
        data["endpoints"] = tuple(Endpoint(**e) for e in data["endpoints"])
    return Settings(**data)


def settings_dict(settings: Settings) -> dict:
    return asdict(settings)
