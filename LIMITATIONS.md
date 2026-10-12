# Known limitations and incomplete acceptance criteria

This release is a local prototype/pilot candidate. It must not be labelled production-ready, enterprise-grade, AI-powered or network-wide real-time monitoring.

## Implemented and covered

Correct method labels; null failed timings; refusal/timeout categories; successful-sample statistics and historical p95; real DNS and verified HTTPS checks; reachable vs performance state separation; hysteresis/confirmation/recovery and stale UNKNOWN; deterministic diagnosis; shared coordinator and non-overlap lease; local persistence/incident lifecycle/exports; isolated simulation; configuration validation; preserved CSS/playbooks/zone chart features; deterministic regression and Streamlit session checks.

## Incomplete or intentionally limited

| Requested capability / acceptance item | Status and boundary |
|---|---|
| Native macOS compatibility verification | Pending. macOS route parsing is mocked; no native Mac was available. Recommended Python 3.12 install and checklist provided. |
| User's real disconnect/reconnect/live network validation | Pending. Real localhost TCP success/refusal was tested; public targets, user network and venue network were not measured for delivery. |
| Cross-platform VPN/interface/link/IPv6 gateway awareness | Partial. IPv4 default-route metadata; literal IPv6 probes and A→AAAA resolution supported. No comprehensive VPN policy routing, interface link-state event stream, IPv6-only default-route discovery or native Windows validation. |
| Confirm local router/hardware outage | Insufficient without a known local service or independent link evidence. No automatic gateway port guess. Local failures remain hypotheses. |
| Live ICMP packet loss / game-server quality | Not implemented. Live failure percentages are check failure rates. Packet-loss fixture is explicitly simulated. |
| Automatically adaptive baseline thresholds | Not implemented. Validated per-endpoint policies plus historical sample summaries support manual calibration. |
| Per-group inherited threshold policies | Configure equivalent per-endpoint policies; no group inheritance layer. |
| Fully deterministic protocol-rich arena station topology | Partial fixture simulations use the normalized contract; fixtures do not represent discovered devices. |
| Guaranteed always-on distributed monitoring | Not implemented. CLI survives browser closure while its process runs; no launchd/systemd supervisor or distributed deployment. One periodic process is supported; shared lease prevents simultaneous batches, not duplicate sequential schedules. |
| DNS resolver-change notifications / multiple resolver comparison | Resolver used is recorded per sample; no separate configuration-change incident stream. |
| Strict whole-request HTTPS timing including DNS | HTTPS duration explicitly excludes DNS, includes connect/TLS/headers; worker enforces 90-second whole-batch deadline. Slow-trickle server phases are capped by parent cancellation rather than each header byte. |
| UI screenshot/pixel rendering comparison | CSS preserved and real Streamlit script/widget/chart construction tested. No browser pixel/screenshot acceptance was performed. |
| Local timezone display | Internal UTC and dashboard explicitly labelled UTC; automatic local timezone presentation is not implemented. |
| Unbounded storage growth | Logical age/count retention implemented; SQLite high-water disk pages are reused. Automatic physical compaction and disk-quota enforcement are not implemented. |
| Incident evidence retention | Per-batch linked rows plus latest incident evidence retained within retention policy; oldest supporting rows may expire. Not an immutable audit archive. |
| Release certification | No native/venue pilot certification. See TEST_RESULTS.md for actual executed evidence. |

## Safe follow-up work

After native Mac and authorized-network validation, calibrate endpoint policies, add explicit local services, decide whether ICMP is needed, and choose a host supervisor. Remote access would require authentication, authorization, TLS and a separate security design. Keep measurement truthfulness ahead of cosmetic additions.
