# Deterministic diagnosis rules

Every result contains title, severity, observed evidence, possible causes, alternatives, evidence strength, recommended steps, affected IDs, timestamp, current state and whether more evidence is needed. Severity of a pattern can differ from the current confirmed alert state while failure confirmation is pending. Evidence strength is descriptive, never a fabricated percentage. The same rule function consumes live and simulation schemas.

Evaluation order prevents weaker explanations from overriding stronger method-specific evidence:

1. Empty/missing schema → UNKNOWN.
2. Expired measurements → UNKNOWN, refresh required.
3. Configuration errors → review target/method/policy, not an outage claim.
4. Unusable/unknown checks → insufficient evidence.
5. DNS query fails while direct-IP TCP works → DNS failure pattern; NXDOMAIN can be name-specific.
6. TCP succeeded but HTTPS validation failed → HTTP/TLS/HEAD/redirect issue, not internet failure.
7. All configured checks fail → widespread failures; fault location unconfirmed.
8. TCP checks to >=2 independently labelled providers fail and no external TCP/HTTPS path succeeds → external reachability problem; local healthy service strengthens a WAN hypothesis.
9. Local configured service fails while external services respond → local service/configuration issue; a closed port does not prove gateway failure.
10. A subset fails → partial service outage, not total internet outage.
11. Simulated ICMP loss exists → simulated packet-loss pattern only.
12. Mixed success/failure within a window → intermittent check failures.
13. Duration variation exceeds configured method threshold → variation degradation.
14. Confirmed failing checks resume → RECOVERING; later confirmation → recovery confirmed.
15. At least three severe/non-severe changes in last ten stored windows → recent intermittent pattern (history, not current outage).
16. Elevated duration without failures → performance degradation, not UNREACHABLE.
17. All configured checks within thresholds → healthy monitored services, not a guarantee of the whole venue.

A local network hardware outage cannot be confirmed by this collector. Default route/interface metadata is displayed, but route existence alone is not a connectivity test. VPN policy routing, ICMP loss, broadcast throughput and game quality require additional authorized tools/measurements. Public targets are examples, not a sole local-health test. Provider labels are operator assertions and should represent truly independent paths/services when configured.
