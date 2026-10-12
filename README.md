
# Esports-PingShield V3

### Network Monitoring, Performance Degradation Detection & Incident Management

**Esports-PingShield** is a Python-based network and service monitoring dashboard built with Streamlit. It helps technical operators monitor configured services, identify connectivity problems, detect performance degradation, and investigate incidents through evidence-based, rule-driven diagnostics.

The project is designed as a local monitoring prototype with potential applications in **IT Operations, Network Operations Centers (NOC), and Esports Event Technology**.

Unlike basic availability checks, Esports-PingShield distinguishes between a service being reachable and a service responding within acceptable performance thresholds.

> **Project status:** Tested local prototype and portfolio project. Not a production-ready or network-wide monitoring platform.

---

## Key Features

| Feature | Description |
|---|---|
| Network Monitoring | TCP connectivity, DNS resolution, and verified HTTPS HEAD checks |
| Performance Monitoring | Successful-check duration, failure rates, and duration variation |
| Intelligent Diagnostics | Rule-based analysis with supporting evidence, possible causes, and recommended troubleshooting actions |
| Incident Management | Incident detection, acknowledgment, tracking, and confirmed recovery |
| Historical Analysis | Stored measurements, endpoint trends, and statistical summaries |
| Interactive Dashboard | Streamlit interface with endpoint health, performance charts, and monitoring controls |
| Data Export | CSV and JSON exports for further investigation |
| Configurable Monitoring | Endpoint allowlist, thresholds, sampling, intervals, and recovery policies |
| Simulation Mode | Local scenarios for demonstrating monitoring behavior |

---

## Why This Project Matters

In technical operations, a successful connection does not always mean a service is performing well.

A service may remain reachable while experiencing unusually slow or inconsistent response times.

Esports-PingShield addresses this distinction by monitoring both **service availability** and **service-check performance**.

For esports event operations, this can provide supporting visibility into infrastructure and external service health, helping technical teams investigate potential issues during event preparation or live operations.

The current prototype does not directly measure game-server ping, gameplay packet loss, or real-time player experience.

---

## Dashboard Preview

The dashboard includes:

- **Network Overview:** Current health and monitoring status.
- **Endpoint Health:** Status of configured services grouped by zone.
- **Network Performance:** Protocol-specific measurement charts.
- **Smart Network Diagnosis:** Evidence-based diagnostic findings.
- **Active Incidents:** Incident status, acknowledgment, and recovery tracking.
- **Historical Trends:** Stored performance measurements and statistics.
- **Infrastructure Telemetry:** Detailed measurements and technical evidence.
- **Configuration Notes:** Monitoring methods, endpoints, and threshold explanations.

### Screenshots

Screenshots of the live dashboard, performance degradation detection, outage monitoring, and incident recovery will be added here.

---

## Real-World Validation: Performance Degradation

During a local monitoring session, Esports-PingShield detected performance degradation even though every configured check completed successfully.

### Observed Results

| Endpoint | Successful Checks | Observed State |
|---|---|---|
| Cloudflare DNS | 3/3 | HEALTHY |
| Google DNS | 3/3 | HEALTHY |
| System DNS | 3/3 | HEALTHY |
| Cloudflare Web | 3/3 | WARNING |
| Google Web | 3/3 | WARNING |

**Total: 15 successful checks out of 15 attempts.**

Despite the successful checks, both HTTPS endpoints were classified as WARNING.

The diagnostic engine reported:

**Latency variation degradation**

The finding indicated that successful service-check durations varied beyond the configured threshold.

Observed HTTPS check durations included approximately:

- Cloudflare Web: 555.7 ms
- Google Web: 556.3 ms

### Technical Significance

This scenario demonstrates that:

1. Service availability and service performance are different concepts.
2. Successful network checks can still exhibit degraded response behavior.
3. Rule-based monitoring can identify conditions requiring further investigation.
4. Diagnostic evidence can support troubleshooting without claiming a confirmed root cause.

These values represent HTTPS check durations, not in-game latency or ICMP ping.

---

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic and monitoring implementation |
| Streamlit | Interactive monitoring dashboard |
| SQLite | Local historical measurements and incident storage |
| TCP / DNS / HTTPS | Service connectivity and response checks |
| Pytest | Automated testing |
| Ruff | Code quality and formatting checks |

The application is intended to run locally on a monitoring host.

---

## System Architecture

Esports-PingShield separates monitoring, analysis, persistence, and presentation into different components.

### Main Components

- **Monitoring and collection:** Execute configured network checks.
- **State management:** Classify observations and confirm state transitions.
- **Diagnosis engine:** Evaluate evidence using deterministic rules.
- **Incident management:** Track severe conditions and recovery.
- **Storage layer:** Persist completed measurements and incidents.
- **Streamlit dashboard:** Display current and historical results.

### Simplified Workflow

```text
Configured Endpoints
        |
        v
Network Checks
(TCP / DNS / HTTPS)
        |
        v
Measurement Collection
        |
        v
State Evaluation
        |
        +----> Rule-Based Diagnosis
        |
        +----> Incident Management
        |
        v
SQLite Storage
        |
        v
Streamlit Dashboard
```

For more implementation details, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Installation

### Requirements

- Python 3.12
- pip
- Supported operating system and compatible dependencies

The documented release test environment used Linux and Python 3.12. The project has also been exercised locally on macOS, but full platform compatibility should be validated independently.

### 1. Clone or Download

```bash
git clone https://github.com/latifaaaah/Esports_PingShield.git
cd Esports_PingShield
```

Alternatively, download the repository ZIP from GitHub and extract it.

### 2. Create a Virtual Environment

```bash
python3.12 -m venv .venv
```

Activate it on macOS/Linux:

```bash
source .venv/bin/activate
```

For Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Launch the Dashboard

```bash
python -m streamlit run app.py --server.address 127.0.0.1
```

Open the local address displayed by Streamlit, usually:

`http://127.0.0.1:8501`

---

## How to Use

1. Launch the Streamlit dashboard.
2. Review the configured endpoints and monitoring settings.
3. Select **Simulation** for local demonstrations or **Live (local only)** for real checks.
4. Click **Refresh measurements** to collect one measurement batch.
5. Use **Start monitoring** for periodic collection.
6. Review endpoint health, performance charts, and diagnostic findings.
7. Inspect incidents and historical trends.
8. Use **Stop monitoring** to stop the dashboard's periodic collector.

Live collection is asynchronous, and the interface updates as results become available.

Monitoring runs from the machine hosting the Python application.

### Independent Collection

The project also includes a collector that can run separately from browser interaction:

```bash
python service.py
```

Stop it with `Ctrl+C`.

For normal use, choose either the dashboard periodic collector or the independent service. Running multiple periodic collectors is not the intended scheduling configuration.

---

## Monitoring Methods & Metric Accuracy

| Metric / Method | Interpretation |
|---|---|
| TCP Connect | Time required to establish a TCP connection to a configured service |
| DNS Resolution | Duration of a configured DNS resolution check |
| HTTPS HEAD | Duration of a verified HTTPS request through response headers, excluding prior DNS resolution |
| Failure Rate | Percentage of unsuccessful checks within a measurement window |
| Duration Variation (`jitter_ms`) | Mean absolute difference between consecutive successful check durations |
| Successful Duration (`latency_ms`) | Mean duration of successful checks |
| P95 | Nearest-rank 95th percentile, reported when at least 20 successful samples exist |
| Packet Loss | Available for explicitly simulated ICMP fixtures; not measured in live monitoring |

**Important:** TCP connection duration is not ICMP RTT. HTTPS duration is not game ping. The duration-variation metric is not network packet-delay jitter, and check failure rate is not packet loss.

The application distinguishes raw observations from confirmed alert states to reduce unstable status transitions.

---

## Alert States & Recovery

The monitoring system evaluates configured thresholds and confirmation windows to classify endpoint conditions.

Depending on the observations and confirmed state, the dashboard can display states such as:

- HEALTHY
- WARNING
- CRITICAL
- UNREACHABLE
- RECOVERING
- UNKNOWN

A service may be reachable while still exceeding its configured performance thresholds.

Recovery requires confirmation through subsequent healthy measurement windows rather than immediately clearing a previous severe state after a single successful check.

Stale measurements are not treated as proof of current health.

---

## Configuration

The project provides a configuration example:

```bash
cp settings.example.json settings.json
```

Default monitoring policies are defined in `settings.py`.

Supported configuration includes:

- Exact authorized monitoring targets.
- Measurement methods and ports.
- Warning, critical, and recovery thresholds.
- Sampling and collection intervals.
- Timeouts and confirmation windows.
- Data retention settings.

The configuration uses an operator-owned endpoint allowlist. It is not designed for arbitrary public network scanning.

The default collection interval is 30 seconds, with three samples per window and separate failure/recovery confirmation windows.

Thresholds should be calibrated for the intended network environment. Default values are not universal esports performance standards.

---

## Incident Management

Esports-PingShield supports a local incident lifecycle, including:

- Detection of confirmed severe endpoint conditions.
- Incident creation and persistence.
- Incident acknowledgment and operator notes.
- Tracking of active incidents.
- Confirmation of recovery.
- Recording of resolved incidents.

The project uses SQLite for persistent incident and measurement history.

The incident system is designed for a local monitoring prototype, not distributed enterprise incident management.

---

## Testing & Validation

The project includes automated tests covering monitoring logic, state handling, storage behavior, worker execution, and UI interactions.

### Reported Local Test Result

**82 tests passed** during a previous local test run.

This result documents a specific test execution and does not guarantee that every future environment or configuration will behave identically.

### Run Tests

Install development dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Execute the test suite:

```bash
python -m pytest -q
```

Run code quality checks:

```bash
python -m ruff check .
python -m ruff format . --check
```

Check installed dependencies:

```bash
python -m pip check
```

Audit the documented locked dependency set:

```bash
python -m pip_audit -r requirements-lock.txt
```

### Optional Live Smoke Test

```bash
python smoke_live.py --live
```

This performs low-volume checks against configured authorized endpoints.

Manual local scenarios have also included internet disconnection, reconnection, incident recovery, and successful checks with degraded HTTPS performance.

See [VALIDATION.md](VALIDATION.md) and [TEST_RESULTS.md](TEST_RESULTS.md) for additional validation procedures and recorded evidence.

---

## Esports Operations Relevance

Esports tournaments depend on reliable technical environments.

Potential uses of this prototype include:

- Monitoring selected external services during event preparation.
- Identifying degraded service-check performance.
- Supporting troubleshooting with recorded evidence.
- Tracking incidents and confirmed recovery.
- Reviewing historical service behavior.
- Demonstrating operational monitoring workflows.

### Current Limitations

The project does not currently:

- Measure actual in-game latency.
- Measure live ICMP packet loss.
- Capture network traffic.
- Discover or monitor individual gaming PCs automatically.
- Detect DDoS attacks.
- Monitor the entire venue network.
- Provide production-grade distributed monitoring.
- Determine confirmed root causes from rule-based evidence alone.

These capabilities would require additional monitoring methods, integrations, and validation.

---

## Security & Operational Boundaries

- Live monitoring uses an operator-controlled target allowlist.
- Monitoring runs locally.
- No administrator privileges are required for the supported probes.
- Network checks are limited to configured targets.
- SQLite data is stored locally.
- Public deployment and production security hardening are outside the current prototype scope.

Only monitor systems and services you are authorized to test.

See [SECURITY.md](SECURITY.md) for operational and security limitations.

---

## Project Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, components, and state model |
| [DIAGNOSIS_RULES.md](DIAGNOSIS_RULES.md) | Diagnostic rules and evidence evaluation |
| [VALIDATION.md](VALIDATION.md) | Validation scenarios and procedures |
| [TEST_RESULTS.md](TEST_RESULTS.md) | Recorded testing evidence |
| [SECURITY.md](SECURITY.md) | Security and operational boundaries |
| [LIMITATIONS.md](LIMITATIONS.md) | Known limitations and future acceptance criteria |
| [CHANGELOG.md](CHANGELOG.md) | Development changes and corrections |
| [AUDIT.md](AUDIT.md) | Earlier technical findings and priorities |
| [DEPENDENCY_AUDIT.json](DEPENDENCY_AUDIT.json) | Dependency audit results |

---

## Future Improvements

Potential development directions include:

- Additional authorized local infrastructure monitoring.
- Better esports-specific operational views.
- More extensive long-running reliability validation.
- Improved alert filtering and prioritization.
- Further baseline analysis and threshold calibration.
- Game-server-specific monitoring integrations.
- Expanded automated testing and deployment validation.

These are proposed improvements, not currently implemented capabilities.

---

## Project Summary

Esports-PingShield V3 demonstrates practical experience with:

- Python application development.
- Network and service monitoring.
- Performance measurement and alert classification.
- Rule-based troubleshooting.
- Incident lifecycle management.
- SQLite persistence.
- Automated testing.
- Interactive operational dashboards.

**The project's central engineering goal is to distinguish service availability from service performance and provide useful operational evidence when problems occur.**

---

**Built with Python, Streamlit, and SQLite.**

