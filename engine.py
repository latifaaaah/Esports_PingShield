"""Shared normalization and endpoint evaluation for live and simulated windows."""

import pandas as pd

from collector import collect_all, utc_now
from config import BASE_DEVICES, CRITICAL_MS, DISASTER_SCENARIOS, WARNING_MS, get_scenario_key
from settings import Settings

COLUMNS = [
    "id",
    "zone",
    "latency_ms",
    "jitter_ms",
    "failure_rate_pct",
    "packet_loss_pct",
    "warn_ms",
    "crit_ms",
    "recover_ms",
    "jitter_warn_ms",
    "sample_count",
    "success_count",
    "status",
    "raw_status",
    "timestamp",
    "measurement_type",
    "method",
    "scope",
    "provider",
    "errors",
    "mode",
]


def classify(row) -> str:
    count = row.get("sample_count", 0)
    if not count:
        return "UNKNOWN"
    errors = row.get("errors", {})
    if errors.get("config_error") or errors.get("collector_error"):
        return "UNKNOWN"
    if not row.get("success_count", 0):
        if not row.get("expected_service", True):
            return "UNKNOWN"
        if row.get("method") == "https" and row.get("tcp_success"):
            return "WARNING" if errors.get("http_redirect") else "CRITICAL"
        return "UNREACHABLE"
    value = row.get("latency_ms")
    if pd.isna(value):
        return "UNKNOWN"
    packet_loss = row.get("packet_loss_pct")
    if value > row["crit_ms"] or (pd.notna(packet_loss) and packet_loss >= 5):
        return "CRITICAL"
    variation = row.get("jitter_ms")
    if (
        value > row["warn_ms"]
        or row.get("failure_rate_pct", 0) > 0
        or (pd.notna(variation) and variation > row.get("jitter_warn_ms", 50))
        or (pd.notna(packet_loss) and packet_loss > 0)
    ):
        return "WARNING"
    return "HEALTHY"


def evaluate(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    df = df.copy()
    df["raw_status"] = df.apply(classify, axis=1)
    df["status"] = df["raw_status"]
    return df


def process_live(settings: Settings | None = None, cancel=None) -> pd.DataFrame:
    return evaluate(collect_all(settings, cancel))


def process_scenario(scenario_label: str, selected_zones: list[str], window: int = 0) -> pd.DataFrame:
    """Retain arena fixtures; simulate protocol checks with the same live schema/rules."""
    devices = [d.copy() for d in BASE_DEVICES if d["zone"] in selected_zones]
    if not devices:
        return pd.DataFrame(columns=COLUMNS)
    key = get_scenario_key(scenario_label)
    df = pd.DataFrame(devices)
    df["latency_ms"], df["jitter_ms"] = df["base_ping"], df["base_jitter"]
    df["packet_loss_pct"] = df["base_loss"]
    df["failure_rate_pct"] = 0.0
    df["warn_ms"], df["crit_ms"], df["recover_ms"] = WARNING_MS, CRITICAL_MS, WARNING_MS * 0.8
    df["jitter_warn_ms"] = 5.0
    df["sample_count"], df["success_count"] = 5, 5
    df["method"], df["measurement_type"], df["mode"] = (
        "icmp_simulated",
        "SIMULATED ICMP fixture",
        "simulation",
    )
    df["scope"] = ["local" if z.startswith("Stage") else "external" for z in df["zone"]]
    df["provider"] = df["id"]
    df["timestamp"] = utc_now()
    df["errors"] = [{} for _ in range(len(df))]
    df["tcp_success"] = True
    if key == "SERVER_DDOS":
        df.loc[df["id"] == "GAME-SERVER-PRIMARY", ["latency_ms", "jitter_ms", "packet_loss_pct"]] = [
            145,
            32,
            12.5,
        ]
    elif key == "STAGE_SWITCH_FAIL":
        df.loc[
            df["zone"] == "Stage Right", ["latency_ms", "jitter_ms", "packet_loss_pct", "success_count"]
        ] = [None, None, 100, 0]
    elif key == "STREAM_PACKET_LOSS":
        df.loc[df["id"] == "OBS-BROADCAST-01", ["latency_ms", "jitter_ms", "packet_loss_pct"]] = [
            48,
            18.5,
            4.2,
        ]
    elif key == "TOTAL_CONGESTION":
        df["latency_ms"] += 35
        df["packet_loss_pct"] += 2.5
    elif key == "HIGH_LATENCY":
        df["latency_ms"] += 40
    elif key == "JITTER":
        df["jitter_ms"] = 15.0
    elif key == "GATEWAY_FAILURE":
        mask = df["scope"] == "local"
        df.loc[mask, ["latency_ms", "jitter_ms", "success_count", "failure_rate_pct"]] = [None, None, 0, 100]
        for idx in df.index[mask]:
            df.at[idx, "errors"] = {"timeout": 5}
    elif key == "DNS_FAILURE":
        idx = df.index[-1]
        df.loc[idx, ["method", "measurement_type", "latency_ms", "success_count", "failure_rate_pct"]] = [
            "dns",
            "SIMULATED DNS resolution",
            None,
            0,
            100,
        ]
        df.at[idx, "errors"] = {"nxdomain": 5}
    elif key in {"WAN_OUTAGE", "COMPLETE_FAILURE", "INTERMITTENT", "RECOVERY", "PARTIAL_FAILURE"}:
        fail = (
            key not in {"INTERMITTENT", "RECOVERY"}
            or (key == "INTERMITTENT" and window % 2 == 0)
            or (key == "RECOVERY" and window == 0)
        )
        if fail:
            mask = df["scope"] == "external" if key != "COMPLETE_FAILURE" else pd.Series(True, index=df.index)
            if key == "PARTIAL_FAILURE":
                mask = df["id"] == df["id"].iloc[-1]
            df.loc[mask, ["latency_ms", "jitter_ms", "success_count", "failure_rate_pct"]] = [
                None,
                None,
                0,
                100,
            ]
            for idx in df.index[mask]:
                df.at[idx, "errors"] = {"timeout": 5}
    elif key == "HTTP_FAILURE":
        idx = df.index[-1]
        df.loc[idx, ["method", "measurement_type", "latency_ms", "success_count", "failure_rate_pct"]] = [
            "https",
            "SIMULATED HTTPS HEAD",
            None,
            0,
            100,
        ]
        df.at[idx, "errors"] = {"http_error": 5}
        df.at[idx, "http_status"] = 503
    return evaluate(df.drop(columns=["base_ping", "base_jitter", "base_loss"]))


DISASTER_SCENARIOS.update(
    {
        "HIGH_LATENCY": "High latency (connectivity retained)",
        "PARTIAL_FAILURE": "Partial service outage",
        "DNS_FAILURE": "DNS resolution failure",
        "WAN_OUTAGE": "External connectivity outage",
        "COMPLETE_FAILURE": "Complete check failure",
        "INTERMITTENT": "Intermittent failures (advance windows)",
        "RECOVERY": "Outage → recovery (advance windows)",
        "JITTER": "Latency variation degradation",
        "HTTP_FAILURE": "HTTPS application error",
        "GATEWAY_FAILURE": "Local service failure (external checks work)",
    }
)
