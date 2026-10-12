from datetime import datetime, timedelta, timezone
import json
import ssl
import threading
import time
from unittest.mock import MagicMock

import dns.exception
import dns.resolver
import pandas as pd
import pytest

import collector
from collector import Sample, measure_target, probe, summarize
from diagnosis import diagnose_live
from engine import evaluate, process_scenario
from config import DISASTER_SCENARIOS
from monitor import Monitor, bounded_collect
from network import discover_network
from settings import Endpoint, Settings, load_settings
from state import EndpointState, fresh_view, transition
from storage import Store
from test_diagnosis import frame


@pytest.mark.parametrize(
    "outcomes,mean,failure,jitter",
    [
        ([], None, None, None),
        ([Sample(False, error="timeout")] * 3, None, 100, None),
        ([Sample(True, 10)], 10, 0, None),
        ([Sample(True, 10), Sample(False, error="refused"), Sample(True, 20)], 15, 33.3, 10),
    ],
)
def test_metrics(outcomes, mean, failure, jitter):
    result = summarize(outcomes)
    assert result["latency_ms"] == mean
    assert result["failure_rate_pct"] == failure
    assert result["jitter_ms"] == jitter


def test_p95_requires_twenty():
    assert summarize([Sample(True, n) for n in range(19)])["p95_ms"] is None
    assert summarize([Sample(True, n) for n in range(20)])["p95_ms"] == 18


@pytest.mark.parametrize(
    "exc,error",
    [
        (TimeoutError(), "timeout"),
        (ConnectionRefusedError(), "refused"),
        (PermissionError(), "permission"),
        (ssl.SSLCertVerificationError(), "tls_verification"),
        (dns.resolver.NXDOMAIN(), "nxdomain"),
    ],
)
def test_failed_probes_are_not_latency(monkeypatch, exc, error):
    monkeypatch.setattr(collector, "resolve", lambda *a: ("1.1.1.1", None))
    monkeypatch.setattr(collector, "connect_ip", lambda *a: (_ for _ in ()).throw(exc))
    result = probe(Endpoint("A", "1.1.1.1"), 1)
    assert not result.success and result.duration_ms is None and result.error == error


def test_tcp_success(monkeypatch):
    sock = MagicMock()
    monkeypatch.setattr(collector, "connect_ip", lambda *a: sock)
    result = probe(Endpoint("A", "1.1.1.1"), 1)
    assert result.success and result.duration_ms >= 0 and result.tcp_success
    sock.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "code,expected", [(204, None), (503, "http_error"), (302, "http_redirect"), (405, "http_error")]
)
def test_http_headers_status_tls_and_no_redirect(monkeypatch, code, expected):
    monkeypatch.setattr(collector, "resolve", lambda *a: ("1.1.1.1", "8.8.8.8"))
    monkeypatch.setattr(collector, "connect_ip", lambda *a: MagicMock())
    context = MagicMock()
    context.wrap_socket.return_value = MagicMock()
    monkeypatch.setattr(collector.ssl, "create_default_context", lambda: context)
    conn = MagicMock()
    conn.getresponse.return_value.status = code
    conn._context = context
    monkeypatch.setattr(collector.http.client, "HTTPSConnection", lambda *a, **kw: conn)
    result = probe(Endpoint("A", "example.com", method="https"), 1)
    assert result.error == expected and result.http_status == code and result.tcp_success
    assert conn.request.call_args.args[:2] == ("HEAD", "/")
    context.wrap_socket.assert_called_once()
    assert context.wrap_socket.call_args.kwargs["server_hostname"] == "example.com"
    conn.close.assert_called_once()


def test_dns_probe_specific(monkeypatch):
    monkeypatch.setattr(collector, "resolve", lambda *a: ("93.184.216.34", "192.168.1.1"))
    row = measure_target(Endpoint("DNS", "example.com", method="dns"), samples=2)
    assert row["method"] == "dns" and row["resolver"] == "192.168.1.1" and row["success_count"] == 2


def test_dns_timeout_and_v6_fallback(monkeypatch):
    resolver = MagicMock()
    resolver.resolve.side_effect = [dns.resolver.NoAnswer(), ["2001:db8::1"]]
    # A real answer carries the nameserver used, not just configured preference.
    answer = MagicMock()
    answer.__getitem__.return_value = "2001:db8::1"
    answer.nameserver = "1.1.1.1"
    resolver.resolve.side_effect = [dns.resolver.NoAnswer(), answer]
    monkeypatch.setattr(collector.dns.resolver, "Resolver", lambda: resolver)
    assert collector.resolve("example.com", 1) == ("2001:db8::1", "1.1.1.1")
    assert all(c.kwargs["lifetime"] <= 1 for c in resolver.resolve.call_args_list)
    resolver.resolve.side_effect = dns.exception.Timeout()
    assert probe(Endpoint("DNS", "example.com", method="dns"), 1).error == "timeout"


def test_ip_does_not_use_resolver(monkeypatch):
    monkeypatch.setattr(collector.dns.resolver, "Resolver", lambda: pytest.fail("IP must bypass DNS"))
    assert collector.resolve("2001:db8::1", 1) == ("2001:db8::1", None)


def test_socket_closes_on_failure(monkeypatch):
    sock = MagicMock()
    sock.connect.side_effect = TimeoutError()
    monkeypatch.setattr(collector.socket, "socket", lambda *a: sock)
    with pytest.raises(TimeoutError):
        collector.connect_ip("::1", 443, 1)
    sock.close.assert_called_once()


def test_collector_exception_isolated(monkeypatch):
    monkeypatch.setattr(collector, "measure_target", lambda *a: (_ for _ in ()).throw(RuntimeError()))
    df = evaluate(collector.collect_all(Settings(endpoints=(Endpoint("A", "1.1.1.1"),))))
    assert df.iloc[0]["status"] == "UNKNOWN"
    assert df.iloc[0]["errors"] == {"collector_error": 1}


@pytest.mark.parametrize(
    "options",
    [
        {"port": 0},
        {"port": True},
        {"host": "x;whoami"},
        {"host": "https://example.com"},
        {"warn_ms": 300, "crit_ms": 100},
        {"recover_ms": 500},
        {"path": "/\r\nx"},
        {"jitter_warn_ms": float("nan")},
        {"resolver": "not-an-ip"},
    ],
)
def test_endpoint_validation(options):
    args = dict(id="A", host="example.com")
    args.update(options)
    with pytest.raises((ValueError, TypeError)):
        Endpoint(**args)


@pytest.mark.parametrize(
    "options",
    [
        {"samples": 0},
        {"samples": 1.5},
        {"timeout": 0},
        {"interval": 5},
        {"stale_seconds": 10},
        {"retention_days": 0},
        {"max_batches": 0},
    ],
)
def test_settings_validation(options):
    with pytest.raises(ValueError):
        Settings(**options)


def test_duplicate_allowlist():
    with pytest.raises(ValueError):
        Settings(endpoints=(Endpoint("A", "1.1.1.1"),) * 2)


def test_config_malformed(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{")
    with pytest.raises(ValueError):
        load_settings(path)


def test_latency_does_not_imply_unreachable():
    df = frame(latency=500)
    assert (df["status"] == "CRITICAL").all()
    assert (df["success_count"] == 3).all()


def next_row(raw, second, latency=10):
    return dict(
        raw_status=raw, timestamp=f"2026-10-11T12:00:{second:02d}+00:00", latency_ms=latency, recover_ms=80
    )


def test_confirm_recovery_hysteresis_duplicate_and_unknown():
    policy = Settings()
    state = EndpointState()
    state = transition(state, next_row("UNREACHABLE", 1, None), policy)
    assert state.status == "WARNING"
    state = transition(state, next_row("UNREACHABLE", 2, None), policy)
    assert state.status == "UNREACHABLE"
    same = transition(state, next_row("UNREACHABLE", 2, None), policy)
    assert same == state
    state = transition(state, next_row("UNKNOWN", 3, None), policy)
    state = transition(state, next_row("WARNING", 4, 120), policy)
    state = transition(state, next_row("HEALTHY", 5, 90), policy)
    assert state.status == "RECOVERING" and state.healthy == 0
    state = transition(state, next_row("HEALTHY", 6), policy)
    assert state.status == "RECOVERING"
    state = transition(state, next_row("HEALTHY", 7), policy)
    assert state.status == "HEALTHY"


def test_stale_unknown():
    df = frame()
    now = datetime.now(timezone.utc) + timedelta(hours=1)
    stale = fresh_view(df, 120, now)
    assert (stale["status"] == "UNKNOWN").all() and diagnose_live(stale).title == "Expired measurements"
    assert (df["status"] == "HEALTHY").all()


def test_dns_failure_with_ip_success():
    df = frame()
    df.loc[0, "method"] = "dns"
    df.loc[0, "success_count"] = 0
    df.at[0, "errors"] = {"nxdomain": 3}
    df = evaluate(df)
    assert diagnose_live(df).title == "DNS resolution failure"


def test_http_app_failure():
    df = frame()
    df.loc[1, "method"] = "https"
    df.loc[1, "success_count"] = 0
    df.loc[1, "tcp_success"] = True
    df.at[1, "errors"] = {"http_error": 3}
    df = evaluate(df)
    assert diagnose_live(df).title == "HTTP application or TLS check failure"


def test_one_provider_not_wan_proof():
    df = frame(False, (True, True))
    df["provider"] = "one"
    assert diagnose_live(df).title == "Partial external connectivity failure"


def test_configuration_diagnosis():
    df = frame()
    df.at[0, "errors"] = {"config_error": 1}
    df = evaluate(df)
    assert diagnose_live(df).title == "Monitoring configuration error"


def test_simulation_all_scenarios_repeatable():
    zones = ["Stage Left", "Stage Right", "Production Booth", "Server Rack"]
    for scenario in DISASTER_SCENARIOS.values():
        a = process_scenario(scenario, zones)
        b = process_scenario(scenario, zones)
        pd.testing.assert_frame_equal(a.drop(columns="timestamp"), b.drop(columns="timestamp"))
        assert diagnose_live(a).timestamp
    assert process_scenario(DISASTER_SCENARIOS["NORMAL"], []).empty


def batch(failed=False, time_offset=0):
    df = frame(external_failures=(failed, False)).iloc[1:].copy()
    df["timestamp"] = (datetime.now(timezone.utc) + timedelta(seconds=time_offset)).isoformat()
    return df


def test_store_incident_restart_idempotence_retention_and_export(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    policy = Settings(max_batches=10)
    store.save_batch(batch(True, 0), policy, {})
    bad = store.save_batch(batch(True, 1), policy, {}, "confirmed")
    assert bad.iloc[0]["status"] == "UNREACHABLE"
    assert len(store.incidents()) == 1
    assert store.save_batch(batch(True, 2), policy, {}, "confirmed").equals(store.latest()[0])
    store = Store(tmp_path / "db.sqlite")
    recovery = store.save_batch(batch(False, 3), policy, {})
    assert recovery.iloc[0]["status"] == "RECOVERING"
    store.save_batch(batch(False, 4), policy, {})
    incident = store.incidents().iloc[0]
    assert incident["status"] == "RESOLVED" and incident["ended"] and incident["duration_seconds"] >= 0
    assert json.loads(store.incidents().to_json(orient="records"))[0]["id"] == incident["id"]
    for n in range(5, 20):
        store.save_batch(batch(False, n), policy, {})
    with store.connection() as conn:
        assert conn.execute("SELECT count(*) FROM batches").fetchone()[0] == 10
    assert len(store.history()) == 20


def test_simulation_rejected_and_older_batch_rejected(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    df = batch()
    df["mode"] = "simulation"
    with pytest.raises(ValueError):
        store.save_batch(df, Settings(), {})
    store.save_batch(batch(False, 2), Settings(), {})
    with pytest.raises(ValueError):
        store.save_batch(batch(False, 0), Settings(), {})


def test_ack_notes_and_removed_target(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    policy = Settings(failure_windows=1)
    store.save_batch(batch(True, 0), policy, {})
    incident = store.incidents().iloc[0]
    store.annotate(incident["id"], "Investigating", True)
    assert store.incidents().iloc[0]["status"] == "ACKNOWLEDGED"
    store.save_batch(batch(False, 1).iloc[1:], policy, {})
    assert "recovery not verified" in store.incidents().iloc[0]["notes"]


def test_lease_concurrent_owners(tmp_path):
    a = Store(tmp_path / "db.sqlite")
    b = Store(tmp_path / "db.sqlite")
    assert a.acquire("a") and not b.acquire("b")
    b.release("b")
    assert not b.acquire("b")
    a.release("a")
    assert b.acquire("b")
    with b.connection() as conn:
        conn.execute("UPDATE lease SET expires=0")
    assert a.acquire("a")


def wait_until(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.01)
    pytest.fail("Timed out waiting for coordinator")


def test_monitor_sessions_no_overlap_and_safe_stop(tmp_path):
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def collect(settings, cancel):
        calls.append(1)
        entered.set()
        release.wait(2)
        return batch(), {}

    monitor = Monitor(Store(tmp_path / "db.sqlite"), Settings(), collect)
    try:
        assert monitor.request()
        assert entered.wait(2)
        assert not monitor.request()  # second session refresh during active batch
        monitor.stop()
        release.set()
        wait_until(lambda: not monitor.status()["busy"])
        assert monitor.store.latest()[0].empty  # cancelled batch not committed
        assert len(calls) == 1
        assert monitor.request()
        wait_until(lambda: monitor.status()["last_completed"] is not None)
    finally:
        monitor.close()
    assert not monitor.thread.is_alive()


def test_second_coordinator_does_not_collect(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    assert store.acquire("external")
    monitor = Monitor(store, Settings(), lambda *a: pytest.fail("Must honor lease"))
    try:
        monitor.request()
        wait_until(lambda: monitor.status()["error"] is not None)
        assert "Another collector" in monitor.status()["error"]
    finally:
        monitor.close()


def test_monitor_storage_error_graceful(tmp_path, monkeypatch):
    store = Store(tmp_path / "db.sqlite")
    monkeypatch.setattr(store, "save_batch", lambda *a: (_ for _ in ()).throw(OSError()))
    monitor = Monitor(store, Settings(), lambda *a: (batch(), {}))
    try:
        monitor.request()
        wait_until(lambda: monitor.status()["error"] is not None)
        assert not monitor.status()["busy"]
    finally:
        monitor.close()


def test_worker_cancel_kills_process(monkeypatch):
    process = MagicMock()
    process.poll.return_value = None
    monkeypatch.setattr("monitor.subprocess.Popen", lambda *a, **kw: process)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(InterruptedError):
        bounded_collect(Settings(), cancel)
    process.kill.assert_called_once()


def test_gateway_mac_and_linux_missing(monkeypatch):
    monkeypatch.setattr("network.platform.system", lambda: "Darwin")
    result = MagicMock()
    result.stdout = "gateway: 192.168.10.1\ninterface: en0\n"
    monkeypatch.setattr("network.subprocess.run", lambda *a, **kw: result)
    info = discover_network()
    assert info.gateway == "192.168.10.1" and info.interface == "en0"
    monkeypatch.setattr("network.platform.system", lambda: "Linux")
    result.stdout = "[]"
    assert discover_network().gateway is None


def test_no_gateway_fallback_on_command_error(monkeypatch):
    monkeypatch.setattr("network.subprocess.run", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    assert discover_network().gateway is None


def test_actual_loopback_tcp_success_and_refusal():
    """Real sockets on this host only; does not claim public/venue validation."""
    import socket

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(3)
    port = listener.getsockname()[1]

    def accept_three():
        for _ in range(3):
            conn, _ = listener.accept()
            conn.close()

    thread = threading.Thread(target=accept_three, daemon=True)
    thread.start()
    try:
        row = measure_target(Endpoint("LOOPBACK", "127.0.0.1", port=port, scope="local"), 3, 0.5)
        assert row["success_count"] == 3 and row["latency_ms"] is not None
        thread.join(timeout=2)
        assert not thread.is_alive()
    finally:
        listener.close()
    failed = measure_target(Endpoint("LOOPBACK", "127.0.0.1", port=port, scope="local"), 1, 0.5)
    assert failed["latency_ms"] is None and failed["errors"].get("refused") == 1


def test_real_isolated_worker_with_no_endpoints():
    frame, network = bounded_collect(Settings(endpoints=()), threading.Event())
    assert frame.empty and "method" in network


def test_worker_hard_deadline_and_failure(monkeypatch):
    process = MagicMock()
    process.poll.return_value = None
    monkeypatch.setattr("monitor.subprocess.Popen", lambda *a, **kw: process)
    monkeypatch.setattr("monitor.BATCH_DEADLINE", 0)
    with pytest.raises(TimeoutError):
        bounded_collect(Settings(), threading.Event())
    process.kill.assert_called_once()


def test_tls_failure_closes_unwrapped_socket(monkeypatch):
    raw = MagicMock()
    monkeypatch.setattr(collector, "resolve", lambda *a: ("1.1.1.1", None))
    monkeypatch.setattr(collector, "connect_ip", lambda *a: raw)
    conn = MagicMock()
    conn._context.wrap_socket.side_effect = ssl.SSLCertVerificationError()
    monkeypatch.setattr(collector.http.client, "HTTPSConnection", lambda *a, **kw: conn)
    result = probe(Endpoint("A", "example.com", method="https"), 1)
    assert result.error == "tls_verification" and result.tcp_success and result.duration_ms is None
    raw.close.assert_called_once()
    conn.close.assert_called_once()


def test_windows_gateway_and_linux_metric_choice(monkeypatch):
    from unittest.mock import MagicMock

    result = MagicMock()
    monkeypatch.setattr("network.subprocess.run", lambda *a, **kw: result)
    monkeypatch.setattr("network.platform.system", lambda: "Windows")
    result.stdout = '{"NextHop":"10.0.0.1","InterfaceAlias":"Wi-Fi"}'
    assert discover_network().gateway == "10.0.0.1"
    monkeypatch.setattr("network.platform.system", lambda: "Linux")
    result.stdout = (
        '[{"gateway":"10.0.0.1","dev":"eth0","metric":100},{"gateway":"10.2.0.1","dev":"eth1","metric":5}]'
    )
    assert discover_network().interface == "eth1"


def test_ipv4_literal_dns_config_rejected():
    with pytest.raises(ValueError):
        Endpoint("DNS", "8.8.8.8", method="dns")


def test_warning_interrupts_consecutive_failures():
    state = EndpointState()
    policy = Settings()
    state = transition(state, next_row("UNREACHABLE", 1, None), policy)
    state = transition(state, next_row("WARNING", 2, 120), policy)
    state = transition(state, next_row("UNREACHABLE", 3, None), policy)
    assert state.status == "WARNING" and state.failures == 1


def test_old_day_retention(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    old = batch()
    old["timestamp"] = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    store.save_batch(old, Settings(), {})
    assert store.history().empty


def test_read_store_error_raises_instead_of_fake_health(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    store.path = tmp_path / "missing" / "db.sqlite"
    import sqlite3

    with pytest.raises(sqlite3.Error):
        store.latest()


def test_intermit_history_and_confirmed_recovery():
    current = frame()
    history = pd.concat(
        [
            frame(external_failures=(bool(n % 2), False)).assign(timestamp=f"2026-10-11T12:00:{n:02d}+00:00")
            for n in range(6)
        ]
    )
    assert "Intermittent connectivity" in diagnose_live(current, history=history).title
    current["previous_status"] = "RECOVERING"
    assert diagnose_live(current).title == "Network recovery confirmed"


def test_historical_p95_uses_actual_success_samples():
    from reporting import performance_summary

    df = pd.DataFrame(
        [
            {
                "id": "A",
                "method": "tcp",
                "raw_samples": [{"success": True, "duration_ms": n} for n in range(20)]
                + [{"success": False, "duration_ms": 1000}],
            }
        ]
    )
    result = performance_summary(df).iloc[0]
    assert result["successful_samples"] == 20 and result["p95_ms"] == 18 and result["mean_ms"] == 9.5


def test_tcp53_filtered_but_https_works_is_not_wan_outage():
    df = frame(False, (True, True))
    web = df.iloc[[0]].copy()
    web["id"] = "WEB"
    web["scope"] = "external"
    web["method"] = "https"
    web["provider"] = "web"
    combined = pd.concat([df, web], ignore_index=True)
    assert diagnose_live(combined).title == "Partial external connectivity failure"


def test_simultaneous_lease_contenders(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    store = Store(tmp_path / "db.sqlite")
    gate = threading.Barrier(8)

    def attempt(index):
        gate.wait(timeout=2)
        return store.acquire(str(index))

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(8)))
    assert sum(outcomes) == 1


def test_boolean_numeric_configuration_rejected():
    with pytest.raises(ValueError):
        Settings(timeout=True)
    with pytest.raises(ValueError):
        Endpoint("A", "example.com", warn_ms=True, recover_ms=0.5)
