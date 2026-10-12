"""Pure, timestamped state transitions; displayed current state is never history."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import pandas as pd

from settings import Settings


@dataclass
class EndpointState:
    status: str = "UNKNOWN"
    failures: int = 0
    healthy: int = 0
    timestamp: str | None = None
    recovery_required: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def transition(previous: EndpointState, row: dict, policy: Settings) -> EndpointState:
    """Two bad windows confirm severe alerts by default; two cool windows close them."""
    timestamp = row["timestamp"]
    if previous.timestamp and timestamp <= previous.timestamp:
        return previous
    raw = row["raw_status"]
    if raw == "UNKNOWN":
        return EndpointState("UNKNOWN", 0, 0, timestamp, previous.recovery_required)
    if raw in {"CRITICAL", "UNREACHABLE"}:
        count = previous.failures + 1
        confirmed = (
            previous.status in {"CRITICAL", "UNREACHABLE", "RECOVERING"} or count >= policy.failure_windows
        )
        return EndpointState(
            raw if confirmed else "WARNING", count, 0, timestamp, confirmed or previous.recovery_required
        )
    if raw == "WARNING":
        return EndpointState("WARNING", 0, 0, timestamp, previous.recovery_required)
    # Use an independent lower recovery threshold, with variation/failure criteria in raw state.
    needs_recovery = previous.recovery_required
    latency = pd.to_numeric(row.get("latency_ms"), errors="coerce")
    cool = pd.notna(latency) and latency <= row["recover_ms"]
    if needs_recovery:
        count = previous.healthy + 1 if cool else 0
        return EndpointState(
            "HEALTHY" if count >= policy.recovery_windows else "RECOVERING",
            0,
            count,
            timestamp,
            count < policy.recovery_windows,
        )
    return EndpointState("HEALTHY", 0, 0, timestamp)


def fresh_view(df: pd.DataFrame, stale_seconds: float, now: datetime | None = None) -> pd.DataFrame:
    result = df.copy()
    if not result.empty:
        now = now or datetime.now(timezone.utc)
        ages = (now - pd.to_datetime(result["timestamp"], utc=True, errors="coerce")).dt.total_seconds()
        stale = ages.isna() | (ages > stale_seconds) | (ages < -5)
        result.loc[stale, "status"] = "UNKNOWN"
        for column in ("latency_ms", "jitter_ms", "failure_rate_pct", "packet_loss_pct"):
            if column in result:
                result.loc[stale, column] = None
        result["freshness"] = ["STALE" if s else "CURRENT" for s in stale]
    return result
