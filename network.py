"""Read-only default-route discovery. Never guesses a gateway or scans it."""

from dataclasses import asdict, dataclass
import ipaddress
import json
import platform
import subprocess


@dataclass(frozen=True)
class NetworkInfo:
    gateway: str | None = None
    interface: str | None = None
    method: str = "unavailable"
    error: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def discover_network() -> NetworkInfo:
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["/sbin/route", "-n", "get", "default"], capture_output=True, text=True, timeout=2, check=True
            )
            fields = dict(line.strip().split(":", 1) for line in result.stdout.splitlines() if ":" in line)
            gateway = fields.get("gateway", "").strip()
            interface = fields.get("interface", "").strip()
            method = "macOS route -n get default (IPv4)"
        elif system == "Linux":
            result = subprocess.run(
                ["ip", "-j", "route", "show", "default"],
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            )
            routes = json.loads(result.stdout)
            route = min(routes, key=lambda r: int(r.get("metric", 0))) if routes else {}
            gateway, interface = route.get("gateway"), route.get("dev")
            method = "Linux ip route (main IPv4 table)"
        elif system == "Windows":
            command = (
                "Get-NetRoute -DestinationPrefix 0.0.0.0/0 | "
                "Sort-Object RouteMetric | Select-Object -First 1 NextHop,InterfaceAlias | ConvertTo-Json -Compress"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
            )
            route = json.loads(result.stdout) if result.stdout.strip() else {}
            gateway, interface = route.get("NextHop"), route.get("InterfaceAlias")
            method = "Windows Get-NetRoute (route metric; not full interface preference)"
        else:
            return NetworkInfo(error=f"Unsupported route discovery: {system}")
        if not gateway:
            return NetworkInfo(interface=interface, method=method, error="No default gateway detected")
        ipaddress.ip_address(gateway)
        return NetworkInfo(gateway, interface, method)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return NetworkInfo(error=f"Route discovery unavailable: {type(exc).__name__}")
