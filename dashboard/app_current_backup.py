# dashboard/app.py
import base64
import math
import os
import random
import re
import sys
from dataclasses import asdict

import pandas as pd
import requests
import streamlit as st

try:
    import plotly.graph_objects as go

    _HAS_PLOTLY = True
except Exception:
    _HAS_PLOTLY = False

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT in sys.path:
    sys.path.remove(_REPO_ROOT)
sys.path.insert(0, _REPO_ROOT)

API_BASE = os.getenv("LUMINA_API_BASE", "http://localhost:8000")
_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "lumina-logo-transparent-clean.png")

st.set_page_config(
    page_title="LUMINA - Digital Arrest Protection",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Palette derived from dashboard/assets/lumina-logo.png
LEVEL_COLORS = {
    "critical": "#E01C2B",
    "high": "#D9A441",
    "medium": "#B08948",
    "low": "#6FA877",
}

LEVEL_SUMMARY = {
    "critical": ("Digital arrest pattern detected", "Immediate family intervention recommended"),
    "high": ("Escalating digital-arrest indicators", "Alert trusted contacts and monitor closely"),
    "medium": ("Suspicious call pattern", "Verify caller identity - keep monitoring"),
    "low": ("Normal call behavior", "No action needed"),
}

CHART_COLORS = {
    "fused": "#E01C2B",
    "ml": "#A4A4A4",
    "rules": "#6F6F6F",
    "grid": "rgba(255,255,255,0.07)",
}

CALL_KEYS = [
    "call_duration_min",
    "is_unknown_number",
    "is_video_call",
    "hour_of_day",
    "caller_call_history",
    "outgoing_activity_ratio",
]

TELEMETRY_KEYS = [
    "screen_time_on_call_percent",
    "num_app_switches",
    "num_home_presses",
    "has_sms_activity",
    "has_social_app_activity",
    "location_change",
    "screen_brightness",
    "screen_on_continuous_hours",
    "persistence_hours",
]

TELEMETRY_LABELS = {
    "screen_time_on_call_percent": "Screen time on call",
    "num_app_switches": "App switches",
    "num_home_presses": "Home-screen presses",
    "has_sms_activity": "SMS activity",
    "has_social_app_activity": "Social-app activity",
    "location_change": "Location change",
    "screen_brightness": "Screen brightness",
    "screen_on_continuous_hours": "Screen-on continuous hours",
    "persistence_hours": "Persistence hours",
}

DIGITAL_ARREST_SCENARIO = [
    {
        "t": 2,
        "label": "Call connects - unknown number",
        "signals": {
            "call_duration_min": 2, "is_unknown_number": 1, "is_video_call": 0,
            "hour_of_day": 10, "caller_call_history": 0, "outgoing_activity_ratio": 0.6,
            "screen_time_on_call_percent": 30, "num_app_switches": 5, "num_home_presses": 4,
            "has_sms_activity": 1, "has_social_app_activity": 1, "location_change": 120,
            "screen_brightness": 35, "screen_on_continuous_hours": 0, "persistence_hours": 0,
        },
        "note": "Unknown number connects. Victim still uses the phone normally.",
    },
    {
        "t": 20,
        "label": "Caller switches to video - pressure builds",
        "signals": {
            "call_duration_min": 25, "is_unknown_number": 1, "is_video_call": 1,
            "hour_of_day": 10, "caller_call_history": 0, "outgoing_activity_ratio": 0.45,
            "screen_time_on_call_percent": 55, "num_app_switches": 3, "num_home_presses": 2,
            "has_sms_activity": 1, "has_social_app_activity": 1, "location_change": 60,
            "screen_brightness": 50, "screen_on_continuous_hours": 0, "persistence_hours": 0,
        },
        "note": "Victim is moved to a video call; screen time rises, app use drops.",
    },
    {
        "t": 50,
        "label": "Authority claim + secrecy demand",
        "signals": {
            "call_duration_min": 55, "is_unknown_number": 1, "is_video_call": 1,
            "hour_of_day": 10, "caller_call_history": 0, "outgoing_activity_ratio": 0.25,
            "screen_time_on_call_percent": 70, "num_app_switches": 1, "num_home_presses": 1,
            "has_sms_activity": 0, "has_social_app_activity": 0, "location_change": 25,
            "screen_brightness": 70, "screen_on_continuous_hours": 0, "persistence_hours": 0,
        },
        "note": "Caller impersonates authority. Victim stops messaging and social apps.",
    },
    {
        "t": 90,
        "label": "Isolation deepens",
        "signals": {
            "call_duration_min": 95, "is_unknown_number": 1, "is_video_call": 1,
            "hour_of_day": 10, "caller_call_history": 0, "outgoing_activity_ratio": 0.1,
            "screen_time_on_call_percent": 90, "num_app_switches": 0, "num_home_presses": 0,
            "has_sms_activity": 0, "has_social_app_activity": 0, "location_change": 10,
            "screen_brightness": 90, "screen_on_continuous_hours": 2, "persistence_hours": 1,
        },
        "note": "No app switching, no movement - the victim is anchored to the call.",
    },
    {
        "t": 150,
        "label": "Escalated threat - digital arrest",
        "signals": {
            "call_duration_min": 165, "is_unknown_number": 1, "is_video_call": 1,
            "hour_of_day": 10, "caller_call_history": 0, "outgoing_activity_ratio": 0.03,
            "screen_time_on_call_percent": 98, "num_app_switches": 0, "num_home_presses": 0,
            "has_sms_activity": 0, "has_social_app_activity": 0, "location_change": 2,
            "screen_brightness": 100, "screen_on_continuous_hours": 5, "persistence_hours": 3,
        },
        "note": "Every digital-arrest indicator is now active - maximum escalation.",
    },
]

NORMAL_CALL_SCENARIO = [
    {
        "t": 0,
        "label": "Call connects - known family number",
        "signals": {
            "call_duration_min": 2, "is_unknown_number": 0, "is_video_call": 0,
            "hour_of_day": 14, "caller_call_history": 15, "outgoing_activity_ratio": 0.85,
            "screen_time_on_call_percent": 20, "num_app_switches": 15, "num_home_presses": 12,
            "has_sms_activity": 1, "has_social_app_activity": 1, "location_change": 400,
            "screen_brightness": 30, "screen_on_continuous_hours": 0, "persistence_hours": 0,
        },
        "note": "Known number, normal screen use, phone used normally.",
    },
    {
        "t": 10,
        "label": "Catching up with family",
        "signals": {
            "call_duration_min": 12, "is_unknown_number": 0, "is_video_call": 0,
            "hour_of_day": 14, "caller_call_history": 15, "outgoing_activity_ratio": 0.8,
            "screen_time_on_call_percent": 30, "num_app_switches": 18, "num_home_presses": 14,
            "has_sms_activity": 1, "has_social_app_activity": 1, "location_change": 300,
            "screen_brightness": 35, "screen_on_continuous_hours": 0, "persistence_hours": 0,
        },
        "note": "Normal app and message activity continues.",
    },
    {
        "t": 20,
        "label": "Conversation continues (brief video)",
        "signals": {
            "call_duration_min": 25, "is_unknown_number": 0, "is_video_call": 1,
            "hour_of_day": 14, "caller_call_history": 15, "outgoing_activity_ratio": 0.75,
            "screen_time_on_call_percent": 40, "num_app_switches": 14, "num_home_presses": 10,
            "has_sms_activity": 1, "has_social_app_activity": 1, "location_change": 250,
            "screen_brightness": 40, "screen_on_continuous_hours": 0, "persistence_hours": 0,
        },
        "note": "Even with video, normal outgoing activity keeps risk low.",
    },
    {
        "t": 35,
        "label": "Wrapping up the call",
        "signals": {
            "call_duration_min": 38, "is_unknown_number": 0, "is_video_call": 0,
            "hour_of_day": 14, "caller_call_history": 15, "outgoing_activity_ratio": 0.7,
            "screen_time_on_call_percent": 35, "num_app_switches": 16, "num_home_presses": 11,
            "has_sms_activity": 1, "has_social_app_activity": 1, "location_change": 220,
            "screen_brightness": 35, "screen_on_continuous_hours": 0, "persistence_hours": 0,
        },
        "note": "Behavior remains normal throughout.",
    },
    {
        "t": 45,
        "label": "Call ends naturally",
        "signals": {
            "call_duration_min": 45, "is_unknown_number": 0, "is_video_call": 0,
            "hour_of_day": 14, "caller_call_history": 15, "outgoing_activity_ratio": 0.65,
            "screen_time_on_call_percent": 30, "num_app_switches": 12, "num_home_presses": 9,
            "has_sms_activity": 1, "has_social_app_activity": 1, "location_change": 200,
            "screen_brightness": 30, "screen_on_continuous_hours": 0, "persistence_hours": 0,
        },
        "note": "No isolation signals - low risk maintained.",
    },
]

INTERVENTIONS = {
    "critical": {
        "title": "[CRITICAL] IMMEDIATE FAMILY INTERVENTION REQUIRED",
        "steps": [
            "Call the person on an ALTERNATIVE number right now (the scammer may still be on the active line).",
            "If possible, visit their location in person.",
            "Do NOT let them share OTPs, UPI PINs or bank details with anyone on the call.",
            "If the scam is confirmed, dial 1930 (National Cyber Helpline) and file a report at cybercrime.gov.in.",
        ],
    },
    "high": {
        "title": "[HIGH] ALERT TRUSTED CONTACTS AND MONITOR CLOSELY",
        "steps": [
            "Alert a trusted family member or friend to monitor the situation.",
            "Ask the person to verify the caller's identity through an official channel.",
            "If any money or OTP demand is made, hang up and dial 1930.",
        ],
    },
    "medium": {
        "title": "[MEDIUM] KEEP MONITORING - VERIFY CALLER IDENTITY",
        "steps": [
            "Continue monitoring the call pattern for escalation.",
            "Verify the caller's identity independently (do not call back on the same number).",
            "Remind the person: no government agency arrests over video call or demands money by phone.",
        ],
    },
    "low": {
        "title": "[LOW] NO ACTION NEEDED - NORMAL BEHAVIOR",
        "steps": [
            "This call shows no significant scam indicators.",
            "Continue normal monitoring.",
            "Reminder: digital arrest has no legal standing - no agency arrests over video call.",
        ],
    },
}


@st.cache_data(ttl=10, show_spinner=False)
def _health_status() -> dict:
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        response.raise_for_status()
        data = response.json()
        return {"api": "online", "model_status": data.get("model_status", "unknown")}
    except Exception:
        return {"api": "offline", "model_status": "unknown"}


# ============================= LOGO ASSETS =============================
@st.cache_data(show_spinner=False)
def _logo_b64() -> str:
    """Exact official logo bytes as a data-URI-ready base64 string (never altered)."""
    with open(_LOGO_PATH, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


@st.cache_data(show_spinner=False)
def _logo_watermark_b64() -> str:
    """The official logo for subtle dark-background watermarks.

    The source PNG is already transparent (RGBA), so the exact official bytes
    are reused as-is - no runtime processing, the artwork file is never touched.
    """
    return _logo_b64()


def _logo_data_uri() -> str:
    return f"data:image/png;base64,{_logo_b64()}"


def _logo_watermark_uri() -> str:
    return f"data:image/png;base64,{_logo_watermark_b64()}"


def _logo_img(width: int = 210, radius: int = 0) -> str:
    uri = _logo_data_uri()
    return (
        f'<img class="logo-img" src="{uri}" '
        f'width="{width}" '
        f'alt="LUMINA logo" '
        f'style="border-radius:{radius}px;"/>'
    )


def _corners() -> str:
    """Decorative HUD corner brackets used on hero panels."""
    return '<div class="corners"><i></i><i></i><i></i><i></i></div>'


# ============================= BRAND MOTIFS =============================
_PATHS = {
    "phone": '<path d="M7 3h3.2l1.8 4.2-2.3 1.5a11.4 11.4 0 0 0 4.9 4.9l1.5-2.3 4.2 1.8V16a2 2 0 0 1-2.2 2A16.4 16.4 0 0 1 5 7.2 2 2 0 0 1 7 3z"/>',
    "magnifier": '<circle cx="10.8" cy="10.8" r="6.4"/><path d="M15.4 15.4 21 21"/>',
    "shield": '<path d="M12 2.6 20 5.4v6.1c0 4.9-3.3 8.6-8 9.9-4.7-1.3-8-5-8-9.9V5.4z"/><path d="m8.8 12 2.2 2.2 4.2-4.4"/>',
    "warning": '<path d="M12 3.6 21.4 20H2.6z"/><path d="M12 10v4.4"/><circle cx="12" cy="17.4" r=".3" fill="currentColor"/>',
    "handcuffs": '<circle cx="6.5" cy="6" r="2.8"/><circle cx="17.5" cy="6" r="2.8"/><path d="M6.5 8.8v2M17.5 8.8v2M6.5 10.8h11"/><path d="M8.6 10.8v5.2a3.4 3.4 0 0 0 6.8 0v-5.2"/>',
    "siren": '<path d="M12 3.2a7.2 7.2 0 0 0-7.2 7.2v5l-1.6 2.6h17.6L19.2 15.4v-5A7.2 7.2 0 0 0 12 3.2z"/><path d="M10 19.6a2 2 0 0 0 4 0"/>',
    "lock": '<rect x="6.6" y="11" width="10.8" height="9" rx="1.4"/><path d="M9 11V7.8a3 3 0 0 1 6 0V11"/><circle cx="12" cy="15.2" r="1.1"/>',
}


def _icon(name: str, size: int = 18) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round">{_PATHS.get(name, _PATHS["warning"])}</svg>'
    )


def _seal_svg(size: int = 240) -> str:
    motifs = [
        (120, 26, "phone"),
        (196, 68, "magnifier"),
        (222, 120, "warning"),
        (120, 214, "handcuffs"),
        (18, 120, "lock"),
        (58, 194, "shield"),
    ]
    parts = "".join(
        f'<g transform="translate({x},{y}) translate(-12,-12)" opacity=".9">{_PATHS[name]}</g>'
        for x, y, name in motifs
    )
    parts += (
        '<g transform="translate(120,120) translate(-12,-12)" opacity=".95">'
        '<circle cx="12" cy="12" r="9" opacity=".25"/>'
        '<circle cx="12" cy="12" r="4.5" fill="currentColor" stroke="none"/>'
        "</g>"
    )
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 240 240" fill="none" stroke="currentColor">
        <circle cx="120" cy="120" r="112" stroke-width="1" opacity=".5"/>
        <circle cx="120" cy="120" r="86" stroke-width="1" opacity=".3"/>
        {parts}
    </svg>
    """


def _circuit_svg() -> str:
    return """
    <svg width="132" height="16" viewBox="0 0 132 16" fill="none" stroke="currentColor">
        <path d="M2 8h26M28 8h8l8-6h12M56 8l8 6h12M76 8h20M96 8h8l6-6h10M120 8h10"
              stroke-width="1" opacity=".8"/>
        <circle cx="2" cy="8" r="1.6" fill="currentColor" stroke="none" opacity=".9"/>
        <circle cx="28" cy="8" r="1.6" fill="currentColor" stroke="none" opacity=".9"/>
        <circle cx="56" cy="8" r="1.6" fill="currentColor" stroke="none" opacity=".9"/>
        <circle cx="76" cy="8" r="1.6" fill="currentColor" stroke="none" opacity=".9"/>
        <circle cx="96" cy="8" r="1.6" fill="currentColor" stroke="none" opacity=".9"/>
        <circle cx="120" cy="8" r="2" fill="currentColor" stroke="none" opacity=".9"/>
    </svg>
    """


# ============================= THEME / CSS =============================
_CSS = """
:root {
    --lumina-red: #E01C2B;
    --lumina-red-soft: rgba(224,28,43,.12);
    --lumina-red-line: rgba(224,28,43,.4);
    --lumina-bg: #050404;
    --lumina-panel: #0E0D0D;
    --lumina-card: #141313;
    --lumina-card2: #1A1818;
    --lumina-border: #262424;
    --lumina-border2: #3A3737;
    --lumina-text: #FCFCFC;
    --lumina-muted: #8A8A8A;
    --lumina-muted2: #6F6F6F;
    --lumina-amber: #D9A441;
    --lumina-green: #6FA877;
}

html, body, [data-testid="stAppViewContainer"] {
    font-family: "Inter", -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(1100px 480px at 15% -10%, rgba(224,28,43,.08), transparent 60%),
        radial-gradient(900px 420px at 92% -4%, rgba(224,28,43,.05), transparent 60%),
        linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px),
        var(--lumina-bg);
    background-size: auto, auto, 44px 44px, 44px 44px, auto;
    color: var(--lumina-text);
}
[data-testid="stHeader"] { background: transparent; }
#MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none; }
[data-testid="stMainBlockContainer"] { padding-top: 1.1rem; max-width: 1480px; }
a { color: var(--lumina-red); }
::selection { background: rgba(224,28,43,.3); }
[data-testid="stCaptionContainer"] { color: var(--lumina-muted); font-size: .76rem; line-height: 1.55; }
[data-testid="stCaptionContainer"] strong { color: var(--lumina-text); }
[data-testid="stDivider"] { border-color: var(--lumina-border); }

@keyframes luminaFade {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: none; }
}
@keyframes luminaPulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(224,28,43,0); }
    50% { box-shadow: 0 0 0 7px rgba(224,28,43,.09); }
}

/* ---------- logo ---------- */
.logo-img {
    display: block;
    width: 100%;
    max-width: 210px;
    height: auto;
    object-fit: contain;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

.logo-tile {
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent !important;
    border: none !important;
    border-radius: 0;
    padding: 0;
    margin: 0;
    box-shadow: none !important;
    line-height: 0;
    flex: 0 0 auto;
}

.logo-tile img {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* ---------- hud corners ---------- */
.corners { position: absolute; inset: 12px; pointer-events: none; z-index: 2; }
.corners i { position: absolute; width: 13px; height: 13px; border: 2px solid rgba(224,28,43,.5); }
.corners i:nth-child(1) { top: 0; left: 0; border-right: none; border-bottom: none; border-top-left-radius: 4px; }
.corners i:nth-child(2) { top: 0; right: 0; border-left: none; border-bottom: none; border-top-right-radius: 4px; }
.corners i:nth-child(3) { bottom: 0; left: 0; border-right: none; border-top: none; border-bottom-left-radius: 4px; }
.corners i:nth-child(4) { bottom: 0; right: 0; border-left: none; border-top: none; border-bottom-right-radius: 4px; }

/* ---------- hero ---------- */
.lumina-hero {
    position: relative; overflow: hidden;
    background:
        linear-gradient(rgba(255,255,255,.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.02) 1px, transparent 1px),
        linear-gradient(180deg, #181515, #0B0A0A);
    background-size: 36px 36px, 36px 36px, auto;
    border: 1px solid var(--lumina-border2); border-radius: 16px;
    padding: 2.1rem 2.4rem;
    display: flex; align-items: center; justify-content: space-between;
    gap: 2rem; flex-wrap: wrap;
    box-shadow: 0 22px 48px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.04);
    animation: luminaFade .35s ease both;
}
.lumina-hero::before {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background: radial-gradient(620px 300px at 5% -12%, rgba(224,28,43,.2), transparent 65%);
}
.hero-watermark {
    position: absolute; right: -70px; top: 50%; transform: translateY(-50%);
    opacity: .06; pointer-events: none; z-index: 0;
}
.hero-watermark img { display: block; width: 480px; height: 480px; object-fit: contain; }
.lumina-brand { display: flex; align-items: center; gap: 1.3rem; position: relative; z-index: 1; }
.lumina-wordmark {
    font-size: 1.55rem; font-weight: 900; letter-spacing: .2em; line-height: 1.05;
    color: var(--lumina-text); text-transform: uppercase;
    display: flex; align-items: center; flex-wrap: wrap;
}
.lumina-wordmark .dot { color: var(--lumina-red); }
.lumina-wordmark .word-sub {
    font-size: .6rem; font-weight: 800; letter-spacing: .32em; color: var(--lumina-muted2);
    border-left: 2px solid var(--lumina-red); padding-left: .7rem; margin-left: .7rem;
    text-transform: uppercase;
}
.lumina-statement {
    font-size: .88rem; color: var(--lumina-muted); margin-top: .6rem; letter-spacing: .02em;
}
.hero-phrase {
    font-size: .64rem; font-weight: 800; letter-spacing: .28em; text-transform: uppercase;
    color: var(--lumina-muted2); margin-top: .9rem; border-top: 1px solid var(--lumina-border);
    padding-top: .72rem; display: inline-block;
}
.hero-side { display: flex; flex-direction: column; align-items: flex-end; gap: .75rem; position: relative; z-index: 1; }
.status-pill {
    display: inline-flex; align-items: center; gap: .55rem;
    border: 1px solid var(--lumina-border2); border-radius: 999px;
    background: var(--lumina-card); padding: .44rem 1rem;
    font-size: .68rem; font-weight: 800; letter-spacing: .16em;
    text-transform: uppercase; color: var(--lumina-text); white-space: nowrap;
    box-shadow: 0 6px 18px rgba(0,0,0,.3);
}
.status-dot { width: 7px; height: 7px; border-radius: 50%; flex: 0 0 auto; }
.status-dot.ok { background: var(--lumina-green); box-shadow: 0 0 0 3px rgba(111,168,119,.2); }
.status-dot.red { background: var(--lumina-red); box-shadow: 0 0 0 3px rgba(224,28,43,.28); }
.hero-badges { display: flex; gap: .45rem; flex-wrap: wrap; justify-content: flex-end; }

/* ---------- pills ---------- */
.pill {
    font-size: .64rem; font-weight: 800; letter-spacing: 1.4px; text-transform: uppercase;
    padding: 4px 10px; border-radius: 999px; border: 1px solid; white-space: nowrap;
}
.pill-red   { color: #fff; border-color: var(--lumina-red); background: var(--lumina-red); }
.pill-green { color: var(--lumina-green); border-color: var(--lumina-green); background: rgba(111,168,119,.08); }
.pill-amber { color: var(--lumina-amber); border-color: var(--lumina-amber); background: rgba(217,164,65,.08); }
.pill-slate { color: var(--lumina-muted); border-color: var(--lumina-border2); background: var(--lumina-card); }

/* ---------- section headings ---------- */
.section-head {
    display: flex; align-items: flex-start; gap: .95rem;
    margin: 2.5rem 0 .95rem; padding-bottom: .85rem;
    position: relative;
    animation: luminaFade .3s ease both;
}
.section-head::after {
    content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 1px;
    background: linear-gradient(90deg, rgba(224,28,43,.55), rgba(255,255,255,.06) 46%, transparent 78%);
}
.section-num {
    font-family: "Cascadia Code", Consolas, monospace; font-size: .8rem; font-weight: 800;
    color: var(--lumina-red); background: var(--lumina-red-soft);
    border: 1px solid var(--lumina-red-line); border-radius: 7px;
    padding: 4px 10px; margin-top: 2px; flex: 0 0 auto;
}
.section-title { font-size: 1.3rem; font-weight: 900; color: var(--lumina-text); text-transform: uppercase; letter-spacing: .07em; line-height: 1.2; }
.section-sub { font-size: .8rem; color: var(--lumina-muted); margin-top: 4px; line-height: 1.55; }
.section-circuit { margin-left: auto; align-self: center; color: rgba(224,28,43,.4); flex: 0 0 auto; }

/* ---------- pipeline ---------- */
.pipe-row {
    display: flex; align-items: stretch;
    border: 1px solid var(--lumina-border2); border-radius: 14px;
    background: var(--lumina-card); overflow: hidden; flex-wrap: wrap;
    box-shadow: 0 10px 28px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.03);
}
.pipe {
    flex: 1 1 132px; min-width: 132px; padding: 1.15rem .95rem .95rem;
    animation: luminaFade .35s ease both; position: relative;
}
.pipe + .pipe { border-left: 1px solid var(--lumina-border); }
.pipe-arrow { align-self: center; color: var(--lumina-muted2); font-weight: 900; font-size: 1.05rem; padding: 0 .3rem; }
.pipe-icon {
    width: 36px; height: 36px; border: 1px solid var(--lumina-border2); border-radius: 9px;
    display: flex; align-items: center; justify-content: center; margin-bottom: .6rem;
    color: var(--lumina-muted); background: var(--lumina-card2);
}
.pipe-kicker { font-size: .6rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; color: var(--lumina-muted2); }
.pipe-value { font-size: 1.04rem; font-weight: 900; color: var(--lumina-text); margin: .25rem 0; }
.pipe-sub { font-size: .67rem; color: var(--lumina-muted2); line-height: 1.5; }
.pipe-hot { background: linear-gradient(180deg, rgba(224,28,43,.12), transparent 72%); }
.pipe-hot::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: var(--lumina-red); }
.pipe-hot .pipe-icon { border-color: var(--lumina-red); color: var(--lumina-red); background: var(--lumina-card); }
.pipe-hot .pipe-kicker { color: var(--lumina-red); }
.pipe-hot .pipe-value { color: var(--lumina-red); }

/* ---------- risk hero ---------- */
.risk-hero {
    position: relative; overflow: hidden;
    background:
        linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px),
        linear-gradient(180deg, #191616, #0D0C0C);
    background-size: 40px 40px, 40px 40px, auto;
    border: 1px solid var(--lumina-border2); border-radius: 16px;
    margin-bottom: 1rem;
    box-shadow: 0 16px 40px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.04);
    animation: luminaFade .4s ease both;
}
.risk-hero .risk-glow { position: absolute; inset: 0; pointer-events: none; }
.risk-hero .risk-watermark {
    position: absolute; right: -60px; top: 50%; transform: translateY(-50%);
    opacity: .06; pointer-events: none; z-index: 0;
}
.risk-hero .risk-watermark img { width: 420px; height: 420px; object-fit: contain; }
.risk-main {
    position: relative; z-index: 1; display: flex; align-items: center; gap: 2rem;
    padding: 1.7rem 2rem; flex-wrap: wrap;
}
.risk-left { flex: 1 1 280px; min-width: 280px; position: relative; }
.risk-eyebrow { font-size: .7rem; font-weight: 800; letter-spacing: .3em; text-transform: uppercase; color: var(--lumina-muted); }
.risk-level { font-size: 3.9rem; font-weight: 900; line-height: 1; letter-spacing: .04em; color: var(--lumina-text); margin-top: .45rem; }
.risk-level.critical { color: var(--lumina-red); text-shadow: 0 0 26px rgba(224,28,43,.45); }
.risk-level.high { color: var(--lumina-amber); text-shadow: 0 0 24px rgba(217,164,65,.35); }
.risk-level.medium { color: var(--lumina-amber); }
.risk-level.low { color: var(--lumina-green); }
.risk-score { font-family: "Cascadia Code", Consolas, monospace; font-size: 1.85rem; font-weight: 700; color: var(--lumina-text); margin-top: .55rem; }
.risk-score small { font-size: 1.1rem; color: var(--lumina-muted2); font-weight: 600; }
.risk-status { display: inline-block; margin-top: .7rem; font-size: .76rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; color: var(--lumina-text); border: 1px solid var(--lumina-border2); border-radius: 999px; padding: .32rem .85rem; background: var(--lumina-card); }
.risk-action { margin-top: .62rem; font-size: .84rem; font-weight: 700; color: var(--lumina-muted); }
.risk-action b { color: var(--lumina-red); }
.risk-mid { flex: 1 1 340px; min-width: 300px; border-left: 1px solid var(--lumina-border); padding-left: 1.8rem; }
.risk-mid-title { font-size: .62rem; font-weight: 800; letter-spacing: .24em; text-transform: uppercase; color: var(--lumina-muted2); margin-bottom: .75rem; }
.risk-signal {
    display: flex; align-items: center; gap: .8rem; padding: .62rem .7rem; margin-bottom: .5rem;
    background: var(--lumina-card); border: 1px solid var(--lumina-border); border-radius: 10px;
}
.risk-signal-icon {
    width: 32px; height: 32px; border: 1px solid var(--lumina-border2); border-radius: 8px;
    display: flex; align-items: center; justify-content: center; flex: 0 0 auto;
    color: var(--lumina-red); background: var(--lumina-card2);
}
.risk-signal-text { font-size: .9rem; font-weight: 800; color: var(--lumina-text); line-height: 1.3; }
.risk-signal-detail { font-size: .74rem; color: var(--lumina-muted2); font-weight: 600; }
.risk-right { flex: 0 0 auto; position: relative; display: flex; flex-direction: column; align-items: center; gap: .4rem; }
.risk-gauge-label { font-size: .6rem; font-weight: 800; letter-spacing: .24em; text-transform: uppercase; color: var(--lumina-muted2); }
.gauge-wrap { position: relative; }
.risk-hero-footer {
    position: relative; z-index: 1; display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
    padding: .8rem 2rem; border-top: 1px solid var(--lumina-border); background: rgba(0,0,0,.22);
}
.risk-interv { font-size: .74rem; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; color: var(--lumina-muted2); display: flex; align-items: center; gap: .6rem; }
.risk-interv .status-dot { background: var(--lumina-muted2); }
.risk-interv.on { color: var(--lumina-red); }
.risk-meta { font-size: .7rem; font-weight: 700; letter-spacing: .08em; color: var(--lumina-muted); }
.risk-hero.critical { border-color: var(--lumina-red); animation: luminaFade .4s ease both, luminaPulse 3s ease-in-out infinite; }
.risk-hero.high { border-color: rgba(217,164,65,.5); }
.risk-hero.medium { border-color: rgba(217,164,65,.38); }
.risk-hero.low { border-color: rgba(111,168,119,.45); }
.risk-hero.critical .risk-glow { background: radial-gradient(700px 300px at 100% 0%, rgba(224,28,43,.16), transparent 65%); }
.risk-hero.high .risk-glow { background: radial-gradient(700px 300px at 100% 0%, rgba(217,164,65,.1), transparent 65%); }
.risk-hero.medium .risk-glow { background: radial-gradient(700px 300px at 100% 0%, rgba(176,137,72,.08), transparent 65%); }
.risk-hero.low .risk-glow { background: radial-gradient(700px 300px at 100% 0%, rgba(111,168,119,.06), transparent 65%); }

/* ---------- factors ---------- */
.factor-row {
    display: flex; align-items: center; gap: 1rem;
    background: var(--lumina-card); border: 1px solid var(--lumina-border); border-radius: 10px;
    padding: 1rem 1.2rem; margin-bottom: .6rem;
    animation: luminaFade .3s ease both;
    box-shadow: 0 6px 18px rgba(0,0,0,.18), inset 0 1px 0 rgba(255,255,255,.03);
}
.factor-idx { font-family: "Cascadia Code", Consolas, monospace; font-size: .9rem; font-weight: 800; color: var(--lumina-red); flex: 0 0 auto; }
.factor-icon { width: 40px; height: 40px; border: 1px solid var(--lumina-border2); border-radius: 9px; display: flex; align-items: center; justify-content: center; color: var(--lumina-red); background: var(--lumina-card2); flex: 0 0 auto; }
.factor-title { font-size: 1.02rem; font-weight: 800; color: var(--lumina-text); }
.factor-detail { font-size: .8rem; color: var(--lumina-muted); font-weight: 600; margin-left: .5rem; }
.factor-more { font-size: .78rem; color: var(--lumina-muted); margin-top: .3rem; }

/* ---------- intervention ---------- */
.intervention { border-radius: 14px; border: 1px solid var(--lumina-border2); overflow: hidden; background: var(--lumina-card); height: 100%; box-shadow: 0 12px 30px rgba(0,0,0,.3); }
.intervention-critical, .intervention-high {
    border-color: var(--lumina-red); position: relative;
    background: linear-gradient(180deg, #1A1011, #0E0B0B);
}
.intervention-critical::before, .intervention-high::before {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background: radial-gradient(560px 260px at 0% 0%, rgba(224,28,43,.16), transparent 65%);
}
.intervention-head { padding: 1.35rem 1.5rem .6rem; position: relative; }
.intervention-eyebrow { font-size: .68rem; font-weight: 800; letter-spacing: .22em; text-transform: uppercase; color: var(--lumina-red); display: flex; align-items: center; gap: .5rem; }
.intervention-title { font-size: 1.45rem; font-weight: 900; line-height: 1.18; letter-spacing: .02em; margin-top: .5rem; color: var(--lumina-text); }
.intervention-steps { padding: .8rem 1.5rem 1.3rem; position: relative; }
.intervention-steps .step { display: flex; gap: .8rem; align-items: flex-start; margin: .5rem 0; }
.intervention-steps .step-num { font-family: "Cascadia Code", Consolas, monospace; font-weight: 800; font-size: .78rem; color: var(--lumina-red); flex: 0 0 auto; padding-top: .1rem; }
.intervention-steps .step-text { font-size: .86rem; font-weight: 600; line-height: 1.5; color: var(--lumina-muted); }
.intervention-critical .intervention-steps, .intervention-high .intervention-steps { border-top: 1px solid var(--lumina-border); }
.intervention-critical .intervention-steps .step-text, .intervention-high .intervention-steps .step-text { color: rgba(252,252,252,.85); }
.intervention-medium .intervention-steps, .intervention-low .intervention-steps { border-top: 1px solid var(--lumina-border); }

/* ---------- delivery ---------- */
.delivery-card { border: 1px solid var(--lumina-border2); border-radius: 12px; background: var(--lumina-card); padding: 1.1rem 1.2rem; height: 100%; box-shadow: 0 8px 22px rgba(0,0,0,.22), inset 0 1px 0 rgba(255,255,255,.03); }
.delivery-title { font-size: .66rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; color: var(--lumina-muted); margin-bottom: .55rem; }
.delivery-item { display: flex; justify-content: space-between; align-items: center; font-size: .82rem; padding: .5rem 0; border-bottom: 1px dashed var(--lumina-border); gap: .6rem; }
.delivery-item:last-child { border-bottom: none; }
.delivery-label { color: var(--lumina-muted); font-weight: 700; }
.delivery-value { font-weight: 800; font-family: "Cascadia Code", Consolas, monospace; text-align: right; }
.delivery-value.on { color: var(--lumina-red); }
.delivery-value.good { color: var(--lumina-green); }
.delivery-value.dim { color: var(--lumina-muted2); }
.demo-stamp {
    display: inline-block; border: 2px solid var(--lumina-red); color: var(--lumina-red);
    font-weight: 900; letter-spacing: .14em; font-size: .6rem; text-transform: uppercase;
    padding: .18rem .5rem; border-radius: 6px; transform: rotate(-2deg); white-space: nowrap;
}

/* ---------- notices ---------- */
.notice {
    border: 1px solid var(--lumina-border); background: var(--lumina-card); border-left: 3px solid var(--lumina-muted2);
    border-radius: 10px; padding: .72rem 1rem; font-size: .8rem; color: var(--lumina-text);
    margin-top: .6rem; line-height: 1.6; box-shadow: 0 4px 14px rgba(0,0,0,.18);
}
.notice-red { border-left-color: var(--lumina-red); }
.notice-amber { border-left-color: var(--lumina-amber); }
.notice-green { border-left-color: var(--lumina-green); }
.notice-muted { color: var(--lumina-muted); }

/* ---------- timeline ---------- */
.timeline { position: relative; padding-left: 1.7rem; }
.timeline::before { content: ""; position: absolute; left: 7px; top: 12px; bottom: 12px; width: 2px; background: linear-gradient(180deg, var(--lumina-border2), rgba(224,28,43,.35), var(--lumina-border2)); }
.timeline-node { position: relative; padding: 0 0 1.25rem .3rem; }
.timeline-node::before {
    content: ""; position: absolute; left: -1.7rem; top: 8px;
    width: 14px; height: 14px; border-radius: 50%;
    background: var(--lumina-card); border: 2.5px solid var(--lumina-muted2);
    box-shadow: 0 0 0 4px rgba(0,0,0,.25);
}
.timeline-node.danger::before { border-color: var(--lumina-red); background: var(--lumina-red); box-shadow: 0 0 0 4px rgba(224,28,43,.18); }
.timeline-time { font-family: "Cascadia Code", Consolas, monospace; font-weight: 800; font-size: .8rem; color: var(--lumina-muted); letter-spacing: .08em; }
.timeline-label { font-weight: 900; font-size: 1.05rem; color: var(--lumina-text); margin-top: .15rem; }
.timeline-note { font-size: .78rem; color: var(--lumina-muted2); line-height: 1.5; margin-top: .2rem; }
.timeline-final { display: inline-flex; align-items: center; gap: .6rem; font-weight: 900; font-size: 1.35rem; text-transform: uppercase; letter-spacing: .1em; color: var(--lumina-red); margin-top: .2rem; }

/* ---------- empty state ---------- */
.empty-hero {
    position: relative; overflow: hidden;
    background:
        linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px),
        linear-gradient(180deg, #161313, #0B0A0A);
    background-size: 40px 40px, 40px 40px, auto;
    border: 1px solid var(--lumina-border2); border-radius: 16px;
    padding: 3.2rem 2.4rem; text-align: center;
    animation: luminaFade .4s ease both;
}
.empty-hero::before {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background: radial-gradient(620px 300px at 12% 0%, rgba(224,28,43,.18), transparent 65%);
}
.empty-seal { position: absolute; right: -40px; bottom: -40px; color: var(--lumina-red); opacity: .12; pointer-events: none; }
.empty-watermark-side {
    position: absolute; right: -50px; top: 50%; transform: translateY(-50%);
    opacity: .06; pointer-events: none; z-index: 0;
}
.empty-watermark-side img { width: 400px; height: 400px; object-fit: contain; }
.empty-brand { position: relative; z-index: 1; display: flex; flex-direction: column; align-items: center; gap: .9rem; }
.empty-kicker { font-size: .68rem; font-weight: 800; letter-spacing: .34em; text-transform: uppercase; color: var(--lumina-red); }
.empty-title { font-size: 1.7rem; font-weight: 900; letter-spacing: .08em; color: var(--lumina-text); text-transform: uppercase; }
.empty-sub { color: var(--lumina-muted); font-size: .9rem; margin-top: .15rem; max-width: 620px; margin-left: auto; margin-right: auto; line-height: 1.65; position: relative; }
.mode-card {
    background: var(--lumina-card); border: 1px solid var(--lumina-border); border-radius: 12px;
    padding: 1.15rem 1.3rem; height: 100%; position: relative;
    box-shadow: 0 8px 22px rgba(0,0,0,.22), inset 0 1px 0 rgba(255,255,255,.03);
    transition: border-color .18s ease, transform .18s ease;
}
.mode-card:hover { border-color: var(--lumina-border2); transform: translateY(-2px); }
.mode-card-title { font-weight: 900; font-size: .82rem; color: var(--lumina-text); text-transform: uppercase; letter-spacing: .06em; display: flex; align-items: center; gap: .55rem; }
.mode-card-title svg { color: var(--lumina-red); flex: 0 0 auto; }
.mode-card-sub { font-size: .77rem; color: var(--lumina-muted2); line-height: 1.6; margin-top: .45rem; }

/* ---------- report ---------- */
.report-panel {
    position: relative; overflow: hidden;
    background: linear-gradient(180deg, #161313, #0C0B0B);
    border: 1px solid var(--lumina-border2); border-radius: 14px;
    padding: 1.7rem 2rem; margin-bottom: .9rem;
    display: flex; align-items: center; gap: 1.4rem; flex-wrap: wrap;
    box-shadow: 0 12px 30px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.04);
}
.report-panel::before {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background: radial-gradient(520px 240px at 100% 0%, rgba(224,28,43,.18), transparent 65%);
}
.report-eyebrow { font-size: .68rem; font-weight: 800; letter-spacing: .26em; text-transform: uppercase; color: var(--lumina-red); position: relative; }
.report-title { font-size: 1.45rem; font-weight: 900; letter-spacing: .03em; margin-top: .4rem; color: var(--lumina-text); position: relative; }
.report-sub { color: var(--lumina-muted); font-size: .8rem; margin-top: .3rem; position: relative; }
.report-logo { margin-left: auto; flex: 0 0 auto; position: relative; }

/* ---------- footer ---------- */
.footer {
    background: linear-gradient(180deg, #161313, #0C0B0B);
    border: 1px solid var(--lumina-border2); border-radius: 12px;
    padding: 1.2rem 1.6rem; display: flex; justify-content: space-between;
    align-items: center; gap: 1rem; flex-wrap: wrap;
    box-shadow: 0 10px 26px rgba(0,0,0,.3), inset 0 1px 0 rgba(255,255,255,.04);
}
.footer-brand { font-weight: 900; letter-spacing: .3em; font-size: 1.05rem; color: var(--lumina-text); }
.footer-brand .dot { color: var(--lumina-red); }
.footer-line { font-size: .72rem; font-weight: 700; letter-spacing: .14em; color: var(--lumina-muted); text-transform: uppercase; }
.footer-line b { color: var(--lumina-red); }

/* ---------- native component polish ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid var(--lumina-border); border-radius: 12px; background: var(--lumina-card); padding: 1rem 1rem .4rem;
}
[data-testid="stBaseButton-primary"] {
    background: var(--lumina-red); color: #fff; border: 1px solid var(--lumina-red);
    border-radius: 8px; font-weight: 800; letter-spacing: .08em;
    transition: background .15s ease, border-color .15s ease, transform .15s ease;
}
[data-testid="stBaseButton-primary"]:hover { background: #B31421; border-color: #B31421; color: #fff; transform: translateY(-1px); }
[data-testid="stBaseButton-primary"]:focus-visible { outline: 2px solid rgba(224,28,43,.5); outline-offset: 2px; }
[data-testid="stBaseButton-secondary"] {
    background: var(--lumina-card2); color: var(--lumina-text); border: 1px solid var(--lumina-border2);
    font-weight: 700; border-radius: 8px; transition: color .15s ease, border-color .15s ease, transform .15s ease;
}
[data-testid="stBaseButton-secondary"]:hover { border-color: var(--lumina-red); color: #fff; transform: translateY(-1px); }
[data-testid="stBaseButton-secondary"]:focus-visible { outline: 2px solid rgba(224,28,43,.5); outline-offset: 2px; }
[data-testid="stBaseButton-tertiary"] { background: transparent; color: var(--lumina-muted); border: 1px solid transparent; border-radius: 8px; transition: color .15s ease; }
[data-testid="stBaseButton-tertiary"]:hover { color: var(--lumina-text); }

[data-testid="stRadio"] > div { gap: 8px; }
[data-testid="stRadio"] label {
    display: flex; align-items: center; gap: 8px;
    border: 1px solid var(--lumina-border2); border-radius: 999px; padding: .42rem .95rem;
    background: var(--lumina-card2); font-size: .76rem; font-weight: 700; color: var(--lumina-text);
    cursor: pointer; transition: all .15s ease; margin: 0;
}
[data-testid="stRadio"] label:hover { border-color: var(--lumina-muted); }
[data-testid="stRadio"] label:has(input:checked) {
    border-color: var(--lumina-text); background: var(--lumina-text); color: var(--lumina-bg);
}
[data-testid="stRadio"] input { accent-color: var(--lumina-red); }

[data-testid="stMetric"] { background: var(--lumina-card); border: 1px solid var(--lumina-border); border-radius: 10px; padding: .65rem .85rem; }
[data-testid="stMetricLabel"] { color: var(--lumina-muted); font-size: .68rem; letter-spacing: .12em; text-transform: uppercase; font-weight: 800; }
[data-testid="stMetricValue"] { color: var(--lumina-text); font-family: "Cascadia Code", Consolas, monospace; }

[data-testid="stAlert"] { border: 1px solid var(--lumina-border); border-radius: 10px; }
[data-testid="stExpander"] { border: 1px solid var(--lumina-border); background: var(--lumina-card); border-radius: 10px; }
[data-testid="stExpander"] summary { color: var(--lumina-text); font-weight: 800; font-size: .84rem; }
[data-testid="stDataFrame"] { border: 1px solid var(--lumina-border); border-radius: 10px; overflow: hidden; }
[data-testid="stPlotlyChart"] { background: var(--lumina-card); border: 1px solid var(--lumina-border); border-radius: 10px; padding: .4rem .4rem 0; }
[data-testid="stProgress"] > div > div { background: var(--lumina-red); }
[data-testid="stWidgetLabel"] p { color: var(--lumina-muted); font-weight: 800; font-size: .8rem; letter-spacing: .4px; }

@media (max-width: 900px) {
    .lumina-name { font-size: 1.9rem; }
    .risk-level { font-size: 2.4rem; }
    .hero-side { align-items: flex-start; }
    .pipe-value { font-size: .92rem; }
}
"""

st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


# ============================= HELPERS =============================
def _to_body(signals: dict, include_telemetry: bool = True) -> dict:
    body = {key: signals.get(key, 0) for key in CALL_KEYS}
    body["day_of_week"] = signals.get("day_of_week", 2)
    if include_telemetry:
        body["extra_telemetry"] = {key: signals.get(key, 0) for key in TELEMETRY_KEYS}
    return body


def score_snapshot(signals: dict, include_telemetry: bool = True) -> dict:
    response = requests.post(
        f"{API_BASE}/api/score",
        json=_to_body(signals, include_telemetry),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def trigger_intervention(signals: dict, include_telemetry: bool = True) -> dict:
    response = requests.post(
        f"{API_BASE}/api/silent-intervention",
        json=_to_body(signals, include_telemetry),
        params={"victim_name": "Family Member"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _row(signals: dict, t: int, label: str, note: str, include_telemetry: bool) -> dict:
    result = score_snapshot(signals, include_telemetry)
    return {
        "t": t,
        "label": label,
        "note": note,
        "signals": signals,
        "score": result["risk_score"],
        "level": result["risk_level"],
        "factors": result.get("top_factors", []),
        "alert_message": result.get("alert_message", ""),
        "explanation": result.get("explanation", ""),
        "ml_probability": result.get("ml_probability"),
        "rule_contribution": result.get("rule_contribution"),
        "ml_cap_applied": result.get("ml_cap_applied"),
        "safety_rule_contributions": result.get("safety_rule_contributions", []),
        "missing_telemetry": result.get("missing_telemetry", []),
        "model_status": result.get("model_status", "unavailable"),
    }


def run_scenario(scenario, name: str, include_telemetry: bool) -> list:
    timeline = []
    progress = st.progress(0, text=f"Running {name}...")
    for i, snap in enumerate(scenario):
        progress.progress((i + 1) / len(scenario), text=f"Scoring: {snap['label']}")
        timeline.append(_row(snap["signals"], snap["t"], snap["label"], snap["note"], include_telemetry))
    progress.empty()
    return timeline


def _simulator_signals() -> tuple:
    """One random snapshot from the Python AndroidDeviceSimulator (simulated source)."""
    from app.services.android_simulator import AndroidDeviceSimulator

    sim = AndroidDeviceSimulator()
    if random.random() < 0.5:
        telem = sim.generate_scam_scenario()
        kind = "scam"
    else:
        telem = sim.generate_normal_scenario()
        kind = "normal"
    d = asdict(telem)
    is_scam = kind == "scam"
    signals = {
        "call_duration_min": d.get("call_duration_minutes", 0),
        "is_unknown_number": int(is_scam),
        "is_video_call": int(bool(d.get("is_video_call"))),
        "hour_of_day": 12,
        "caller_call_history": 0 if is_scam else 8,
        "outgoing_activity_ratio": 0.1 if is_scam else 0.7,
        "day_of_week": 2,
        "screen_time_on_call_percent": d.get("screen_time_on_call_percent", 0),
        "num_app_switches": d.get("num_app_switches", 0),
        "num_home_presses": d.get("num_home_presses", 0),
        "has_sms_activity": int(bool(d.get("has_sms_activity"))),
        "has_social_app_activity": int(bool(d.get("has_social_app_activity"))),
        "location_change": d.get("location_change", 0),
        "screen_brightness": d.get("screen_brightness", 0),
        "screen_on_continuous_hours": d.get("screen_on_continuous_hours", 0),
        "persistence_hours": 2 if d.get("call_duration_minutes", 0) > 60 else 0,
    }
    return signals, kind


def run_simulator_snapshot(include_telemetry: bool) -> tuple:
    signals, kind = _simulator_signals()
    is_scam = kind == "scam"
    label = "Simulated scam call" if is_scam else "Simulated normal call"
    note = (
        "Random snapshot from the AndroidDeviceSimulator (scam profile: unknown caller, "
        "long video call, high isolation signals)."
        if is_scam
        else "Random snapshot from the AndroidDeviceSimulator (normal profile: known caller, "
        "normal device activity)."
    )
    row = _row(signals, 0, label, note, include_telemetry)
    return [row], "scam" if is_scam else "normal"


def reset_state():
    for key in [
        "timeline",
        "scenario_name",
        "include_telemetry",
        "intervention",
        "report_bytes",
        "report_filename",
        "report_meta",
    ]:
        st.session_state.pop(key, None)


# ============================= UI BUILDERS =============================
def _section(num: str, title: str, sub: str) -> None:
    st.markdown(
        f"""
        <div class="section-head">
            <div class="section-num">{num}</div>
            <div>
                <div class="section-title">{title}</div>
                <div class="section-sub">{sub}</div>
            </div>
            <div class="section-circuit">{_circuit_svg()}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _pill(text: str, kind: str) -> str:
    return f'<span class="pill pill-{kind}">{text}</span>'


def render_hero() -> None:
    hs = _health_status()
    if hs["api"] == "online":
        status = f'<span class="status-dot ok"></span>SYSTEM ONLINE'
        model = hs.get("model_status", "unknown")
        if model == "available":
            model_pill = _pill("MODEL · XGBOOST ONLINE", "green")
        elif model == "degraded":
            model_pill = _pill("MODEL · RULES-ONLY", "amber")
        else:
            model_pill = _pill("MODEL UNAVAILABLE", "red")
    else:
        status = f'<span class="status-dot red"></span>SYSTEM OFFLINE'
        model_pill = _pill("MODEL UNKNOWN", "slate")

    badges = (
        model_pill
        + _pill("SIMULATED TELEMETRY", "slate")
        + _pill("DEMO · NOT DELIVERED", "red")
    )

    st.markdown(
        f"""
        <div class="lumina-hero">
            <div class="hero-watermark"><img src="{_logo_watermark_uri()}" alt=""/></div>
            <div class="lumina-brand">
                <div class="logo-tile">{_logo_img(210)}</div>
                <div>
                    <div class="lumina-tag">AI Bridge Against<br/>Digital Arrest Isolation</div>
                    <div class="lumina-statement">Detect the pattern. Break the isolation. Bring help in.</div>
                    <div class="hero-phrase">Detect → Analyze → Alert → Protect → Connect</div>
                </div>
            </div>
            <div class="hero-side">
                <div class="status-pill">{status}</div>
                <div class="hero-badges">{badges}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _gauge_svg(score: float, color: str) -> str:
    radius = 50.0
    circumference = 2 * math.pi * radius
    pct = max(0.0, min(100.0, float(score))) / 100.0
    dash = circumference * pct
    gap = circumference - dash
    return f"""
    <svg width="132" height="132" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="{radius}" fill="none" stroke="#2A2828" stroke-width="7"/>
        <circle cx="60" cy="60" r="{radius}" fill="none" stroke="{color}" stroke-width="7"
            stroke-dasharray="{dash:.2f} {gap:.2f}"
            transform="rotate(-90 60 60)"/>
        <text x="60" y="56" text-anchor="middle" fill="#FCFCFC" font-size="25" font-weight="800"
            font-family="Cascadia Code, Consolas, monospace">{score:.0f}</text>
        <text x="60" y="72" text-anchor="middle" fill="#6F6F6F" font-size="9"
            font-family="Cascadia Code, Consolas, monospace">/ 100</text>
    </svg>
    """


def risk_hero(level: str, score: float, intervention: dict = None) -> None:
    color = LEVEL_COLORS.get(level, "#6F6F6F")
    descriptor, action = LEVEL_SUMMARY.get(level, ("Risk assessed", "Review the pipeline below"))
    triggered = bool(intervention.get("intervention_triggered")) if intervention else False
    delivery = str(intervention.get("delivery_status", "")) if intervention else ""
    interv_line = (
        f'<div class="risk-interv on"><span class="status-dot red"></span> '
        f'INTERVENTION TRIGGERED · {delivery}</div>'
        if triggered
        else f'<div class="risk-interv"><span class="status-dot"></span> INTERVENTION MONITORING</div>'
    )
    st.markdown(
        f"""
        <div class="risk-hero {level}">
            <div class="risk-glow"></div>
            <div style="flex:1; min-width:260px; position:relative;">
                <div class="risk-eyebrow">Current Risk</div>
                <div class="risk-level {level}">{level.upper()}</div>
                <div class="risk-score">{score:.1f} <small>/ 100</small></div>
                <div class="risk-status">{descriptor}</div>
                <div class="risk-action"><b>●</b> {action}</div>
                {interv_line}
            </div>
            <div class="gauge-wrap">{_gauge_svg(score, color)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _pipe_stage(icon: str, kicker: str, value: str, sub: str, hot: bool = False,
                color: str = None, delay: float = 0.0) -> str:
    cls = "pipe" + (" pipe-hot" if hot else "")
    value_style = f' style="color:{color};"' if color else ""
    return f"""
    <div class="{cls}" style="animation-delay:{delay:.2f}s">
        <div class="pipe-icon">{_icon(icon)}</div>
        <div class="pipe-kicker">{kicker}</div>
        <div class="pipe-value"{value_style}>{value}</div>
        <div class="pipe-sub">{sub}</div>
    </div>
    """


def pipeline_strip(snap: dict, intervention: dict = None) -> None:
    missing = len(snap["missing_telemetry"])
    ml_value = f"{snap['ml_probability']:.1f}%" if snap.get("ml_probability") is not None else "rules-only"
    ml_sub = (
        "XGBoost · 11 call-behavior features"
        if snap.get("ml_probability") is not None
        else f"not served ({snap['model_status']}) - rules only"
    )
    active_count = sum(1 for item in snap["safety_rule_contributions"] if item.get("active"))
    level = snap["level"]
    level_color = LEVEL_COLORS.get(level, "#6F6F6F")

    triggered = bool(intervention.get("intervention_triggered")) if intervention else False
    if triggered:
        intv_value = "TRIGGERED"
        intv_sub = "high / critical threshold"
        intv_hot = True
    else:
        intv_value = "MONITOR"
        intv_sub = "below alert threshold"
        intv_hot = False

    stages = [
        _pipe_stage("phone", "Telemetry", f"{29 - missing}/29",
                    f"{missing} field(s) unavailable", delay=0.0),
        _pipe_stage("magnifier", "Features", "11/11",
                    "call-behavior schema", delay=0.06),
        _pipe_stage("shield", "ML Corroboration", ml_value, ml_sub, delay=0.12),
        _pipe_stage("warning", "Safety Rules", f"{snap['rule_contribution']:.1f}%",
                    f"{active_count} explicit signal(s)", delay=0.18),
        _pipe_stage("lock", "Gated Fusion", f"{snap['score']:.1f}%",
                    "ceiling applied" if snap.get("ml_cap_applied") else "no ceiling applied",
                    hot=bool(snap.get("ml_cap_applied")), delay=0.24),
        _pipe_stage("handcuffs", "Risk", level.upper(), "declared level",
                    hot=level in ("high", "critical"), color=level_color, delay=0.30),
        _pipe_stage("siren", "Intervention", intv_value, intv_sub, hot=intv_hot, delay=0.36),
    ]
    cells = []
    for i, cell in enumerate(stages):
        cells.append(cell)
        if i < len(stages) - 1:
            cells.append('<div class="pipe-arrow">&#8594;</div>')

    st.markdown(f'<div class="pipe-row">{"".join(cells)}</div>', unsafe_allow_html=True)
    st.caption(
        "Fusion rule: risk = 0.5 x ML probability + 0.5 x rule contribution, then gated. "
        "The score cannot cross 49.9 unless rule evidence is at least 50%, and cannot cross 74.9 unless rule "
        "evidence is at least 75%. ML corroborates - it never decides the risk level alone."
    )
    if snap.get("ml_cap_applied"):
        st.markdown(
            f'<div class="notice notice-amber"><b>Ceiling applied:</b> {snap["ml_cap_applied"]}</div>',
            unsafe_allow_html=True,
        )
    if snap["missing_telemetry"]:
        labels = [TELEMETRY_LABELS.get(name, name) for name in snap["missing_telemetry"]]
        st.markdown(
            f'<div class="notice notice-muted"><b>Missing telemetry:</b> {", ".join(labels)}. '
            "Missing fields are NOT treated as behavioral signals - no fabricated zero/false evidence.</div>",
            unsafe_allow_html=True,
        )


def _factor_parts(factor: str) -> tuple:
    match = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", factor)
    if match:
        return match.group(1).strip(), f"({match.group(2).strip()})"
    return factor, ""


def render_detection_factors(factors: list) -> None:
    motif_cycle = ["phone", "magnifier", "handcuffs", "warning", "lock", "siren"]
    rows = []
    for i, factor in enumerate(factors[:3]):
        title, detail = _factor_parts(factor)
        rows.append(
            f"""
            <div class="factor-row" style="animation-delay:{0.08 * i:.2f}s">
                <div class="factor-idx">{i + 1:02d}</div>
                <div class="factor-icon">{_icon(motif_cycle[i % len(motif_cycle)])}</div>
                <div class="factor-title">{title}{f'<span class="factor-detail">{detail}</span>' if detail else ''}</div>
            </div>
            """
        )
    st.markdown(f'<div>{"".join(rows)}</div>', unsafe_allow_html=True)
    if len(factors) > 3:
        st.markdown(
            f'<div class="factor-more">Additional signals: {", ".join(factors[3:6])}.</div>',
            unsafe_allow_html=True,
        )


def render_intervention(inter: dict, level: str) -> None:
    triggered = bool(inter.get("intervention_triggered"))
    delivery = str(inter.get("delivery_status", ""))
    delivered = bool(inter.get("delivered"))
    contacts = inter.get("alert_sent_to") or []
    contacts_text = ", ".join(contacts) if contacts else "none configured (LUMINA_TRUSTED_CONTACTS not set)"
    rec = INTERVENTIONS.get(level, INTERVENTIONS["low"])
    match = re.match(r"^\[([^\]]+)\]\s*(.*)$", rec["title"])
    tag = match.group(1) if match else level.upper()
    title = match.group(2) if match else rec["title"]

    panel_class = "intervention"
    if level in ("high", "critical"):
        panel_class += f" intervention-{level}"
    eyebrow_icon = _icon("siren", 15)
    steps = "".join(
        f'<div class="step"><span class="step-num">{i + 1:02d}</span>'
        f'<span class="step-text">{step}</span></div>'
        for i, step in enumerate(rec["steps"])
    )
    st.markdown(
        f"""
        <div class="{panel_class}">
            <div class="intervention-head">
                <div class="intervention-eyebrow">{eyebrow_icon} {tag}</div>
                <div class="intervention-title">{title}</div>
            </div>
            <div class="intervention-steps">{steps}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if triggered and delivery == "SENT":
        trigger_html = f'<span class="delivery-value good">YES</span>'
        status_html = f'<span class="delivery-value good">DELIVERED</span>'
        real_html = f'<span class="delivery-value good">YES</span>'
    elif triggered and delivery == "SIMULATED":
        trigger_html = f'<span class="delivery-value on">YES</span>'
        status_html = f'<span class="delivery-value dim">SIMULATED</span> <span class="demo-stamp">demo - not delivered</span>'
        real_html = f'<span class="delivery-value dim">NO</span>'
    elif triggered:
        trigger_html = f'<span class="delivery-value on">YES</span>'
        status_html = f'<span class="delivery-value on">{delivery}</span>'
        real_html = f'<span class="delivery-value dim">NO</span>'
    else:
        trigger_html = f'<span class="delivery-value dim">NO</span>'
        status_html = f'<span class="delivery-value dim">{delivery}</span>'
        real_html = f'<span class="delivery-value dim">-</span>'

    c_left, c_right = st.columns([3, 2], gap="large")
    with c_left:
        st.markdown(
            f"""
            <div class="delivery-card">
                <div class="delivery-title">Silent Intervention / Delivery</div>
                <div class="delivery-item"><span class="delivery-label">Triggered</span>{trigger_html}</div>
                <div class="delivery-item"><span class="delivery-label">Delivery status</span>{status_html}</div>
                <div class="delivery-item"><span class="delivery-label">Real delivery</span>{real_html}</div>
                <div class="delivery-item"><span class="delivery-label">Recipient(s)</span>
                    <span class="delivery-value dim">{contacts_text}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c_right:
        st.caption(
            "Evaluated by the real backend endpoint /api/silent-intervention for the latest snapshot. "
            "DEMO MODE: the alert is built and logged but NOT actually delivered - no SMS is sent."
        )

    if not triggered:
        st.markdown(
            f'<div class="notice notice-green">No intervention required at this risk level: '
            f"{inter.get('reason') or 'behavior is below the alert threshold.'}</div>",
            unsafe_allow_html=True,
        )
    elif delivery == "SENT":
        st.markdown(
            '<div class="notice notice-green">Alert delivered to trusted contacts.</div>',
            unsafe_allow_html=True,
        )
    elif delivery == "SIMULATED":
        st.markdown(
            f'<div class="notice notice-amber">Alert built but not delivered (simulated): '
            f"{inter.get('reason') or 'no real delivery channel configured.'}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="notice notice-red">Alert delivery failed or was blocked: '
            f"{inter.get('reason') or 'unknown delivery error.'}</div>",
            unsafe_allow_html=True,
        )

    if inter.get("message"):
        with st.expander("Alert message preview (SIMULATED - not delivered)"):
            st.code(inter["message"])


# ============================= CHARTS & TABLES =============================
def risk_evolution_chart(timeline: list) -> None:
    frame = pd.DataFrame(
        [
            {
                "Time (min)": row["t"],
                "Risk Score": row["score"],
                "ML %": row.get("ml_probability"),
                "Rule %": row.get("rule_contribution"),
                "level": row["level"],
            }
            for row in timeline
        ]
    )

    if _HAS_PLOTLY:
        colors = [LEVEL_COLORS.get(lv, "#6F6F6F") for lv in frame["level"]]
        fig = go.Figure()

        fig.add_hrect(y0=50, y1=74.9, fillcolor="rgba(217,164,65,0.03)", line_width=0)
        fig.add_hrect(y0=74.9, y1=100, fillcolor="rgba(224,28,43,0.04)", line_width=0)

        fig.add_trace(
            go.Scatter(
                x=frame["Time (min)"], y=frame["Risk Score"],
                name="Fused risk",
                mode="lines+markers",
                line=dict(color=CHART_COLORS["fused"], width=3, shape="spline"),
                marker=dict(size=11, color=colors, line=dict(color="#0E0D0D", width=2)),
                text=[
                    f"t={int(t)} min · {lv.upper()} · {s:.0f}/100"
                    for t, lv, s in zip(frame["Time (min)"], frame["level"], frame["Risk Score"])
                ],
                hovertemplate="%{text}<extra></extra>",
            )
        )
        if frame["Rule %"].notna().any():
            fig.add_trace(
                go.Scatter(
                    x=frame["Time (min)"], y=frame["Rule %"],
                    name="Rule evidence",
                    mode="lines+markers",
                    line=dict(color=CHART_COLORS["rules"], width=2, dash="dot"),
                    marker=dict(size=6, color=CHART_COLORS["rules"]),
                )
            )
        if frame["ML %"].notna().any():
            fig.add_trace(
                go.Scatter(
                    x=frame["Time (min)"], y=frame["ML %"],
                    name="ML probability",
                    mode="lines+markers",
                    line=dict(color=CHART_COLORS["ml"], width=2, dash="dash"),
                    marker=dict(size=6, color=CHART_COLORS["ml"]),
                )
            )
        fig.add_hline(
            y=49.9, line_dash="dash", line_color="rgba(217,164,65,.5)", line_width=1,
            annotation_text="HIGH ceiling · rule <50%", annotation_position="top left",
            annotation_font=dict(size=10, color="#D9A441"),
        )
        fig.add_hline(
            y=74.9, line_dash="dash", line_color="rgba(224,28,43,.55)", line_width=1,
            annotation_text="CRITICAL ceiling · rule <75%", annotation_position="top left",
            annotation_font=dict(size=10, color="#E01C2B"),
        )

        fig.update_layout(
            height=360,
            margin=dict(l=8, r=8, t=10, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#8A8A8A", size=12),
            xaxis=dict(
                title="Time in call (minutes)",
                gridcolor=CHART_COLORS["grid"],
                zeroline=False,
            ),
            yaxis=dict(
                title="Risk score",
                range=[0, 100],
                gridcolor=CHART_COLORS["grid"],
                zeroline=False,
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                bgcolor="rgba(0,0,0,0)",
                font=dict(color="#8A8A8A"),
            ),
            hovermode="closest",
        )
        st.plotly_chart(fig, width="stretch")
    else:
        fallback = frame[["Time (min)", "Risk Score"]].copy()
        fallback["HIGH ceiling (49.9)"] = 49.9
        fallback["CRITICAL ceiling (74.9)"] = 74.9
        st.line_chart(fallback.set_index("Time (min)"), height=340)

    st.caption(
        "The two dashed lines mark the gating ceilings. The fused score cannot rise above 49.9 while rule "
        "evidence is below 50%, nor above 74.9 while rule evidence is below 75%. Watch the Digital Arrest "
        "scenario: ML alone pushes toward 99.9% at stage 3, but the ceiling holds the score at 74.9 (HIGH) "
        "until the rule evidence crosses 75% at stage 4."
    )


def rule_evidence_table(last: dict) -> None:
    active = [item for item in last["safety_rule_contributions"] if item.get("active")]
    if not active:
        st.markdown(
            '<div class="notice notice-green">No explicit rule signals fired for this snapshot.</div>',
            unsafe_allow_html=True,
        )
        return

    df = pd.DataFrame(
        [
            {
                "Signal": item.get("reason", "Signal"),
                "Weight": float(item.get("weight", 0)) * 100,
                "Evidence type": "Counter-evidence (reduces risk)" if item.get("weight", 0) < 0 else "Risk signal",
            }
            for item in active
        ]
    )

    def _style_weight(value: float) -> str:
        if value < 0:
            return "color:#6FA877; font-weight:700;"
        if value >= 10:
            return "color:#E01C2B; font-weight:700;"
        return "color:#D9A441; font-weight:700;"

    styled = (
        df.style
        .map(lambda _v: "text-align:left;", subset=["Signal"])
        .map(_style_weight, subset=["Weight"])
        .format({"Weight": "{:.1f}%"})
        .hide(axis="index")
    )
    st.dataframe(styled, width="stretch")
    st.caption(
        f"Rule contribution (sum capped at 100%): {last['rule_contribution']:.1f}%. "
        "These are explicit, non-ML signals - each is gated by whether its telemetry was observed."
    )


def _behavior_signal_table(timeline: list) -> None:
    rows = []
    for row in timeline:
        signals = row["signals"]
        ml = row.get("ml_probability")
        rows.append(
            {
                "Time (min)": row["t"],
                "Event": row["label"],
                "Duration (min)": signals.get("call_duration_min", 0),
                "Unknown": "Yes" if signals.get("is_unknown_number") else "No",
                "Video": "Yes" if signals.get("is_video_call") else "No",
                "Outgoing Act.": round(signals.get("outgoing_activity_ratio", 0), 2),
                "Screen %": signals.get("screen_time_on_call_percent", 0),
                "App Switches": signals.get("num_app_switches", 0),
                "SMS/Social": (
                    "Yes" if signals.get("has_sms_activity") or signals.get("has_social_app_activity") else "No"
                ),
                "ML %": f"{ml:.0f}" if ml is not None else "-",
                "Rule %": f"{row['rule_contribution']:.0f}",
                "Ceiling": "Capped" if row.get("ml_cap_applied") else "-",
                "Risk": f"{row['score']:.0f}",
                "Level": row["level"].upper(),
            }
        )
    df = pd.DataFrame(rows)

    def _level_style(value: str) -> str:
        color = LEVEL_COLORS.get(str(value).lower(), "#6F6F6F")
        return f"color:{color}; font-weight:800;"

    def _ceiling_style(value: str) -> str:
        if value == "Capped":
            return "color:#D9A441; font-weight:700;"
        return "color:#6F6F6F;"

    styled = (
        df.style
        .map(lambda _v: "text-align:left;", subset=["Event"])
        .map(_level_style, subset=["Level"])
        .map(_ceiling_style, subset=["Ceiling"])
        .set_properties(subset=["Time (min)", "Duration (min)", "Outgoing Act.", "Screen %",
                                "App Switches", "ML %", "Rule %", "Risk"],
                        **{"text-align": "right", "font-family": "Consolas, monospace"})
        .hide(axis="index")
    )
    st.dataframe(styled, width="stretch")


def behavior_timeline_story(timeline: list) -> None:
    nodes = []
    for row in timeline:
        danger = " danger" if row["level"] in ("high", "critical") else ""
        nodes.append(
            f"""
            <div class="timeline-node{danger}">
                <div class="timeline-time">{row['t']} MIN</div>
                <div class="timeline-label">{row['label']}</div>
                <div class="timeline-note">{row['note']}</div>
            </div>
            """
        )
    final_level = timeline[-1]["level"]
    final_color = LEVEL_COLORS.get(final_level, "#6F6F6F")
    final_state = " danger" if final_level in ("high", "critical") else ""
    nodes.append(
        f"""
        <div class="timeline-node{final_state}">
            <div class="timeline-final" style="color:{final_color};">{final_level.upper()} RISK</div>
        </div>
        """
    )
    st.markdown(f'<div class="timeline">{"".join(nodes)}</div>', unsafe_allow_html=True)

    with st.expander("View full signal table"):
        _behavior_signal_table(timeline)
        for row in timeline:
            st.caption(f"**t={row['t']} min - {row['label']}:** {row['note']}")


def incidents_table(incidents: list) -> None:
    if not incidents:
        st.markdown(
            '<div class="notice notice-muted">No incidents recorded yet. Run a scenario to create one.</div>',
            unsafe_allow_html=True,
        )
        return

    df = pd.DataFrame(
        [
            {
                "Time": str(row.get("timestamp", ""))[:19].replace("T", " "),
                "Risk Level": str(row.get("risk_level", "")).upper(),
                "Score": float(row.get("risk_score") or 0),
                "Status": row.get("alert_status", ""),
            }
            for row in incidents
        ]
    )

    def _level_style(value: str) -> str:
        color = LEVEL_COLORS.get(str(value).lower(), "#6F6F6F")
        return f"color:{color}; font-weight:800;"

    def _status_style(value: str) -> str:
        status = str(value).lower()
        if status == "triggered":
            return "color:#E01C2B; font-weight:700;"
        if status == "monitor":
            return "color:#D9A441; font-weight:700;"
        if status == "none":
            return "color:#6FA877; font-weight:700;"
        return "color:#6F6F6F;"

    styled = (
        df.style
        .map(_level_style, subset=["Risk Level"])
        .map(_status_style, subset=["Status"])
        .set_properties(subset=["Score"], **{"text-align": "right", "font-family": "Consolas, monospace"})
        .format({"Score": "{:.0f}"})
        .hide(axis="index")
    )
    st.dataframe(styled, width="stretch")

    with st.expander("Incident details"):
        for row in incidents:
            explanation = row.get("explanation") or "No explanation recorded."
            st.caption(f"**{str(row.get('timestamp', ''))[:19].replace('T', ' ')}** - {explanation}")


# ============================= MAIN FLOW =============================
render_hero()

# ---------- 01 · TELEMETRY SOURCE ----------
_section(
    "01",
    "Telemetry Source",
    "Simulated inputs only - scripted scenarios or random snapshots from the Python "
    "AndroidDeviceSimulator. There is no real on-device capture yet.",
)
with st.container(border=True):
    telemetry_mode = st.radio(
        "Simulated telemetry mode",
        [
            "FULL TELEMETRY",
            "SIMULATED GAPS",
        ],
        index=0,
        horizontal=True,
        label_visibility="visible",
        key="telemetry_mode",
    )
    include_telemetry = telemetry_mode.startswith("FULL")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        run_scam = st.button("RUN DIGITAL ARREST SIMULATION", type="primary", width="stretch", key="run_scam")
    with c2:
        run_normal = st.button("RUN NORMAL CALL", width="stretch", key="run_normal")
    with c3:
        run_sim = st.button("RUN RANDOM SIMULATOR", width="stretch", key="run_sim")
    with c4:
        st.button("RESET", type="tertiary", width="stretch", key="reset_state", on_click=reset_state)

st.caption(
    "SIMULATED GAPS sends the snapshot WITHOUT device telemetry. The engine reports those fields as "
    "missing and never treats them as behavioral evidence - see the notice under the pipeline."
)

if run_scam:
    try:
        st.session_state.pop("intervention", None)
        st.session_state["timeline"] = run_scenario(DIGITAL_ARREST_SCENARIO, "Digital Arrest Scenario", include_telemetry)
        st.session_state["scenario_name"] = "Digital Arrest Scenario"
        st.session_state["include_telemetry"] = include_telemetry
    except Exception as exc:
        st.error(f"Backend call failed: {exc}. Start it with `python run.py`.")

if run_normal:
    try:
        st.session_state.pop("intervention", None)
        st.session_state["timeline"] = run_scenario(NORMAL_CALL_SCENARIO, "Normal Call Scenario", include_telemetry)
        st.session_state["scenario_name"] = "Normal Call Scenario"
        st.session_state["include_telemetry"] = include_telemetry
    except Exception as exc:
        st.error(f"Backend call failed: {exc}. Start it with `python run.py`.")

if run_sim:
    try:
        st.session_state.pop("intervention", None)
        timeline, kind = run_simulator_snapshot(include_telemetry)
        st.session_state["timeline"] = timeline
        st.session_state["scenario_name"] = f"AndroidDeviceSimulator - {'scam' if kind == 'scam' else 'normal'} snapshot"
        st.session_state["include_telemetry"] = include_telemetry
    except Exception as exc:
        st.error(f"Backend call failed: {exc}. Start it with `python run.py`.")

timeline = st.session_state.get("timeline")

if timeline:
    last = timeline[-1]
    level = last["level"]
    score = last["score"]
    include_telemetry = st.session_state.get("include_telemetry", True)
    scenario_name = st.session_state.get("scenario_name", "")

    if "intervention" not in st.session_state:
        try:
            st.session_state["intervention"] = trigger_intervention(last["signals"], include_telemetry)
        except Exception as exc:
            st.session_state["intervention"] = {"error": str(exc)}
    intervention = st.session_state.get("intervention")

    # ---------- 02 · LIVE RISK & DECISION PIPELINE ----------
    _section(
        "02",
        "Live Risk & Decision Pipeline",
        "The full pipeline for the latest snapshot - from telemetry to a gated, explainable risk level.",
    )
    risk_hero(level, score, intervention)
    st.caption(
        f"Latest assessment at t={last['t']} min · {scenario_name} · "
        f"model status: {last['model_status']}"
    )
    pipeline_strip(last, intervention)

    # ---------- 03 · RISK EVOLUTION ----------
    _section(
        "03",
        "Risk Evolution",
        "How the gated fused score develops across the scored snapshots of this run.",
    )
    risk_evolution_chart(timeline)
    c_low, c_high = st.columns(2)
    c_low.metric("Start of call", f"{timeline[0]['score']:.0f} / 100")
    c_high.metric("End of call", f"{timeline[-1]['score']:.0f} / 100")

    # ---------- 04 · DETECTION REASONING ----------
    _section(
        "04",
        "Why LUMINA Flagged This Call",
        "The explicit signals behind the current risk level - understandable in seconds.",
    )
    if level == "low":
        st.markdown(
            '<div class="notice notice-green">No significant risk indicators - this matches normal call '
            "behavior. None of the digital-arrest signals crossed the detection threshold.</div>",
            unsafe_allow_html=True,
        )
    else:
        render_detection_factors(last["factors"])
        st.caption(
            f"{len(last['factors'])} headline risk signal(s) shown (capped at 3 by the API). "
            "Full rule evidence below."
        )
    st.markdown("**Rule evidence (explicit safety signals)**")
    rule_evidence_table(last)
    st.markdown(
        f'<div class="notice notice-muted">{last["explanation"]}</div>',
        unsafe_allow_html=True,
    )

    # ---------- 05 · INTERVENTION & DELIVERY ----------
    _section(
        "05",
        "Intervention & Alert Delivery",
        "Recommended trusted-contact actions at this risk level, and the real delivery status from the backend.",
    )
    if intervention and "error" not in intervention:
        render_intervention(intervention, level)
    elif intervention:
        st.error(f"Intervention check failed: {intervention['error']}")

    # ---------- 06 · BEHAVIOR TIMELINE ----------
    _section(
        "06",
        "Behavior Timeline",
        "The story of the call as the risk escalated - snapshot by snapshot.",
    )
    behavior_timeline_story(timeline)

    # ---------- 07 · INCIDENT REPORT ----------
    _section(
        "07",
        "Incident Report",
        "A ReportLab FIR-style PDF generated for the latest snapshot via the real backend endpoint.",
    )
    st.markdown(
        f"""
        <div class="report-panel">
            <div>
                <div class="report-eyebrow">Incident Report</div>
                <div class="report-title">LUMINA Digital Arrest Scam Report</div>
                <div class="report-sub">Official-style investigation artifact for the latest assessed snapshot.</div>
            </div>
            <div class="report-logo logo-tile">{_logo_img(160)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Generate Incident Report (PDF)", width="stretch", key="gen_report"):
        try:
            with st.spinner("Generating PDF report..."):
                response = requests.post(
                    f"{API_BASE}/api/generate-report",
                    json=_to_body(last["signals"], include_telemetry),
                    timeout=30,
                )
                response.raise_for_status()
                meta = response.json()
                filename = os.path.basename(meta["pdf_path"])
                pdf_response = requests.get(f"{API_BASE}/api/download-report/{filename}", timeout=30)
                pdf_response.raise_for_status()
                st.session_state["report_bytes"] = pdf_response.content
                st.session_state["report_filename"] = filename
                st.session_state["report_meta"] = meta
        except Exception as exc:
            st.error(f"Report generation failed: {exc}")

    if st.session_state.get("report_bytes"):
        meta = st.session_state["report_meta"]
        st.markdown(
            '<div class="notice notice-green">Report generated - '
            f"Risk {meta.get('risk_score')}/100 ({str(meta.get('risk_level', '')).upper()})</div>",
            unsafe_allow_html=True,
        )
        st.download_button(
            "Download Incident Report (PDF)",
            data=st.session_state["report_bytes"],
            file_name=st.session_state["report_filename"],
            mime="application/pdf",
            width="stretch",
            key="download_report",
        )
else:
    st.markdown(
        f"""
        <div class="empty-hero">
            <div class="empty-seal">{_seal_svg(340)}</div>
            <div class="empty-watermark"><img src="{_logo_watermark_uri()}" alt=""/></div>
            <div class="empty-brand">
                <div class="logo-tile">{_logo_img(210)}</div>
                <div class="empty-title">LUMINA is standing by</div>
                <div class="empty-sub">Run a simulation to analyze an escalating digital-arrest call, a normal
                call, or a random snapshot. Every input is SIMULATED - the engine and API responses are real.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    mode_c1, mode_c2, mode_c3 = st.columns(3)
    with mode_c1:
        st.markdown(
            f"""
            <div class="mode-card">
                <div class="mode-card-title">{_icon("handcuffs", 16)} Digital Arrest Scenario</div>
                <div class="mode-card-sub">Signals accumulate over a ~2.5 hour call: unknown caller, video
                intimidation, authority claims, then full isolation. Watch the gating ceiling hold the score
                at 74.9 until rule evidence crosses 75%.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with mode_c2:
        st.markdown(
            f"""
            <div class="mode-card">
                <div class="mode-card-title">{_icon("phone", 16)} Normal Call Scenario</div>
                <div class="mode-card-sub">A short, known caller with normal device activity stays at low risk
                throughout - a controlled baseline for comparison.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with mode_c3:
        st.markdown(
            f"""
            <div class="mode-card">
                <div class="mode-card-title">{_icon("magnifier", 16)} Random Simulator Snapshot</div>
                <div class="mode-card-sub">A single random snapshot from the Python AndroidDeviceSimulator
                (scam or normal profile). Toggle Simulated Gaps to see missing telemetry reported honestly.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.divider()

# ---------- RECENT INCIDENTS ----------
_section(
    "08",
    "Recent Incidents",
    "Recent risk assessments recorded by the backend. Every /api/score call logs one entry.",
)
try:
    incidents_response = requests.get(f"{API_BASE}/api/incidents?limit=50", timeout=10)
    incidents_response.raise_for_status()
    incidents = incidents_response.json().get("incidents", [])
    st.caption(f"{len(incidents)} most recent assessment(s) logged by the backend.")
    incidents_table(incidents)
except Exception:
    st.error("Could not reach the backend. Start it with `python run.py`.")

st.divider()
st.markdown(
    f"""
    <div class="footer">
        <div class="footer-brand">LUMINA<span class="dot">.</span></div>
        <div class="footer-line"><b>HELPLINE 1930</b> &nbsp;·&nbsp; REPORT AT CYBERCRIME.GOV.IN</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "LUMINA is a research prototype. All telemetry shown is SIMULATED (scripted scenarios / Python "
    "AndroidDeviceSimulator); no real device data is captured. All alerts are evaluated and logged by the "
    "backend but NOT delivered in demo mode - no SMS is sent."
)