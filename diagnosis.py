"""Transparent evidence patterns. Hypotheses never become asserted root causes."""

from dataclasses import dataclass
import pandas as pd

from collector import utc_now


@dataclass(frozen=True)
class Diagnosis:
    title: str
    severity: str
    explanation: str
    actions: tuple[str, ...]
    evidence: tuple[str, ...] = ()
    possible_causes: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    evidence_strength: str = "limited"
    affected_endpoints: tuple[str, ...] = ()
    timestamp: str = ""
    current_state: str = "UNKNOWN"
    additional_measurements: bool = True


def diagnose_live(df, network: dict | None = None, history: pd.DataFrame | None = None) -> Diagnosis:
    if df is None or df.empty:
        return Diagnosis(
            "No measurements available",
            "UNKNOWN",
            "Not enough data to diagnose connectivity.",
            ("Collect a completed measurement window.",),
            timestamp=utc_now(),
        )
    required = {"id", "status", "success_count", "sample_count", "method", "scope", "provider", "errors"}
    if not required.issubset(df.columns):
        return Diagnosis(
            "Incomplete measurement data",
            "UNKNOWN",
            "Required normalized fields are missing.",
            ("Review collector output.",),
            timestamp=utc_now(),
        )
    rows = df.to_dict("records")
    bad = [r for r in rows if r["status"] != "HEALTHY"]
    failed = [r for r in rows if r["sample_count"] > 0 and r["success_count"] == 0]
    external_tcp = [r for r in rows if r["scope"] == "external" and r["method"] == "tcp"]
    ip_good = any(r["success_count"] > 0 for r in external_tcp)
    local = [r for r in rows if r["scope"] == "local" and r["sample_count"] > 0]
    external = [r for r in rows if r["scope"] == "external" and r["sample_count"] > 0]
    evidence = tuple(
        f"{r['id']}: {r['success_count']}/{r['sample_count']} successful {r['method']} checks; "
        f"state={r['status']}; errors={r['errors']}"
        for r in rows
    )
    timestamp = max((r["timestamp"] for r in rows if r.get("timestamp")), default=utc_now())

    current = next(
        (
            s
            for s in ("UNREACHABLE", "CRITICAL", "UNKNOWN", "RECOVERING", "WARNING")
            if any(r["status"] == s for r in rows)
        ),
        "HEALTHY",
    )

    def result(
        title, severity, explanation, causes=(), actions=(), alternatives=(), strength="moderate", more=True
    ):
        return Diagnosis(
            title,
            severity,
            explanation,
            tuple(actions) or ("Repeat measurements and inspect the affected service configuration.",),
            evidence,
            tuple(causes),
            tuple(alternatives),
            strength,
            tuple(str(r["id"]) for r in bad),
            timestamp,
            current,
            more,
        )

    if any(r.get("freshness") == "STALE" for r in rows):
        return result(
            "Expired measurements",
            "UNKNOWN",
            "Old evidence cannot describe current network health.",
            actions=("Refresh measurements or start monitoring.",),
            strength="insufficient",
        )
    if any(r["errors"].get("config_error") for r in rows):
        return result(
            "Monitoring configuration error",
            "UNKNOWN",
            "A configured check is invalid or unsuitable.",
            actions=("Verify target, port, authorization and expected service.",),
        )
    if any(r["status"] == "UNKNOWN" for r in rows):
        return result(
            "Unknown or insufficient evidence",
            "UNKNOWN",
            "One or more checks have insufficient usable evidence.",
            actions=("Review sample counts, collector errors and optional gateway service configuration.",),
            strength="insufficient",
        )
    dns_failed = [r for r in failed if r["method"] == "dns"]
    if dns_failed and ip_good:
        return result(
            "DNS resolution failure",
            "WARNING",
            "Direct IP TCP checks work while DNS queries fail.",
            ("Resolver configuration, DNS filtering, or a nonexistent test name.",),
            (
                "Inspect the DNS error category and configured resolver.",
                "Compare another authorized DNS name/resolver.",
            ),
            ("NXDOMAIN may affect only the queried name; cache behavior differs from applications.",),
        )
    http_failed = [r for r in failed if r["method"] == "https" and r.get("tcp_success")]
    if http_failed:
        return result(
            "HTTP application or TLS check failure",
            "WARNING",
            "TCP succeeded, but HTTPS health was not validated.",
            ("HTTP error, unvalidated redirect, certificate failure, or unsupported HEAD request.",),
            ("Inspect recorded HTTP status/error; verify TLS and HEAD support.",),
            ("This does not prove the host or internet is down.",),
        )
    if failed and len(failed) == len(rows):
        return result(
            "Widespread connectivity failures",
            "CRITICAL",
            "All configured checks failed; outage location is unconfirmed.",
            ("Local link, routing, WAN, firewall or endpoint restrictions.",),
            ("Check Wi-Fi/Ethernet and default route.", "Verify services and test independent paths."),
            ("Closed/filtered ports can produce the same pattern.",),
        )
    external_connect = [r for r in external if r["method"] in {"tcp", "https"}]
    providers_failed = {r["provider"] for r in external_tcp if r["success_count"] == 0}
    if (
        external_tcp
        and all(r["success_count"] == 0 for r in external_tcp)
        and len(providers_failed) >= 2
        and not any(r["success_count"] > 0 or r.get("tcp_success") is True for r in external_connect)
    ):
        local_good = any(r["success_count"] > 0 for r in local)
        return result(
            "External targets unreachable",
            "CRITICAL",
            "Multiple independent external TCP checks fail"
            + (
                " while a local service responds." if local_good else "; local-path evidence is insufficient."
            ),
            ("WAN, route, firewall, or restrictions on the checked services.",),
            ("Inspect WAN status and routes.", "Compare alternate authorized ports and providers."),
            ("A default route alone is not proof of gateway connectivity.",),
        )
    if (
        local
        and all(r["success_count"] == 0 for r in local)
        and any(r["success_count"] > 0 for r in external)
    ):
        return result(
            "Gateway/local service check failed",
            "WARNING",
            "External services respond; local port failure is not gateway failure.",
            ("Closed local service, filtering or incorrect target.",),
            ("Verify the configured local service and gateway address.",),
        )
    if failed:
        return result(
            "Partial external connectivity failure",
            "WARNING",
            "A subset of services fail while others succeed.",
            ("Service outage, target configuration, DNS or filtering.",),
            ("Compare failing targets, ports and protocols with working services.",),
        )
    if any(pd.notna(r.get("packet_loss_pct")) and r["packet_loss_pct"] > 0 for r in rows):
        return result(
            "Packet-loss fixture degradation",
            "WARNING",
            "Only simulated ICMP packet-loss evidence is available.",
            actions=(
                "In live operation use a separately authorized ICMP tool; TCP failures are not packet loss.",
            ),
        )
    if any(r.get("failure_rate_pct", 0) > 0 for r in rows):
        return result(
            "Intermittent check failures",
            "WARNING",
            "Successful and failed checks coexist within the current window.",
            ("Transient service, routing or filtering issue.",),
            ("Compare several windows before escalating.",),
        )
    if any(pd.notna(r.get("jitter_ms")) and r["jitter_ms"] > r["jitter_warn_ms"] for r in rows):
        return result(
            "Latency variation degradation",
            "WARNING",
            "Successful check duration variation exceeds the configured threshold.",
            ("Changing path load or service processing variation.",),
            ("Compare protocol-specific baselines over multiple windows.",),
        )
    if any(r["status"] == "RECOVERING" for r in rows):
        return result(
            "Network recovery",
            "RECOVERING",
            "Checks resumed; healthy confirmation windows are still required.",
            actions=("Wait for configured recovery confirmation and inspect incident history.",),
            more=False,
        )
    if any(r.get("previous_status") == "RECOVERING" and r["status"] == "HEALTHY" for r in rows):
        return result(
            "Network recovery confirmed",
            "HEALTHY",
            "The configured healthy-window criterion was met after an incident.",
            actions=("Review the resolved incident timeline and continue monitoring.",),
            more=False,
        )
    if (
        history is not None
        and not history.empty
        and {"id", "timestamp", "raw_status"}.issubset(history.columns)
    ):
        for _, group in history.groupby("id"):
            sequence = group.sort_values("timestamp").tail(10)["raw_status"].tolist()
            categories = [s in {"CRITICAL", "UNREACHABLE"} for s in sequence]
            changes = sum(a != b for a, b in zip(categories, categories[1:]))
            if changes >= 3:
                return result(
                    "Intermittent connectivity in recent windows",
                    "WARNING",
                    "At least three changes between severe and non-severe evidence were observed in the last ten stored windows.",
                    ("Changing connectivity, service health or threshold crossings.",),
                    ("Inspect the incident timeline and correlate with link/service logs.",),
                    ("This historical pattern does not mean currently successful checks are failing.",),
                )
    if bad:
        return result(
            "Elevated latency",
            "WARNING",
            "Services respond but exceed configured duration thresholds.",
            ("Path or service processing delays.",),
            ("Compare with endpoint-specific baselines.",),
            ("TCP/HTTPS time is not in-game ping.",),
        )
    return result(
        "Healthy monitored services",
        "HEALTHY",
        "All configured checks succeed within their thresholds.",
        actions=("Continue monitoring; these checks cover only configured services from this host.",),
        strength="strong for configured checks only",
        more=False,
    )
