> Historical V2 record. See CHANGELOG.md and README.md for the current V3 implementation and commands.

# PingShield V2 — Safe diagnosis addition

- Adds `diagnosis.py`: read-only rule-based interpretation of live TCP checks.
- Adds `test_diagnosis.py`: unit tests for connectivity patterns.
- Adds a live-only diagnosis panel in `app.py`.
- Preserves the original collector, thresholds, simulation, styling, charts and telemetry.
- Does not claim TCP failures prove IP packet loss or a definitive root cause.

## Run

```bash
pip install -r requirements.txt
python3 -m unittest test_diagnosis.py -v
streamlit run app.py
```

## Known original issues (not changed)

- `Collector.py` casing conflicts with `from collector import collect_all` on case-sensitive file systems.
- Failed TCP attempts are displayed as a synthetic timeout latency (e.g. 1000 ms), distorting averages.
- Gateway TCP port 80 might be closed even when the router is reachable.
- Public DNS TCP port 53 checks are not DNS-resolution tests.
