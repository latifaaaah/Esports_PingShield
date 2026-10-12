# Authorized real-network pilot checklist

Automated tests cannot substitute for this checklist on the actual Mac/network. Do not disconnect an operating venue network to test it. Use your own lab host and network, or obtain explicit operator authorization.

1. Install Python 3.12 and a dedicated environment, record package versions, run pytest/Ruff/pip check/advisory audit.
2. Launch bound to 127.0.0.1, confirm localhost-only accessibility; verify dark dashboard, all four original arena scenarios/filters/charts/playbooks, empty zone state.
3. Run `/sbin/route -n get default` on macOS and compare gateway/interface/method shown after a completed live batch. Review VPN/multiple-interface differences; no address should be guessed on discovery failure.
4. Configure only authorized targets and one known responding local service if available. Verify independently that its selected port is expected to answer. Record baseline successful duration distribution for each method.
5. Request manual refresh; verify counts, timestamps, DNS answering resolver, HTTPS status/TLS and errors. Failed checks must have null duration; TCP failures must never appear as packet loss.
6. Start periodic monitoring, open a second browser tab; confirm one active worker/no overlapping batches. Stop and verify the worker ends, no partial batch is committed. Switching to simulation must not add fixture rows to live history.
7. On a personal lab host, disconnect Wi-Fi/Ethernet (or use safe host firewall rules), request/collect enough windows. Capture raw failure, pending WARNING, confirmed UNREACHABLE and opened incident.
8. Reconnect. Check RECOVERING, healthy evidence below recovery thresholds, eventual HEALTHY and same incident ID resolved with end time/duration. Historical severe incidents should remain visible, separate from current health.
9. Leave collection stopped longer than stale_seconds. Current states must become UNKNOWN/STALE and expired cards/chart timings unavailable. Start/refetch should restore current state without deleting history.
10. Compare a purposely closed local port with successful external targets. The diagnosis must identify local service/configuration possibilities, never conclude router down from refusal alone.
11. In an authorized controlled DNS test, force query failure while direct-IP TCP succeeds. Verify DNS-specific evidence; restore DNS and confirm no lasting wrong diagnosis.
12. Test a controlled HTTPS service returning 503, invalid certificate, redirect or HEAD 405. Compare successful TCP evidence; verify application/TLS categories, no redirect following and null failed duration.
13. Exercise intermittent windows and high-duration-but-successful windows using simulation first, then a controlled authorized lab if needed. Ensure high duration is never labelled loss of reachability.
14. Acknowledge/add notes, export CSV/JSON, restart app/collector, verify persisted current state and incident history. Test removal of a target: resolution must state configuration removal, not measured recovery.
15. Verify retention with a test copy of SQLite, disk/error handling and offline backups. Do not delete the real incident database for a test.
16. Record elapsed batch duration/CPU/memory and observed default sampling effects on the actual host. Confirm the 90-second deadline behavior for deliberately slow controlled targets.
17. Record pass/fail, timestamp, OS/Python versions, policy, configuration and screenshots you intentionally choose to share. Resolve failures before any venue pilot.

Optional smoke: `python smoke_live.py --live`; uses only configured allowlist and the same isolated worker. Review configuration before enabling it.
