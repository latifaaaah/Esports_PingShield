"""UI Styling Components, Metrics Cards, Topology Grid, and Visualizations."""

from html import escape
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Icon set (inline SVG, stroke-based, currentColor -> inherits CSS color)
# Purely decorative / presentational — no data or logic lives here.
# ---------------------------------------------------------------------------
ICONS = {
    "monitor": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="18" x2="12" y2="21"/></svg>',
    "pulse": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    "alert": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    "wifi_off": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.58 9"/><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>',
    "gamepad": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="12" x2="10" y2="12"/><line x1="8" y1="10" x2="8" y2="14"/><line x1="15" y1="13" x2="15.01" y2="13"/><line x1="18" y1="11" x2="18.01" y2="11"/><rect x="2" y="6" width="20" height="12" rx="6"/></svg>',
    "camera": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>',
    "server": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>',
}

# Zone -> icon key. Zones not listed here (e.g. Live mode zones) fall back
# to the "monitor" icon.
ZONE_ICON = {
    "Stage Left": "gamepad",
    "Stage Right": "gamepad",
    "Production Booth": "camera",
    "Server Rack": "server",
}

STATUS_COLORS = {
    "CRITICAL": "#ff4d5e",
    "UNREACHABLE": "#ff4d5e",
    "WARNING": "#ffb020",
    "HEALTHY": "#12d992",
    "UNKNOWN": "#8493ad",
    "RECOVERING": "#00e5ff",
}


def apply_custom_css():
    st.markdown(
        """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

        :root {
            --bg-deep: #05070d;
            --bg-panel: #0d1526;
            --bg-panel-alt: #0a1120;
            --border: #1c2740;
            --border-soft: #16203a;
            --cyan: #00e5ff;
            --cyan-dim: rgba(0, 229, 255, 0.35);
            --blue: #2563eb;
            --green: #12d992;
            --red: #ff4d5e;
            --amber: #ffb020;
            --text-main: #e7ecf5;
            --text-dim: #8493ad;
            --text-faint: #556182;
        }

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        /* ---------- App shell ---------- */
        .stApp {
            background:
                radial-gradient(ellipse 1200px 600px at 15% -10%, rgba(0, 229, 255, 0.06), transparent 60%),
                radial-gradient(ellipse 900px 500px at 100% 10%, rgba(37, 99, 235, 0.07), transparent 55%),
                linear-gradient(180deg, #060911 0%, #05070d 100%);
            color: var(--text-main);
        }
        .block-container { padding-top: 2rem; padding-bottom: 3rem; }

        /* Faint grid texture behind everything for a "control room" feel */
        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            background-image:
                linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px);
            background-size: 42px 42px;
            pointer-events: none;
            z-index: 0;
        }

        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: var(--bg-deep); }
        ::-webkit-scrollbar-thumb { background: #22304d; border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: #2c3e63; }

        /* ---------- Sidebar ---------- */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #080c16 0%, #060910 100%);
            border-right: 1px solid var(--border-soft);
        }
        section[data-testid="stSidebar"] * { color: var(--text-main); }
        section[data-testid="stSidebar"] h1 {
            font-family: 'Rajdhani', sans-serif;
            font-weight: 700;
            font-size: 22px;
            letter-spacing: 0.5px;
            border-left: 3px solid var(--cyan);
            padding-left: 10px;
            margin-bottom: 4px;
        }
        section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] p {
            color: var(--text-dim) !important;
            font-size: 12.5px;
        }
        section[data-testid="stSidebar"] label {
            color: var(--text-faint) !important;
            font-size: 11.5px;
            font-weight: 700;
            letter-spacing: 0.8px;
            text-transform: uppercase;
        }
        section[data-testid="stSidebar"] h3 {
            font-family: 'Rajdhani', sans-serif;
            font-size: 15px;
            letter-spacing: 0.5px;
            color: var(--text-main);
            margin-top: 6px;
            padding-top: 14px;
            border-top: 1px solid var(--border-soft);
        }
        section[data-testid="stSidebar"] [data-baseweb="select"] > div {
            background: var(--bg-panel) !important;
            border-color: var(--border) !important;
            border-radius: 8px !important;
        }
        section[data-testid="stSidebar"] span[data-baseweb="tag"] {
            background: linear-gradient(135deg, #0891b2, #0e7490) !important;
            border-radius: 6px !important;
        }

        /* ---------- Headings inside main area ---------- */
        div[data-testid="stMarkdownContainer"] h3 {
            font-family: 'Rajdhani', sans-serif;
            font-weight: 700;
            font-size: 19px;
            letter-spacing: 0.4px;
            color: var(--text-main);
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 14px !important;
        }
        div[data-testid="stMarkdownContainer"] h3::before {
            content: "";
            width: 4px;
            height: 18px;
            background: linear-gradient(180deg, var(--cyan), var(--blue));
            border-radius: 3px;
            display: inline-block;
            box-shadow: 0 0 8px var(--cyan-dim);
        }

        /* ---------- Header banner ---------- */
        .main-header {
            position: relative;
            background: linear-gradient(120deg, #0b1220 0%, #0f1b30 60%, #0b1220 100%);
            border: 1px solid var(--border);
            border-left: 4px solid var(--cyan);
            padding: 22px 26px;
            border-radius: 12px;
            margin-bottom: 26px;
            overflow: hidden;
            box-shadow: 0 10px 30px -12px rgba(0,0,0,0.6);
        }
        .main-header::after {
            content: "";
            position: absolute;
            top: 0; left: -30%;
            width: 30%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0,229,255,0.06), transparent);
            animation: sweep 6s ease-in-out infinite;
        }
        @keyframes sweep {
            0% { left: -30%; }
            50% { left: 110%; }
            100% { left: 110%; }
        }
        .header-row { display: flex; justify-content: space-between; align-items: center; position: relative; z-index: 1; }
        .header-title {
            font-family: 'Rajdhani', sans-serif;
            font-weight: 700;
            font-size: 27px;
            letter-spacing: 0.3px;
            margin: 0;
            color: #f5f8ff;
        }
        .header-subtitle {
            margin: 4px 0 0 0;
            color: var(--text-dim);
            font-size: 13px;
            letter-spacing: 0.2px;
        }
        .live-badge {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            background: rgba(0, 229, 255, 0.1);
            border: 1px solid var(--cyan-dim);
            color: var(--cyan);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
            white-space: nowrap;
        }
        .live-dot {
            width: 7px; height: 7px;
            border-radius: 50%;
            background: var(--cyan);
            box-shadow: 0 0 8px 2px var(--cyan);
            animation: livepulse 1.4s ease-in-out infinite;
        }
        @keyframes livepulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.45; transform: scale(0.75); }
        }

        /* ---------- KPI cards ---------- */
        .metric-card {
            position: relative;
            background: linear-gradient(160deg, var(--bg-panel) 0%, var(--bg-panel-alt) 100%);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 18px;
            box-shadow: 0 8px 20px -10px rgba(0,0,0,0.55);
            transition: transform .2s ease, border-color .2s ease;
            overflow: hidden;
        }
        .metric-card:hover { transform: translateY(-2px); border-color: #29344f; }
        .metric-card::before {
            content: "";
            position: absolute; top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--cyan), transparent);
        }
        .metric-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
        .metric-label {
            font-size: 11px; color: var(--text-faint); font-weight: 700;
            letter-spacing: 1px; text-transform: uppercase;
        }
        .metric-icon {
            width: 26px; height: 26px;
            display: flex; align-items: center; justify-content: center;
            border-radius: 7px;
            background: rgba(255,255,255,0.04);
            color: var(--text-dim);
        }
        .metric-icon svg { width: 14px; height: 14px; }
        .metric-value {
            font-family: 'Rajdhani', sans-serif;
            font-size: 30px; font-weight: 700; line-height: 1;
        }
        .metric-value .unit { font-size: 14px; font-weight: 600; color: var(--text-dim); margin-left: 3px; }
        .metric-green { color: var(--green); }
        .metric-red { color: var(--red); }
        .metric-card:has(.metric-red) .metric-icon { color: var(--red); background: rgba(255,77,94,0.1); }
        .metric-card:has(.metric-green) .metric-icon { color: var(--green); background: rgba(18,217,146,0.1); }

        /* ---------- Arena / stage topology ---------- */
        .arena-wrap {
            background: radial-gradient(ellipse 700px 260px at 50% 0%, rgba(0,229,255,0.07), transparent 70%), var(--bg-panel-alt);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 22px 20px 18px;
            margin-bottom: 4px;
        }
        .arena-screen {
            width: 78%;
            height: 6px;
            margin: 0 auto 6px;
            border-radius: 4px;
            background: linear-gradient(90deg, transparent, var(--cyan), transparent);
            box-shadow: 0 0 18px 2px var(--cyan-dim);
        }
        .arena-screen-label {
            text-align: center;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            letter-spacing: 4px;
            color: var(--text-faint);
            margin-bottom: 22px;
            text-transform: uppercase;
        }
        .arena-floor {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            margin-bottom: 14px;
        }
        .zone-card {
            background: linear-gradient(160deg, #0e1830 0%, #0a1122 100%);
            border: 1px solid var(--border);
            border-radius: 11px;
            padding: 14px 16px;
            transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
        }
        .zone-card:hover { transform: translateY(-2px); }
        .zone-card.healthy { box-shadow: 0 8px 22px -12px rgba(18,217,146,0.25); }
        .zone-card.critical {
            border-color: rgba(255,77,94,0.55);
            box-shadow: 0 0 0 1px rgba(255,77,94,0.15), 0 10px 24px -10px rgba(255,77,94,0.35);
        }
        .zone-card.warning { border-color: rgba(255,176,32,0.5); }
        .zone-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
        .zone-name-wrap { display: flex; align-items: center; gap: 9px; }
        .zone-icon {
            width: 28px; height: 28px; border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            background: rgba(0,229,255,0.08); color: var(--cyan);
            flex-shrink: 0;
        }
        .zone-card.critical .zone-icon { background: rgba(255,77,94,0.12); color: var(--red); }
        .zone-card.warning .zone-icon { background: rgba(255,176,32,0.12); color: var(--amber); }
        .zone-icon svg { width: 15px; height: 15px; }
        .zone-name {
            font-family: 'Rajdhani', sans-serif; font-weight: 700;
            font-size: 15.5px; color: #f1f5fb; letter-spacing: 0.3px;
        }
        .status-pill {
            font-size: 10px; font-weight: 800; letter-spacing: 1px;
            padding: 3px 10px; border-radius: 20px; white-space: nowrap;
        }
        .status-pill.healthy { background: rgba(18,217,146,0.12); color: var(--green); border: 1px solid rgba(18,217,146,0.4); }
        .status-pill.warning { background: rgba(255,176,32,0.14); color: var(--amber); border: 1px solid rgba(255,176,32,0.5); }
        .status-pill.critical {
            background: rgba(255,77,94,0.14); color: var(--red); border: 1px solid rgba(255,77,94,0.5);
            animation: pillpulse 1.3s ease-in-out infinite;
        }
        @keyframes pillpulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.55; } }
        .device-row { display: flex; flex-wrap: wrap; gap: 6px; }
        .device-chip {
            display: inline-flex; align-items: center; gap: 6px;
            background: #070c17; border: 1px solid var(--border-soft);
            padding: 4px 9px 4px 7px; border-radius: 6px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10.5px; color: var(--text-dim);
        }
        .device-chip .dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
        .dot.healthy { background: var(--green); box-shadow: 0 0 5px var(--green); }
        .dot.warning { background: var(--amber); box-shadow: 0 0 5px var(--amber); }
        .dot.critical { background: var(--red); box-shadow: 0 0 5px var(--red); animation: pillpulse 1s infinite; }

        /* ---------- Plotly chart container ---------- */
        div[data-testid="stPlotlyChart"] {
            background: var(--bg-panel-alt);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 10px 6px 2px;
        }

        /* ---------- Playbook card ---------- */
        .playbook-card {
            background: linear-gradient(160deg, rgba(255,77,94,0.07), rgba(255,77,94,0.02));
            border: 1px solid rgba(255,77,94,0.4);
            border-radius: 14px;
            padding: 22px 24px;
            margin-top: 22px;
            position: relative;
        }
        .playbook-title {
            display: flex; align-items: center; gap: 10px;
            font-family: 'Rajdhani', sans-serif;
            color: var(--red); font-weight: 700; font-size: 19px;
            margin: 0 0 14px 0;
        }
        .playbook-title .metric-icon { background: rgba(255,77,94,0.14); color: var(--red); }
        .playbook-card p { color: var(--text-main); font-size: 14px; line-height: 1.7; }
        .playbook-card strong { color: #f5f8ff; }
        .playbook-card ol { color: var(--text-main); font-size: 14px; line-height: 1.9; padding-left: 20px; }

        /* ---------- Native alert / dataframe polish ---------- */
        div[data-testid="stAlert"] {
            border-radius: 12px !important;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--border) !important;
            border-radius: 12px !important;
            overflow: hidden;
        }
        .status-pill.unknown { color: #8493ad; border: 1px solid #8493ad; }
        .status-pill.recovering { color: #00e5ff; border: 1px solid #00e5ff; }
        .status-pill.unreachable { color: #ff4d5e; border: 1px solid #ff4d5e; }
        .dot.unknown { background: #8493ad; }
        .dot.recovering { background: #00e5ff; }
        .dot.unreachable { background: #ff4d5e; }
        @media (max-width: 720px) { .header-row { flex-wrap: wrap; gap: 12px; } .arena-floor { grid-template-columns: 1fr; } }
    </style>
    """,
        unsafe_allow_html=True,
    )


def _metric_card(label, value_html, icon_key):
    # NOTE: rendered as a single line on purpose. Streamlit's markdown parser
    # treats a blank line inside a raw <div> block as the end of the HTML
    # block, after which the remaining markup is printed as literal text
    # instead of being rendered. Keeping this compact avoids that entirely.
    html = (
        '<div class="metric-card">'
        '<div class="metric-top">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-icon">{ICONS[icon_key]}</div>'
        "</div>"
        f'<div class="metric-value">{value_html}</div>'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_kpi_cards(df, critical_nodes):
    simulated = not df.empty and (df["mode"] == "simulation").all()
    latency_rows = df if simulated else df[df["method"] == "tcp"]
    valid = latency_rows[latency_rows["latency_ms"].notna()]
    average = (
        (valid["latency_ms"] * valid["success_count"]).sum() / valid["success_count"].sum()
        if not valid.empty and valid["success_count"].sum()
        else None
    )
    avg_display = f"{average:.1f}" if pd.notna(average) else "N/A"
    failure = df["packet_loss_pct"].max() if simulated else df["failure_rate_pct"].max()
    failure_display = f"{failure:.1f}" if pd.notna(failure) else "N/A"
    cols = st.columns(4)
    with cols[0]:
        _metric_card("Configured Endpoints", f'<span class="metric-green">{len(df)}</span>', "monitor")
    with cols[1]:
        _metric_card(
            "Simulated RTT mean" if simulated else "Mean TCP connect time",
            f'<span>{avg_display}<span class="unit">ms</span></span>',
            "pulse",
        )
    with cols[2]:
        color = "metric-red" if critical_nodes else "metric-green"
        _metric_card("Severe Endpoint States", f'<span class="{color}">{critical_nodes}</span>', "alert")
    with cols[3]:
        _metric_card(
            "Simulated packet loss" if simulated else "Max check failure rate",
            f'<span>{failure_display}<span class="unit">%</span></span>',
            "wifi_off",
        )


def render_topology_grid(df):
    st.subheader("Endpoint Health • Zone Overview")
    st.caption("Configured endpoint grouping, not an automatically discovered network map.")

    # NOTE: every fragment below is assembled with zero newlines / blank
    # lines. Streamlit's markdown parser ends a raw <div> HTML block at the
    # first blank line it sees, after which everything else in the string
    # gets printed as literal text instead of being rendered as HTML.
    cards_html = ""
    for zone in df["zone"].unique():
        zone_df = df[df["zone"] == zone]
        statuses = [s.lower() for s in zone_df["status"]]

        zone_status = next(
            (
                status
                for status in ("unreachable", "critical", "unknown", "recovering", "warning")
                if status in statuses
            ),
            "healthy",
        )

        chips = "".join(
            f'<span class="device-chip"><span class="dot {row.status.lower()}"></span>{escape(str(row.id))}</span>'
            for row in zone_df.itertuples()
        )
        icon = ICONS[ZONE_ICON.get(zone, "monitor")]

        cards_html += (
            f'<div class="zone-card {zone_status}">'
            '<div class="zone-head">'
            '<div class="zone-name-wrap">'
            f'<div class="zone-icon">{icon}</div>'
            f'<div class="zone-name">{escape(str(zone))}</div>'
            "</div>"
            f'<div class="status-pill {zone_status}">{zone_status.upper()}</div>'
            "</div>"
            f'<div class="device-row">{chips}</div>'
            "</div>"
        )

    arena_html = (
        '<div class="arena-wrap">'
        '<div class="arena-screen"></div>'
        '<div class="arena-screen-label">Configured Service Groups</div>'
        f'<div class="arena-floor">{cards_html}</div>'
        "</div>"
    )
    st.markdown(arena_html, unsafe_allow_html=True)


def render_latency_chart(df):
    st.subheader("Network Performance")
    if df.empty:
        st.info("No measurements. Select zones or request a live window.")
        return
    methods = df["measurement_type"].dropna().unique().tolist()
    if not methods:
        st.info("No successful latency measurements available.")
        return
    chosen = st.selectbox("Measurement method", methods, key="chart_method")
    df = df[df["measurement_type"] == chosen].copy()
    df["latency_ms"] = pd.to_numeric(df["latency_ms"], errors="coerce")
    if df["latency_ms"].notna().sum() == 0:
        st.info("No successful latency measurements available for this method.")
        return
    st.caption("Only successful samples contribute to durations. Missing bars mean unavailable timing.")
    colors = [STATUS_COLORS.get(s, "#8493ad") for s in df["status"]]

    fig = go.Figure(
        go.Bar(
            x=df["id"],
            y=df["latency_ms"],
            marker=dict(
                color=colors,
                line=dict(color="rgba(255,255,255,0.12)", width=1),
            ),
            text=df["latency_ms"].round(1),
            textposition="auto",
            textfont=dict(family="JetBrains Mono, monospace", size=12, color="#0b0f1a"),
            hovertemplate="<b>%{x}</b><br>Latency: %{y} ms<extra></extra>",
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#8493ad", family="Inter, sans-serif", size=12),
        height=320,
        yaxis_title=f"{chosen} (ms)",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, linecolor="#1c2740", tickfont=dict(color="#8493ad")),
        yaxis=dict(gridcolor="#151f36", zerolinecolor="#1c2740", tickfont=dict(color="#8493ad")),
        bargap=0.35,
        hoverlabel=dict(bgcolor="#0d1526", font_family="JetBrains Mono, monospace", bordercolor="#1c2740"),
    )

    # Threshold lines only when all endpoints share one threshold (Simulation).
    # In Live mode each target has its own threshold, so lines would mislead.
    if not df.empty and df["crit_ms"].nunique() == 1:
        fig.add_hline(
            y=df["warn_ms"].iloc[0],
            line_dash="dot",
            line_color="#ffb020",
            annotation_text="Warning",
            annotation_font_color="#ffb020",
        )
        fig.add_hline(
            y=df["crit_ms"].iloc[0],
            line_dash="dot",
            line_color="#ff4d5e",
            annotation_text="Critical",
            annotation_font_color="#ff4d5e",
        )

    st.plotly_chart(fig, width="stretch")
