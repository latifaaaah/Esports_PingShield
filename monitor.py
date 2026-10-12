"""One process-shared coordinator; DB lease prevents overlapping worker batches."""

import atexit
import json
import logging
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import pandas as pd

from settings import Settings, settings_dict
from storage import Store

LOG = logging.getLogger(__name__)
BATCH_DEADLINE = 90


def bounded_collect(settings: Settings, cancel: threading.Event) -> tuple[pd.DataFrame, dict]:
    """Hard end-to-end deadline includes DNS, header trickle and worker shutdown."""
    worker = Path(__file__).with_name("worker.py")
    process = subprocess.Popen(
        [sys.executable, str(worker)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    start = time.monotonic()
    payload = json.dumps(settings_dict(settings))
    try:
        while True:
            if cancel.is_set():
                raise InterruptedError("Collection cancelled")
            if time.monotonic() - start >= BATCH_DEADLINE:
                raise TimeoutError("Collection exceeded the 90-second batch deadline")
            try:
                output, errors = process.communicate(payload, timeout=0.25)
                break
            except subprocess.TimeoutExpired:
                payload = None
        if process.returncode:
            LOG.error("Collection worker failed", extra={"returncode": process.returncode})
            raise RuntimeError("Collection worker failed; inspect local logs/configuration")
        result = json.loads(output)
        return pd.DataFrame(result["records"]), result["network"]
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()


class Monitor:
    """Shared across browser sessions via st.cache_resource; no thread uses st.*.

    Stop/Start affect this server coordinator, not every process on the host. A CLI
    collector may also run; the shared DB lease prevents simultaneous batches.
    """

    def __init__(self, store: Store, settings: Settings, collect=bounded_collect):
        self.store, self.settings, self.collect = store, settings, collect
        self.owner = str(uuid.uuid4())
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.cancel = threading.Event()
        self.shutdown = threading.Event()
        self.enabled = False
        self.requested = False
        self.busy = False
        self.error: str | None = None
        self.last_completed: str | None = None
        self.next_due = 0.0
        self.thread = threading.Thread(target=self._loop, name="pingshield-coordinator", daemon=True)
        self.thread.start()
        atexit.register(self.close)

    def start(self) -> None:
        with self.lock:
            self.enabled = True
            self.next_due = 0
            if not self.busy:
                self.cancel.clear()
        self.wake.set()

    def stop(self) -> None:
        with self.lock:
            self.enabled = False
            self.requested = False
            self.cancel.set()
        self.wake.set()

    def request(self) -> bool:
        with self.lock:
            if self.busy or self.requested:
                return False
            self.cancel.clear()
            self.requested = True
        self.wake.set()
        return True

    def status(self) -> dict:
        with self.lock:
            return {
                "enabled": self.enabled,
                "busy": self.busy,
                "requested": self.requested,
                "error": self.error,
                "last_completed": self.last_completed,
                "interval": self.settings.interval,
            }

    def configure_interval(self, interval: float) -> None:
        from dataclasses import replace

        with self.lock:
            self.settings = replace(
                self.settings, interval=interval, stale_seconds=max(self.settings.stale_seconds, interval * 2)
            )
            self.next_due = time.monotonic() + interval
        self.wake.set()

    def _loop(self) -> None:
        while not self.shutdown.is_set():
            with self.lock:
                due = self.requested or (self.enabled and time.monotonic() >= self.next_due)
                if due:
                    self.requested = False
                    self.busy = True
                    self.cancel.clear()
                    settings = self.settings
            if due:
                leased = False
                try:
                    leased = self.store.acquire(self.owner)
                    if not leased:
                        raise RuntimeError("Another collector owns the current batch; retry later")
                    frame, network = self.collect(settings, self.cancel)
                    if not self.cancel.is_set():
                        saved = self.store.save_batch(frame, settings, network)
                        with self.lock:
                            self.error = None
                            self.last_completed = saved["timestamp"].max() if not saved.empty else None
                except InterruptedError:
                    with self.lock:
                        self.error = "Collection cancelled; last completed window retained"
                except Exception as exc:
                    LOG.exception("Monitoring batch failed")
                    with self.lock:
                        self.error = (
                            str(exc)
                            if isinstance(exc, (TimeoutError, RuntimeError))
                            else f"Monitoring/storage error: {type(exc).__name__}"
                        )
                finally:
                    if leased:
                        try:
                            self.store.release(self.owner)
                        except Exception:
                            LOG.exception("Lease release failed; expiry will reclaim it")
                    with self.lock:
                        self.busy = False
                        self.next_due = time.monotonic() + settings.interval
            self.wake.wait(0.25)
            self.wake.clear()

    def close(self) -> None:
        self.stop()
        self.shutdown.set()
        self.wake.set()
        if self.thread is not threading.current_thread():
            self.thread.join(timeout=3)
