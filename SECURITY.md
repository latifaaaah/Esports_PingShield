# Local operation and security review

- Local loopback binding is configured and explicit in launch instructions. No authentication/remote-access deployment has been implemented. Do not expose this app publicly.
- Exact authorized targets in an operator-owned allowlist, max 20; no CIDR ranges, port scans or device discovery. The HTTP/DNS/TCP probes send low-volume standard checks only. Simulation causes no network probes.
- Typed endpoint validation rejects malformed host/URL/port/threshold/path values. DNS checks require names rather than IP bypasses. Operators can intentionally configure private addresses; authorization is their deployment responsibility.
- Subprocess commands use fixed executable/argument lists with no shell. Windows PowerShell route query is a constant; no configured host is interpolated into it. Worker receives JSON through stdin.
- DNS lifetime and socket phases have timeouts; overall worker deadline caps adversarial header/DNS behavior. Maximum four probe threads, at most five samples per target; no unlimited retries.
- HTTPS verifies certificates/hostname using the OS/Python trust store, sends HEAD and reads headers only. Redirects are not followed. No credentials, payload capture or traffic inspection. Environment proxy credentials are not used by these stdlib direct sockets.
- Errors shown to users are categories, not stack traces. Local logs aid debugging; endpoint IDs/addresses and incident metadata are network-sensitive and exports should be shared intentionally. CSV strings are neutralized against spreadsheet formulas. JSON is explicit metadata, never arbitrary executable content.
- SQLite parameterized statements, transactional incident uniqueness, WAL and bounded logical retention. Protect local data/config directories using operating-system account permissions; encryption at rest is not implemented.
- Audited resolved dependency versions are recorded in DEPENDENCY_AUDIT.json. A clean advisory result is time-specific and not proof of complete security. Re-run after dependency changes.
- No deployment onto a real gaming-center network was performed. A controlled pilot requires operator authorization and the native validation checklist.
