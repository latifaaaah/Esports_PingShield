"""Configuration constants and disaster scenarios for Esports-PingShield."""

DISASTER_SCENARIOS = {
    "NORMAL": "Normal Operations (All Green)",
    "SERVER_DDOS": "Scenario A: DDoS on Primary Game Server",
    "STAGE_SWITCH_FAIL": "Scenario B: Stage Right Switch Failure",
    "STREAM_PACKET_LOSS": "Scenario C: Broadcast Stream Packet Loss & Jitter",
    "TOTAL_CONGESTION": "Scenario D: Total Stage Congestion",
}

BASE_DEVICES = [
    {"id": "PC-STAGE-L1", "zone": "Stage Left", "base_ping": 2.1, "base_jitter": 0.3, "base_loss": 0.0},
    {"id": "PC-STAGE-L2", "zone": "Stage Left", "base_ping": 2.3, "base_jitter": 0.4, "base_loss": 0.0},
    {"id": "PC-STAGE-R1", "zone": "Stage Right", "base_ping": 2.2, "base_jitter": 0.2, "base_loss": 0.0},
    {"id": "PC-STAGE-R2", "zone": "Stage Right", "base_ping": 2.4, "base_jitter": 0.5, "base_loss": 0.0},
    {
        "id": "OBS-BROADCAST-01",
        "zone": "Production Booth",
        "base_ping": 3.1,
        "base_jitter": 0.6,
        "base_loss": 0.0,
    },
    {
        "id": "CASTER-DESK-PC",
        "zone": "Production Booth",
        "base_ping": 2.8,
        "base_jitter": 0.4,
        "base_loss": 0.0,
    },
    {
        "id": "GAME-SERVER-PRIMARY",
        "zone": "Server Rack",
        "base_ping": 1.2,
        "base_jitter": 0.1,
        "base_loss": 0.0,
    },
    {
        "id": "GAME-SERVER-BACKUP",
        "zone": "Server Rack",
        "base_ping": 1.3,
        "base_jitter": 0.1,
        "base_loss": 0.0,
    },
]

# ---- Thresholds: single source of truth for the whole project ----
WARNING_MS = 5.0  # above this latency (ms) = warning
CRITICAL_MS = 30.0  # above this latency (ms) = critical incident
LOSS_CRITICAL = 5.0  # above this packet loss (%) = critical incident


def get_scenario_key(label):
    """Convert the label shown in the sidebar into its scenario key."""
    for key, value in DISASTER_SCENARIOS.items():
        if value == label:
            return key
    return "NORMAL"


# ---- Per-scenario playbooks (simulation data) ----
SCENARIO_PLAYBOOKS = {
    "NORMAL": None,
    "SERVER_DDOS": {
        "sop": "SOP-01",
        "cause": "Abnormal inbound traffic volume on the primary game server.",
        "diagnosis": [
            "Check traffic graphs on the firewall/edge router for a sudden spike.",
            "Identify top source IPs and ports hitting the server.",
        ],
        "actions": [
            "Fail over players to GAME-SERVER-BACKUP.",
            "Apply rate limiting / ACL on the edge and contact the ISP if needed.",
        ],
    },
    "STAGE_SWITCH_FAIL": {
        "sop": "SOP-02",
        "cause": "Stage Right access switch down or its uplink degraded.",
        "diagnosis": [
            "Check switch power and port LEDs for link status.",
            "Review uplink port errors and look for a possible loop.",
        ],
        "actions": [
            "Move the uplink or affected PCs to a spare switch.",
            "Replace the faulty cable/SFP and verify link stability.",
        ],
    },
    "STREAM_PACKET_LOSS": {
        "sop": "SOP-03",
        "cause": "Uplink saturation or loss affecting the broadcast stream.",
        "diagnosis": [
            "Check dropped frames and bitrate in OBS.",
            "Check uplink utilization and whether the stream shares a VLAN with other traffic.",
        ],
        "actions": [
            "Apply QoS to prioritize stream traffic.",
            "Lower stream bitrate or switch to the backup encoder/uplink.",
        ],
    },
    "TOTAL_CONGESTION": {
        "sop": "SOP-04",
        "cause": "Network-wide congestion, possibly a broadcast storm or bandwidth hog.",
        "diagnosis": [
            "Check core switch for a broadcast storm or spanning-tree changes.",
            "Find the top bandwidth consumers (updates, downloads, streaming).",
        ],
        "actions": [
            "Isolate zones one by one to locate the source.",
            "Block or throttle the offending traffic and restore zones gradually.",
        ],
    },
}
