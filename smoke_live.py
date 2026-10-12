"""Opt-in live smoke test. Uses only the operator-owned allowlist; no scanning."""

import argparse
from pathlib import Path

from settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live", action="store_true", help="Explicitly enable real checks to configured targets"
    )
    args = parser.parse_args()
    if not args.live:
        parser.error("Use --live only on a network you are authorized to test")
    settings = load_settings(Path(__file__).with_name("settings.json"))
    # Use the same hard-deadline worker architecture as the dashboard.
    from monitor import bounded_collect
    import threading

    frame, network = bounded_collect(settings, threading.Event())
    print(frame.to_json(orient="records", indent=2))
    print("Route discovery:", network)
    print("This verifies checks only; repeat disconnect/reconnect validation on your own machine.")


if __name__ == "__main__":
    main()
