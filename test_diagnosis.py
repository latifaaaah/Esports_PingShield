"""V2 scenarios migrated to the corrected explicit measurement contract."""

import pandas as pd
from diagnosis import diagnose_live
from engine import evaluate
from collector import utc_now


def frame(gateway_fail=False, external_failures=(False, False), latency=10):
    rows = []
    for index, failed in enumerate((gateway_fail, *external_failures)):
        rows.append(
            dict(
                id="HOME-ROUTER" if index == 0 else f"EXT-{index}",
                zone="Local" if index == 0 else "External",
                scope="local" if index == 0 else "external",
                provider=str(index),
                method="tcp",
                measurement_type="TCP connect",
                mode="live",
                sample_count=3,
                success_count=0 if failed else 3,
                latency_ms=None if failed else latency,
                jitter_ms=1,
                jitter_warn_ms=50,
                packet_loss_pct=None,
                failure_rate_pct=100 if failed else 0,
                errors={"timeout": 3} if failed else {},
                warn_ms=100,
                crit_ms=200,
                recover_ms=80,
                timestamp=utc_now(),
            )
        )
    return evaluate(pd.DataFrame(rows))


def test_all_healthy():
    assert diagnose_live(frame()).severity == "HEALTHY"


def test_everything_failed():
    assert diagnose_live(frame(True, (True, True))).title == "Widespread connectivity failures"


def test_external_failed():
    assert diagnose_live(frame(False, (True, True))).title == "External targets unreachable"


def test_partial_failure():
    assert diagnose_live(frame(False, (False, True))).title == "Partial external connectivity failure"


def test_gateway_port_failed():
    assert "Gateway/local service" in diagnose_live(frame(True)).title


def test_latency_warning():
    assert diagnose_live(frame(latency=150)).title == "Elevated latency"


def test_empty():
    assert diagnose_live(pd.DataFrame()).severity == "UNKNOWN"


def test_missing_columns():
    assert diagnose_live(pd.DataFrame({"id": ["a"]})).severity == "UNKNOWN"


def test_missing_gateway_does_not_block_external_observation():
    df = frame().iloc[1:]
    assert diagnose_live(df).severity == "HEALTHY"
