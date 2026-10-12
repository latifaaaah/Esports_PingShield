"""Dark esports operations dashboard; collectors and storage do not call Streamlit."""

from dataclasses import asdict
from html import escape
import logging
from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st

from config import DISASTER_SCENARIOS, SCENARIO_PLAYBOOKS, get_scenario_key
from diagnosis import diagnose_live
from engine import COLUMNS, process_scenario
from monitor import Monitor
from reporting import csv_export, performance_summary
from settings import load_settings, settings_dict
from state import EndpointState, fresh_view, transition
from storage import Store
from ui import apply_custom_css, render_kpi_cards, render_latency_chart, render_topology_grid

ROOT = Path(__file__).resolve().parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
st.set_page_config(page_title="Esports-PingShield Operations Center", page_icon="🎮", layout="wide")
apply_custom_css()


@st.cache_resource
def resources():
    settings = load_settings(ROOT / "settings.json")
    store = Store(ROOT / "data/pingshield.sqlite")
    return settings, store, Monitor(store, settings)


try:
    settings, store, monitor = resources()
except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
    logging.exception("Initialization failed")
    st.error(
        f"Configuration/storage unavailable ({type(exc).__name__}). Review settings.json and folder permissions."
    )
    st.stop()

with st.sidebar:
    st.title("Monitoring Controls")
    mode = st.radio("Data Source", ["Simulation", "Live (local only)"])
    if mode == "Simulation":
        st.caption("Simulated fixtures only; no network traffic or live-history writes.")
        scenario = st.selectbox("Select Disaster Scenario", list(DISASTER_SCENARIOS.values()))
        selected_zones = st.multiselect(
            "Filter Arena Zones",
            ["Stage Left", "Stage Right", "Production Booth", "Server Rack"],
            default=["Stage Left", "Stage Right", "Production Booth", "Server Rack"],
        )
        if st.session_state.get("sim_scenario") != scenario:
            st.session_state.sim_scenario = scenario
            st.session_state.sim_window = 0
            st.session_state.sim_states = {}
        advance = st.button("Advance simulation window")
        if advance:
            st.session_state.sim_window += 1
    else:
        st.caption("Checks from this server only. Start/Stop controls are shared across browser sessions.")
        st.caption("Switching to simulation does not stop an already started live collector.")
        interval = st.number_input(
            "Interval after completed batch (seconds)", 10, 3600, int(monitor.status()["interval"]), step=10
        )
        if interval != monitor.status()["interval"]:
            monitor.configure_interval(interval)
        left, right = st.columns(2)
        if left.button("Start monitoring"):
            monitor.start()
        if right.button("Stop monitoring"):
            monitor.stop()
        if st.button("Refresh measurements"):
            monitor.request()
        st.caption("Live checks run only when requested or started. No aggressive scanning.")
    with st.expander("Configuration and method notes"):
        st.json(settings_dict(monitor.settings))
        st.caption(
            "Edit the operator-owned settings.json and restart to change the endpoint allowlist/policies."
        )
        st.caption(
            "TCP failure ≠ packet loss; a closed gateway port ≠ gateway failure. HTTPS uses verified HEAD, no redirect following."
        )


def render_dashboard(df: pd.DataFrame, network: dict, simulated: bool) -> None:
    if df.empty:
        df = pd.DataFrame(columns=COLUMNS)
    states = set(df["status"])
    overall = next(
        (s for s in ["UNREACHABLE", "CRITICAL", "UNKNOWN", "RECOVERING", "WARNING"] if s in states),
        "HEALTHY" if not df.empty else "UNKNOWN",
    )
    badge = "SIMULATION MODE" if simulated else "LIVE • THIS HOST"
    subtitle = (
        "Arena scenario fixtures" if simulated else "Authorized TCP, DNS and HTTPS checks from the server"
    )
    st.markdown(
        f'<div class="main-header"><div class="header-row"><div>'
        f'<h1 class="header-title">Esports-PingShield | Operations Center</h1>'
        f'<p class="header-subtitle">{escape(subtitle)}</p></div>'
        f'<div class="live-badge">{badge}</div></div></div>',
        unsafe_allow_html=True,
    )
    st.subheader(f"Network Overview • {overall}")
    st.caption(
        "Overall state covers configured checks; it does not locate a network fault or measure game quality."
    )
    if not df.empty:
        st.caption(f"Last completed evidence (UTC): {df['timestamp'].max()}")
        successes = df[df["success_count"] > 0]
        st.caption(
            "Last successful check (UTC): "
            + (
                (successes["timestamp"].max() if not successes.empty else "N/A in this batch")
                if simulated
                else (store.last_success_time() or "N/A")
            )
        )
    if not simulated:
        status = monitor.status()
        st.caption(
            f"Collection: {'RUNNING' if status['busy'] else 'IDLE'} • Periodic: {'ON' if status['enabled'] else 'OFF'}"
        )
        if status["error"]:
            st.warning(status["error"])
        with st.expander("Local route awareness"):
            st.json(network or {"status": "No completed live network discovery yet"})
            st.caption(
                "Discovery observes the selected IPv4 default route. Gateway address alone does not prove reachability; VPN/policy routing may differ."
            )
    severe = int(df["status"].isin(["CRITICAL", "UNREACHABLE"]).sum())
    render_kpi_cards(df, severe)
    left, right = st.columns([1, 1.3])
    with left:
        render_topology_grid(df)
    with right:
        render_latency_chart(df)
    st.subheader("Smart Network Diagnosis • Rule Based")
    history = store.history() if not simulated else None
    diagnosis = diagnose_live(df, network, history)
    st.markdown(f"**{diagnosis.title}**")
    st.write(diagnosis.explanation)
    st.caption(
        f"Evidence: {diagnosis.evidence_strength} • Additional checks required: {diagnosis.additional_measurements}"
    )
    for action in diagnosis.actions:
        st.write(f"• {action}")
    with st.expander("Observed evidence and alternative explanations"):
        st.json(asdict(diagnosis))
    if simulated:
        playbook = SCENARIO_PLAYBOOKS.get(get_scenario_key(scenario))
        if playbook:
            with st.expander("Preserved scenario playbook"):
                st.caption("Injected scenario hypothesis; these causes are not inferred from live timings.")
                st.write(playbook["cause"])
                for action in playbook["diagnosis"] + playbook["actions"]:
                    st.write(f"• {action}")
        st.info("Simulation state is session-local. Live incident history is isolated.")
    else:
        incidents = store.incidents()
        st.subheader("Active Incidents")
        active = incidents[incidents["ended"].isna()] if not incidents.empty else incidents
        if active.empty:
            st.info(
                "No confirmed active incidents. Pending warnings and unknown checks remain visible above."
            )
        else:
            st.dataframe(active.drop(columns=["evidence", "actions"]), width="stretch")
            with st.expander("Acknowledge / add incident notes"):
                chosen = st.selectbox("Incident ID", active["id"].tolist())
                notes = st.text_area("Notes", max_chars=2000)
                if st.button("Save notes and acknowledge"):
                    store.annotate(chosen, notes, acknowledge=True)
                    st.rerun()
        st.subheader("Historical Trends and Incident Timeline")
        history = store.history()
        if history.empty:
            st.info("No saved live measurements yet.")
        else:
            endpoints = st.multiselect(
                "Trend endpoints", history["id"].unique().tolist(), default=[history["id"].iloc[0]]
            )
            trend = history[history["id"].isin(endpoints)].sort_values("timestamp")
            if not trend.empty:
                pivot = trend.pivot_table(
                    index="timestamp", columns="id", values="latency_ms", aggfunc="mean", dropna=False
                )
                st.line_chart(pivot, x_label="UTC timestamp", y_label="Successful check duration (ms)")
            summary = performance_summary(history)
            if not summary.empty:
                st.dataframe(summary, width="stretch")
            st.caption(
                "Missing durations are unavailable, not zero. Compare identical methods/endpoints only. Latest 2,000 rows shown."
            )
            st.download_button(
                "Export measurements CSV",
                csv_export(history.drop(columns=["errors", "raw_samples"], errors="ignore")),
                "pingshield_measurements.csv",
                "text/csv",
            )
        if not incidents.empty:
            st.dataframe(incidents.drop(columns=["evidence", "actions"]), width="stretch")
            st.download_button(
                "Export incident history JSON",
                incidents.to_json(orient="records", indent=2),
                "pingshield_incidents.json",
                "application/json",
            )
        st.caption(
            "Event readiness: "
            + (
                "all configured checks currently healthy"
                if overall == "HEALTHY"
                else "review outstanding checks"
            )
            + ". This does not certify station connectivity, broadcast bitrate or game-server performance."
        )
    st.subheader("Infrastructure Telemetry")
    st.dataframe(df, width="stretch")


if mode == "Simulation":
    df = process_scenario(scenario, selected_zones, st.session_state.sim_window)
    states = st.session_state.sim_states
    # Only advance state once per intentional simulated window, not on widget reruns.
    marker = (scenario, st.session_state.sim_window, tuple(selected_zones))
    if st.session_state.get("sim_processed") != marker:
        for row in df.to_dict("records"):
            states[row["id"]] = transition(states.get(row["id"], EndpointState()), row, settings)
        st.session_state.sim_processed = marker
    if not df.empty:
        df["status"] = [states[r["id"]].status for r in df.to_dict("records")]
    render_dashboard(df, {}, True)
else:

    @st.fragment(run_every="2s")
    def live_dashboard():
        try:
            df, network = store.latest()
            render_dashboard(fresh_view(df, monitor.settings.stale_seconds), network, False)
        except (OSError, sqlite3.Error, ValueError) as exc:
            logging.exception("Read failed")
            st.error(f"History unavailable ({type(exc).__name__}); inspect local storage permissions/logs.")

    live_dashboard()
