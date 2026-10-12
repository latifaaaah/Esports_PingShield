# Esports-PingShield — V3 correctness and operations update

A local Python/Streamlit dashboard for configured TCP services, DNS resolution, and verified HTTPS HEAD checks. Designed as an esports operations portfolio/pilot tool. Preserves the V2 dark/neon styling, arena simulations, filters, endpoint grouping, charts and playbooks while correcting measurement semantics and adding recoverable alert states, local history and incidents.

**This is a tested local prototype, not a production-ready or network-wide monitoring system.** It measures from the machine running Python. It does not capture traffic, discover gaming PCs, measure in-game ping, infer DDoS from latency, or perform live ICMP packet-loss measurements. Rule-based diagnosis offers evidence and possible causes, not confirmed root causes.

## Quick start on macOS

Use Python **3.12**. The executed release test runtime is Linux/Python 3.12; native macOS validation is pending. Do not use Python 3.15 for this release.

1. Unzip the project; open Terminal in the `Esports-PingShield` folder.
2. Create/activate a project environment and install the bounded requirements:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1
```

Open the localhost URL printed by Streamlit. Initial mode is **Simulation**. Choose **Live (local only)** and press **Refresh measurements** to request one real measurement batch, or **Start monitoring** for periodic collection. Collection is asynchronous; the panel refreshes every two seconds. Stop safely cancels the in-flight worker; the previous completed batch remains displayed until stale. Start/Stop are shared between sessions of this server. Switching to simulation does not stop a previously started live monitor.

For the exact audited Linux dependency set:

```bash
python -m pip install -r requirements-lock.txt
```

The lock includes transitive packages and may require native-platform wheel checks on macOS/Windows. Prefer `requirements.txt` if the lock cannot install on your platform, then rerun tests and the vulnerability audit; record the resulting versions.

Windows activation: `.venv\Scripts\Activate.ps1`. Linux/macOS activation: `source .venv/bin/activate`. Use `python -m pip` and `python -m streamlit` to ensure the same environment is used. No administrator privileges are required for the supported probes.

## What you see

- Network Overview: worst current state of configured checks, with last completed/successful evidence in UTC.
- Endpoint Health: configured zones; a grouping visual, not a discovered physical topology.
- Network Performance: charts filtered by measurement method. Failed checks have no duration bar.
- Smart Diagnosis: deterministic explanations, error categories, evidence strength, alternatives and recommended checks.
- Active Incidents: confirmed severe endpoint states, acknowledgment and notes.
- Historical Trends: endpoint timelines and successful-sample mean/median/min/max/p95; CSV and JSON exports.
- Infrastructure Telemetry: complete normalized rows, sample counts, observed errors, raw state, alert state and incident references.
- Controls: interval, manual refresh, start/stop, read-only configuration preview. Edit the operator-owned configuration file to change targets.

## Interpretation

| Field / method | Meaning |
|---|---|
| `TCP connect` | Time establishing a TCP connection to the configured port, after DNS resolution. Not ICMP RTT or game ping. Refusal is a failed service check. |
| `DNS resolution` | DNS A query, then AAAA only if A has no answer, within one lifetime. Records the answering resolver when available. Cache behavior can affect timing. |
| `HTTPS HEAD (TLS + headers)` | TCP connect + verified TLS + HEAD response headers, excluding prior DNS. Body is not downloaded. Only 2xx validates this check. |
| `failure_rate_pct` | Unsuccessful checks / attempted checks in the window. For TCP rows this is TCP connection failure rate. Never packet loss. |
| `jitter_ms` | Mean absolute difference between successive **successful** check durations, in chronological order. It is TCP/DNS/HTTPS duration variation, not IP packet-delay variation. Requires >=2 successes. Failed attempts are omitted. |
| `latency_ms` | Mean successful duration only. No successes → null / N/A. Timeouts are counted separately. |
| `p95_ms` | Nearest-rank p95 only with >=20 successful samples. The default three-sample window has N/A; historical summary can accumulate enough samples. |
| `packet_loss_pct` | Only explicitly simulated ICMP fixtures have values. Live rows always have null. |
| `status` vs `raw_status` | Confirmed/hysteretic current alert state vs observation-based window classification. Reachable but slow can be CRITICAL; it is not UNREACHABLE. |

DNS/HTTP failures have explicit categories. A successful TCP check to `8.8.8.8:53` does not prove DNS resolution works. HTTPS redirects are recorded without following them and do not validate the destination application. HEAD 405 can mean the test method is unsuitable rather than an application outage.

## Configuration

Copy the example if you want editable policy overrides:

```bash
cp settings.example.json settings.json
```

`settings.py` holds conservative initial defaults. `settings.json` is a local operator-owned allowlist, not a public input form. No ranges or scans are accepted; at most 20 exact targets, four concurrent probes, 1–5 samples per window, 0.1–3 second phase timeouts. Interval is 10–3600 seconds **after batch completion**; stale lifetime must cover the interval. Default interval=30 seconds, samples=3, timeout=1.5 seconds, failure_windows=2, recovery_windows=2, stale_seconds=120, retention=30 days/10,000 completed batches.

Thresholds are per endpoint/method; defaults are initial assumptions, not universal esports performance guarantees. Require `recover_ms <= warn_ms < crit_ms`. Recovery requires latency below the independent recovery boundary and no warning/failure/variation condition. Calibrate policies on the intended host/network. Historical summaries help manual baseline calibration; automatic adaptive threshold learning is not implemented.

The gateway is discovered as metadata using macOS `route -n get default`, Linux `ip -j route show default` or Windows `Get-NetRoute`. Discovery failure is shown explicitly. There is no fallback router IP and no automatic attempt at gateway port 80. To monitor a router, add a **known authorized responding service**, set `scope=local`, and use an appropriate port/method. Closed ports alone cannot prove gateway failure. Local-path diagnosis remains limited when no local service is configured.

## Monitoring and history

`st.cache_resource` shares one coordinator between browser sessions. One isolated subprocess performs each completed batch. A SQLite lease prevents overlapping collector batches across processes using the same database. The worker has a hard 90-second overall deadline, including problematic DNS/TLS/header behavior; Stop terminates it safely. Partial/cancelled batches never replace the last completed batch. Network exceptions are isolated per endpoint.

For collection independent of browser activity:

```bash
python service.py
```

Use Ctrl-C to stop. Choose either this collector or the dashboard periodic collector for normal use. A lease prevents simultaneous batches, but running multiple periodic processes is not a supported scheduling arrangement and may produce extra non-overlapping checks. A host service supervisor/launchd installation and guaranteed always-on operation are not included. Dashboard Stop does not stop a separately launched CLI service.

SQLite lives in `data/pingshield.sqlite`, created on first launch. It stores UTC batch and sample timestamps, measurement metadata, diagnostic evidence, endpoint states and incident history. First-schema migration is versioned with `PRAGMA user_version`; unsupported future schemas are rejected. WAL, short transactions, primary keys, indexes and per-operation connection cleanup support single-host access. Data retention bounds both age and row count; SQLite reuses freed pages. High-water file size does not shrink automatically (offline VACUUM instructions below). Simulation is session-local and rejected by live persistence.

## Tests and verification

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
python -m ruff format . --check
python -m pip check
python -m pip_audit -r requirements-lock.txt
```

Tests mock DNS/HTTP/public targets and include an actual localhost TCP success/refusal test, isolated empty worker invocation, state/restart/retention/lease/error tests, and Streamlit widget/session tests. They do not depend on Google/Cloudflare availability.

Optional authorized live smoke test:

```bash
python smoke_live.py --live
```

This sends low-volume probes to the configured allowlist. It is separate from automated tests and does not replace the disconnect/reconnect checklist in `VALIDATION.md`. No public internet, user-machine or real venue validation was performed for this delivery.

## Troubleshooting

- **Missing module:** activate `.venv`, run `python -m pip install -r requirements.txt`, then `python -m pip check`.
- **Native-library import crash:** stop Python/Streamlit and reinstall the affected wheel, e.g. `python -m pip install --force-reinstall --no-cache-dir pyarrow`. Re-run tests; don't change project logic to hide the error.
- **No gateway detected:** check your real route/interface. Linux needs `ip`; macOS uses `/sbin/route`. IPv6-only and policy/VPN routes need manual review.
- **Red/severe after reconnect:** inspect raw state, successful sample counts, configured recovery threshold and confirmation windows. Failure durations are never synthetic timeout latency. Two cool healthy windows normally close the incident. Stale evidence becomes UNKNOWN.
- **Port refused:** the service is closed/rejecting; this alone does not imply host/network failure.
- **Unknown/no measurements:** request a batch; review config/storage errors and freshness, rather than assuming health.
- **HTTPS fails only:** review status, certificate/trust store, HEAD support and redirect policy.
- **Another collector owns batch:** stop duplicate periodic collectors; wait for the active batch or expired lease.
- **Storage unavailable:** stop collectors, inspect folder permissions/free disk; don't remove the database unless you intend to discard history. Back up with SQLite's backup API while live, or copy the database after clean shutdown.
- **Reclaim SQLite high-water disk space:** stop all collectors/dashboard, back up, then run SQLite `VACUUM` offline. A smaller retention value bounds retained data, not immediate physical shrinkage.

## Documentation

`AUDIT.md` — original V2 findings and priorities. `ARCHITECTURE.md` — flow/contracts/state model. `DIAGNOSIS_RULES.md` — evidence ordering. `CHANGELOG.md` — what/why/tests/compatibility. `TEST_RESULTS.md` — executed evidence. `VALIDATION.md` — pilot checklist. `LIMITATIONS.md` — incomplete capabilities/acceptance. `SECURITY.md` — operation boundaries. `DEPENDENCY_AUDIT.json` — exact resolved package advisory results.

Method/API references: [Streamlit fragments](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment), [Streamlit resource cache](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource), [dnspython resolver](https://dnspython.readthedocs.io/en/stable/resolver-class.html), [Python HTTP client](https://docs.python.org/3/library/http.client.html), [SQLite WAL](https://sqlite.org/wal.html). References informed implementation; executed checks and limitations remain the evidence for this release.
