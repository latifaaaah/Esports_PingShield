"""Spreadsheet-safe CSV exports of authorized measurement metadata."""

import pandas as pd


def csv_export(df: pd.DataFrame) -> str:
    result = df.copy()

    def safe(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
            return "'" + value
        return value

    for column in result.columns:
        if result[column].dtype == "object":
            result[column] = result[column].map(safe)
    return result.to_csv(index=False)


def performance_summary(history: pd.DataFrame) -> pd.DataFrame:
    """Statistics over stored individual successful samples; do not average window means."""
    import math
    import statistics

    rows = []
    if history.empty or "raw_samples" not in history:
        return pd.DataFrame()
    for (endpoint, method), group in history.groupby(["id", "method"]):
        values = [
            s["duration_ms"]
            for samples in group["raw_samples"]
            if isinstance(samples, list)
            for s in samples
            if s.get("success")
            and isinstance(s.get("duration_ms"), (int, float))
            and math.isfinite(s["duration_ms"])
            and s["duration_ms"] >= 0
        ]
        if values:
            rows.append(
                {
                    "endpoint": endpoint,
                    "method": method,
                    "successful_samples": len(values),
                    "mean_ms": round(statistics.mean(values), 1),
                    "median_ms": round(statistics.median(values), 1),
                    "min_ms": round(min(values), 1),
                    "max_ms": round(max(values), 1),
                    "p95_ms": round(sorted(values)[math.ceil(0.95 * len(values)) - 1], 1)
                    if len(values) >= 20
                    else None,
                }
            )
    return pd.DataFrame(rows)
