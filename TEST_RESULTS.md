# Executed verification — 2026-10-11

## Baseline (original V2)

- Read all original text sources/docs; preserved original archive.
- `python3 -m unittest test_diagnosis.py -v`: **9 passed**, 0.007 seconds.
- Syntax parse passed for original Python files.
- Confirmed lowercase-import/uppercase-file incompatibility by source inspection.
- Did not claim baseline live network validation.

## Final clean environment

Runtime: Linux x86_64, Python 3.12.14. Dedicated `.release-venv` without system-site-packages. Installed `requirements-lock.txt` (39 resolved runtime packages) plus pytest 9.1.1 / Ruff 0.17.0.

`python -m pytest -q`:

```text
82 passed, 5 warnings in 6.20s
```

Five warnings are a Streamlit/NumPy generic timedelta deprecation in fragment timing; no test fails. Dependency pins freeze the tested versions; future upgrades should re-run the suite.

`python -m pip check`: **No broken requirements found.**

`ruff check`: **All checks passed.** `ruff format --check`: **all files formatted** (final recorded check below).

`pip-audit -r requirements.txt`: **No known vulnerabilities found**, 39 runtime packages. Exact resolved/audited versions are in `requirements-lock.txt` and the advisory result in `DEPENDENCY_AUDIT.json`. Advisory results are time-specific, not a complete security guarantee.

The first clean test attempt failed while importing the installed PyArrow native library (bus error before collection). Reinstalling the same PyArrow 25.0.1 wheel with `--force-reinstall --no-cache-dir` resolved it; the complete clean test suite subsequently passed. The underlying initial binary-loader cause was not established. No application code was changed to suppress it.

## Coverage exercised

- Correct null failed timing, mean/median/p95 support, TCP failure rate, duration variation with 0/1/multiple success samples.
- DNS lifetime, NXDOMAIN, resolver metadata, A→AAAA fallback, IP bypass and invalid DNS query configuration.
- TCP timeout/refusal/permission/TLS categories; successful TCP is separate from health.
- HTTPS 204/503/302/405, verified hostname context, HEAD behavior, resource cleanup and no redirect following.
- Healthy/all fail/local fail/external fail/one endpoint/partial/high-duration/variation/packet-loss simulation/DNS/HTTP/recovery/intermittent/config/empty/insufficient evidence.
- Filtered external TCP 53 while HTTPS succeeds does **not** become a WAN-outage conclusion.
- Failure/recovery confirmation, stale UNKNOWN, lower recovery threshold, duplicate timestamps and interruption by warning/unknown evidence.
- SQLite atomic batches, restart with incident history, duplicate batch identity, out-of-order rejection, aging/count retention, acknowledgment/notes, configuration removal and JSON export.
- Multiple lease owners/coordinators, refresh during active collection, cancellation, storage/collector exceptions and worker hard deadline.
- Real Streamlit AppTest script execution: original scenario playbooks, empty zones, live fixture refresh, charts, telemetry and two browser-session contexts.
- CSV formula neutralization and historical p95 from individual successful samples.

## Real checks actually performed

- A localhost TCP listener in the automated test accepted three real connections on this runtime; a subsequently closed loopback port produced refusal/null duration.
- An actual isolated subprocess with an empty target allowlist ran to completion and returned route metadata/empty measurements.
- No Google/Cloudflare/user-router/public DNS/HTTPS/venue probes were performed for delivery. DNS/HTTPS tests are deterministic mocks. Native Mac/Windows checks and real user-host disconnect/reconnect remain pending.

## Synthetic performance

Executed `benchmark.py` (100 in-memory generated fixture batches / 800 endpoint rows, temporary SQLite only; no real-network data):

| Measurement | Observed |
|---|---:|
| Total processing and storage | 3.793 seconds |
| Mean per batch | 37.93 ms |
| Peak tracked Python allocations | 0.47 MiB |
| SQLite file at completion | 892,928 bytes |

This does not measure Streamlit browser rendering, native-library allocations, venue load or worst-case network performance. Four concurrent probe threads, bounded settings and the 90-second hard worker deadline are implemented constraints, not claims of actual internet sampling latency.
