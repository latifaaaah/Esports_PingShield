"""Optional collector process independent of browser sessions. Ctrl-C stops safely."""

import logging
from pathlib import Path
import time

from monitor import Monitor
from settings import load_settings
from storage import Store


def main() -> None:
    root = Path(__file__).resolve().parent
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    monitor = Monitor(Store(root / "data/pingshield.sqlite"), load_settings(root / "settings.json"))
    monitor.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        monitor.close()


if __name__ == "__main__":
    main()
