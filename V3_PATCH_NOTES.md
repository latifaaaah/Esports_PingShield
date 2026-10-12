# V3 targeted recovery / outage-chart patch

- Chart: coerce latency to numeric and show an unavailable-data notice when all samples failed, rather than calling `.round()` on an object series. No failed sample is plotted as zero.
- Default HTTPS recovery threshold: raised from 400 ms to 500 ms (the existing warning threshold). The former threshold could trap healthy HTTPS windows at 400–500 ms in RECOVERING indefinitely. This does **not** automatically close an incident for genuinely WARNING or CRITICAL measurements; two consecutive raw-HEALTHY windows at or below 500 ms are still required.
- State: numeric coercion of recovery latency prevents malformed values from crashing the state transition.

**Important:** An HTTPS endpoint with consistent durations above 500 ms, high variation, or intermittent failures can still legitimately remain OPEN/RECOVERING. Review its recorded evidence and calibrate endpoint thresholds using an authorized baseline before raising them further. Existing stored incident states and history are preserved.

**Validation:** Python syntax compilation and isolated state-transition checks only; complete Streamlit UI tests and real network retesting remain necessary.
