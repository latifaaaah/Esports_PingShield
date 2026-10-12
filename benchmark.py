"""Deterministic processing/storage benchmark; no live network claims."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import time
import tracemalloc

from engine import process_scenario
from config import DISASTER_SCENARIOS
from settings import Settings
from storage import Store


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        store = Store(Path(folder) / "benchmark.sqlite")
        tracemalloc.start()
        start = time.perf_counter()
        for n in range(100):
            df = process_scenario(
                DISASTER_SCENARIOS["NORMAL"], ["Stage Left", "Stage Right", "Production Booth", "Server Rack"]
            )
            # Deterministic fixture benchmarking must not be confused with measurements.
            df["mode"] = "live"
            df["timestamp"] = (datetime.now(timezone.utc) + timedelta(seconds=n)).isoformat()
            store.save_batch(df, Settings(), {})
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        print(
            json.dumps(
                {
                    "kind": "synthetic processing/storage only",
                    "batches": 100,
                    "endpoint_rows": 800,
                    "elapsed_seconds": round(elapsed, 3),
                    "ms_per_batch": round(elapsed * 10, 2),
                    "python_peak_memory_mib": round(peak / 1024 / 1024, 2),
                    "database_bytes": store.path.stat().st_size,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
