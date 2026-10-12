# V2 source audit — 2026-10-11

Baseline: original V2 ZIP preserved unchanged. All ten text source/document files read; packaged CPython 3.13 cache files are generated artifacts, excluded from delivery. Nine existing unittest diagnosis tests passed in 0.007 s under the available Python runtime. Syntax parses. Live import fails on case-sensitive systems (`Collector.py` vs `collector`). Streamlit/Plotly are initially absent from the runtime. No live-network baseline was claimed.

## Data flow and measurement sources
`app.py` chooses `engine.process_scenario` (fixed invented fixture values) or `engine.process_live` → `Collector.collect_all` → host resolution (untimed, IPv4 only) → five TCP connections → pandas → engine thresholds → optional live diagnosis → HTML/Plotly/dataframe. `ping` is TCP connection establishment duration, including refusal handling; it is not ICMP RTT. `loss` is unsuccessful TCP attempts, not packet loss. `jitter` is sample standard deviation over successful TCP durations, zero with fewer than two. Gateway IP is hardcoded. Port 53 only tests TCP service reachability; port 443 only tests TCP, not DNS or HTTPS application health.

## Confirmed findings (priority order)
| Issue | Severity | File | Evidence/root cause | User impact | Proposed solution | Required verification | Priority |
|---|---|---|---|---|---|---|---|
| Import casing mismatch | High | Collector.py, engine.py | lowercase import, uppercase filename | live mode cannot run on Linux | lowercase module | import + live mocked integration | P0 |
| Synthetic failure latency | High | Collector.py | no success → timeout*1000 | false latency/averages and persistent red perception | null on failure; successful samples only | all timeout, mixed outcomes | P1 |
| Refusal counted as success | High | Collector.py | ConnectionRefusedError → pass | closed service shown healthy | distinct refused error, null duration | refusal regression | P1 |
| TCP failure labelled packet loss | High | UI/app/collector | loss from failed connects | misleading operational decisions | method-specific failure rate | label/UI tests | P1 |
| Gateway assumption | High | Collector.py | 192.168.1.1:80 | wrong router, false outage | discover route; do not assume responding gateway service | discovery and missing route tests | P1 |
| Unbounded DNS resolution | Medium | Collector.py | gethostbyname with no deadline | collection may hang | bounded DNS client, literal-IP direct path | timeout/NXDOMAIN tests | P1 |
| Jitter zero when insufficient | Medium | Collector.py | single successful sample → 0 | false stable link indication | null; documented variation definition | 0/1/multiple samples | P1 |
| No timestamps/freshness/recovery model | High | engine.py, app.py | instantaneous classify; no persisted state | no hysteresis/history; cannot explain recovery | explicit per-endpoint windows, persisted incidents, stale display | disconnect/reconnect/restart | P2 |
| Diagnosis consumes corrupted loss field | High | diagnosis.py | interprets inherited TCP loss | downstream evidence inherits errors | normalized method/errors, conservative rules | DNS/HTTP/partial/config tests | P3 |
| Web/DNS health unsupported | Medium | Collector.py | only TCP checks | application failures missed | real DNS/verified HTTPS checks | mock DNS/HTTP errors | P3 |
| Every rerun measures | Medium | app.py | button value discarded; live call unconditional | repeated traffic, UI blocking | shared bounded collector, cached completed batch, explicit refresh | concurrency/rerun tests | P4 |
| No persistent history/incidents | Medium | entire project | no storage | restart loses event context | transactional SQLite with retention | restart/storage tests | P4 |
| Empty data reported healthy | Medium | ui.py, app.py | df.empty considered healthy | false reassurance | UNKNOWN empty state | empty zone test | P1 |
| README and dependency constraints absent | Medium | README.md, requirements.txt | one-line readme, unbounded packages | unreproducible install | documented compatible constraints + tested lock | fresh install/check | P6 |
| Simulation root causes overly definite | Medium | config.py | scenario name asserts DDoS | could imply inference from latency | label injected hypotheses as fixtures | preserved simulations | P3 |

## Suspected risks, not verified bugs
- Public deployment/authentication risks: original archive has no binding policy, but deployment behavior was not observed.
- Dependency vulnerabilities: unpinned baseline cannot establish exact installed versions; requires dependency advisory tooling.
- Actual macOS route, VPN, IPv6 and link detection: not yet exercised on native macOS hardware.
- No evidence that stale caches specifically cause red after reconnect. Confirmed false failure durations, refusal semantics and thresholds can mislead; reproduction is required before assigning a single root cause.

## Scope and preservation
Preserve dark/neon CSS, four simulation playbooks, zone filters, topology-style endpoint grouping, manual refresh, plots and telemetry. Keep simulation isolated from live storage. No real venue deployment or network scanning. All incomplete acceptance criteria will be recorded in LIMITATIONS.md.

## Resolution mapping

P0–P3 confirmed measurement/import/label/empty-state issues are corrected and covered by automated tests. P2 current/historical states use transactional recovery and freshness. P4 bounded process collection, SQLite and incident history are implemented. P6 documentation/config/dependency constraints and tests are delivered. Findings are not evidence of native macOS or public live operation; outstanding route/VPN/link-state/baseline/pixel/live acceptance remains explicitly listed in LIMITATIONS.md. See CHANGELOG.md for issue-by-issue change/test/compatibility explanations and TEST_RESULTS.md for executed results.
