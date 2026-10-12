"""Real Streamlit script/widget runs; live collection replaced with deterministic fixtures."""

from pathlib import Path
import sys
import time

import pandas as pd
from streamlit.testing.v1 import AppTest

from monitor import Monitor
from reporting import csv_export
from test_diagnosis import frame

ROOT = Path(__file__).resolve().parents[1]


def test_ui_simulation_playbooks_and_empty_zones(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # Test a copy to isolate app-relative SQLite from delivered source.
    import shutil

    root = tmp_path / "app"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("__pycache__", "data"))
    sys.path.insert(0, str(root))
    try:
        app = AppTest.from_file(str(root / "app.py"), default_timeout=10).run()
        assert not app.exception
        assert any("SIMULATION MODE" in m.value for m in app.markdown)
        assert len(app.dataframe) == 1
        assert "latency_ms" in app.dataframe[0].value.columns
        next(w for w in app.selectbox if w.label == "Select Disaster Scenario").set_value(
            "Scenario B: Stage Right Switch Failure"
        ).run()
        assert not app.exception
        assert any("Rule Based" in h.value for h in app.subheader)
        next(w for w in app.multiselect if w.label == "Filter Arena Zones").set_value([]).run()
        assert not app.exception
        assert any("UNKNOWN" in h.value for h in app.subheader)
        app.radio[0].set_value("Live (local only)").run()
        assert not app.exception
        assert any("No saved live" in i.value for i in app.info)
    finally:
        sys.path.pop(0)


def test_ui_live_refresh_and_two_sessions(monkeypatch, tmp_path):
    import streamlit as st

    st.cache_resource.clear()

    # Patch global collector default before the cached resource is constructed.
    class FixtureMonitor(Monitor):
        def __init__(self, store, settings):
            super().__init__(store, settings, lambda *a: (frame(), {}))

    monkeypatch.setattr("monitor.Monitor", FixtureMonitor)
    # Each script executes imports again and receives patched class.
    import shutil

    root = tmp_path / "app"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("__pycache__", "data"))
    first = AppTest.from_file(str(root / "app.py"), default_timeout=10).run()
    first.radio[0].set_value("Live (local only)").run()
    assert not first.exception
    refresh = next(b for b in first.button if b.label == "Refresh measurements")
    refresh.click().run()
    end = time.monotonic() + 3
    while time.monotonic() < end:
        first.run()
        if any("UTC" in c.value for c in first.caption):
            break
        time.sleep(0.05)
    assert not first.exception
    assert any("UTC" in c.value for c in first.caption)
    second = AppTest.from_file(str(root / "app.py"), default_timeout=10).run()
    second.radio[0].set_value("Live (local only)").run()
    assert not second.exception
    assert any("Last completed" in c.value for c in second.caption)


def test_csv_injection_protection():
    text = csv_export(pd.DataFrame({"zone": ['=IMPORTXML("x")', " @SUM(A1)", "normal"]}))
    assert "'=IMPORTXML" in text and "' @SUM" in text
