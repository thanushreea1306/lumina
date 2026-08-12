# dashboard/app.py
import os
import random
from dataclasses import asdict

import pandas as pd
import requests
import streamlit as st

API_BASE = os.getenv("LUMINA_API_BASE", "http://localhost:8000")

st.set_page_config(
    page_title="LUMINA - Digital Arrest Protection",
    layout="wide",
)

LEVEL_COLORS = {
    "critical": "#d32f2f",
    "high": "#f57c00",
    "medium": "#f9a825",
    "low": "#2e7d32",
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

st.markdown(
    """
    <style>
        .main-header {
            font-size: 2.2rem;
            font-weight: 800;
            color: #1a237e;
            text-align: center;
            margin-bottom: 0.2rem;
        }
        .main-sub {
            text-align: center;
            color: #64748b;
            font-size: 1rem;
            margin-bottom: 1rem;
        }
        .risk-banner {
            border-radius: 14px;
            padding: 18px 24px;
            text-align: center;
            border: 2px solid;
        }
        .risk-banner .risk-label {
            font-size: 0.85rem;
            letter-spacing: 2px;
            font-weight: 700;
        }
        .risk-banner .risk-level {
            font-size: 3.2rem;
            font-weight: 800;
            line-height: 1.1;
        }
        .risk-banner .risk-score {
            font-size: 1.6rem;
            font-weight: 700;
        }
        .section-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #1a237e;
            margin-top: 0.4rem;
        }
        .status-box {
            border-radius: 10px;
            padding: 14px 18px;
            border-left: 6px solid;
            margin: 6px 0;
        }
        .pipe {
            border-radius: 10px;
            padding: 12px 14px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            min-height: 150px;
        }
        .pipe-title {
            font-size: 0.7rem;
            letter-spacing: 1px;
            font-weight: 700;
            color: #64748b;
            margin-bottom: 4px;
        }
        .pipe-value {
            font-size: 1.35rem;
            font-weight: 700;
            color: #1a237e;
            margin: 2px 0 4px 0;
        }
        .pipe-sub {
            font-size: 0.78rem;
            color: #475569;
            line-height: 1.4;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


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


def risk_banner(level: str, score: float) -> str:
    color = LEVEL_COLORS.get(level, "#64748b")
    return f"""
    <div class="risk-banner" style="background:{color}1a; border-color:{color};">
        <div class="risk-label" style="color:{color};">CURRENT RISK LEVEL</div>
        <div class="risk-level" style="color:{color};">{level.upper()}</div>
        <div class="risk-score" style="color:{color};">{score:.0f} / 100</div>
    </div>
    """


def pipe_box(title: str, value: str, sub: str) -> str:
    return f"""
    <div class="pipe">
        <div class="pipe-title">{title}</div>
        <div class="pipe-value">{value}</div>
        <div class="pipe-sub">{sub}</div>
    </div>
    """


def pipeline_strip(snap: dict) -> None:
    st.markdown('<div class="section-title">HOW THE DECISION WAS MADE</div>', unsafe_allow_html=True)
    st.caption(
        "Live pipeline for the latest snapshot: telemetry is expanded into features, the ML model "
        "corroborates call behavior, explicit safety rules add evidence, then the two are fused and "
        "gated before a risk level is declared."
    )

    ml_value = f"{snap['ml_probability']:.1f}%" if snap.get("ml_probability") is not None else "not in use"
    ml_sub = (
        f"XGBoost on the 11-feature call-behavior schema (model status: {snap['model_status']}). "
        "Telemetry fields are excluded from ML inference."
        if snap.get("ml_probability") is not None
        else f"XGBoost not served (model status: {snap['model_status']}). No ML probability is fabricated."
    )
    active_count = sum(1 for item in snap["safety_rule_contributions"] if item.get("active"))
    rule_sub = (
        f"{active_count} explicit signal(s) firing. Gated by is_missing_* flags: missing telemetry "
        "is never counted as evidence."
    )
    cap_sub = (
        "Ceiling applied by the gating rule (see warning below)."
        if snap.get("ml_cap_applied")
        else "No ceiling applied - fused score reflects ML + rule evidence."
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(
            pipe_box(
                "1 · TELEMETRY + FEATURES",
                f"{29 - len(snap['missing_telemetry'])}/29 present",
                f"{len(snap['missing_telemetry'])} telemetry field(s) unavailable for this snapshot. "
                "Call-behavior features always present.",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(pipe_box("2 · ML CORROBORATION", ml_value, ml_sub), unsafe_allow_html=True)
    with c3:
        st.markdown(
            pipe_box(
                "3 · SAFETY RULES",
                f"{snap['rule_contribution']:.1f}%",
                rule_sub,
            ),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            pipe_box(
                "4 · GATED FUSION",
                f"{snap['score']:.1f}%",
                cap_sub,
            ),
            unsafe_allow_html=True,
        )
    with c5:
        color = LEVEL_COLORS.get(snap["level"], "#64748b")
        st.markdown(
            f"""<div class="pipe" style="border-color:{color}; background:{color}14;">
                <div class="pipe-title" style="color:{color};">5 · RISK LEVEL</div>
                <div class="pipe-value" style="color:{color};">{snap['level'].upper()}</div>
                <div class="pipe-sub">Derived from the gated fused score.</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.caption(
        "Fusion rule: risk score = 50% x ML probability + 50% x rule contribution, then gated - the score "
        "cannot cross 49.9 unless rule evidence is at least 50%, and cannot cross 74.9 unless rule evidence "
        "is at least 75%. ML alone never decides the risk level."
    )
    if snap.get("ml_cap_applied"):
        st.warning(snap["ml_cap_applied"])
    if snap["missing_telemetry"]:
        labels = [TELEMETRY_LABELS.get(name, name) for name in snap["missing_telemetry"]]
        st.info(
            f"Telemetry unavailable for: {', '.join(labels)}. "
            "Missing fields are NOT treated as behavioral signals (no fabricated zero/false evidence)."
        )


def render_intervention(inter: dict) -> None:
    st.markdown('<div class="section-title">INTERVENTION & ALERT DELIVERY STATUS</div>', unsafe_allow_html=True)
    st.caption(
        "Evaluated by the real backend endpoint /api/silent-intervention for the latest snapshot. "
        "DEMO MODE: the alert is built and logged but NOT actually delivered - no SMS is sent."
    )

    triggered = bool(inter.get("intervention_triggered"))
    delivery = str(inter.get("delivery_status", ""))
    delivered = bool(inter.get("delivered"))

    c1, c2, c3 = st.columns(3)
    c1.metric("Intervention triggered", "YES" if triggered else "NO")
    c2.metric("Delivery status", delivery)
    c3.metric("Delivered (real)", "YES" if delivered else "NO")

    if not triggered:
        st.info(inter.get("reason") or "No intervention required at this risk level.")
    elif delivery == "SENT":
        st.success("Alert delivered to trusted contacts.")
    elif delivery == "SIMULATED":
        st.warning(inter.get("reason") or "Alert built but not delivered (simulated).")
    else:
        st.error(inter.get("reason") or "Alert delivery failed or was blocked.")

    contacts = inter.get("alert_sent_to") or []
    st.markdown(
        f"**Alert recipient(s):** {', '.join(contacts) if contacts else 'none configured (LUMINA_TRUSTED_CONTACTS not set)'}"
    )
    if inter.get("message"):
        with st.expander("Alert message preview (SIMULATED - not delivered)"):
            st.code(inter["message"])


st.markdown('<div class="main-header">LUMINA</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="main-sub">Digital Arrest Protection - detecting when someone is trapped inside a scam call, before they ask for help.</div>',
    unsafe_allow_html=True,
)

# ============ 1 · TELEMETRY SOURCE ============
st.markdown('<div class="section-title">1 · TELEMETRY SOURCE</div>', unsafe_allow_html=True)
st.caption(
    "SIMULATED telemetry: scripted scenarios or random snapshots from the Python AndroidDeviceSimulator. "
    "There is no real on-device capture yet - the Android app is a skeleton. All inputs below are generated, "
    "not read from a real phone."
)
telemetry_mode = st.radio(
    "Telemetry completeness",
    [
        "Full simulated telemetry (all 9 device fields)",
        "Simulated gaps (device telemetry unavailable)",
    ],
    index=0,
    horizontal=True,
    label_visibility="visible",
)
include_telemetry = telemetry_mode.startswith("Full")

c1, c2, c3, c4 = st.columns(4)
with c1:
    run_scam = st.button("RUN DIGITAL ARREST SCENARIO", type="primary", width='stretch')
with c2:
    run_normal = st.button("RUN NORMAL CALL SCENARIO", width='stretch')
with c3:
    run_sim = st.button("RANDOM SIMULATOR SNAPSHOT", width='stretch')
with c4:
    if st.button("Reset", width='stretch'):
        reset_state()
        st.rerun()

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

    if "intervention" not in st.session_state:
        try:
            st.session_state["intervention"] = trigger_intervention(last["signals"], include_telemetry)
        except Exception as exc:
            st.session_state["intervention"] = {"error": str(exc)}

    st.markdown('<div class="section-title">2 · LIVE PIPELINE</div>', unsafe_allow_html=True)
    pipeline_strip(last)
    st.caption(f"Latest assessment at t={last['t']} min - {st.session_state.get('scenario_name', '')}")

    # ============ 3 · CURRENT RISK ============
    st.markdown('<div class="section-title">3 · CURRENT RISK</div>', unsafe_allow_html=True)
    st.markdown(risk_banner(level, score), unsafe_allow_html=True)

    # ============ 4 · WHY WAS THIS DETECTED ============
    st.markdown('<div class="section-title">4 · WHY WAS THIS DETECTED?</div>', unsafe_allow_html=True)
    if level == "low":
        st.success("No significant risk indicators - this matches normal call behavior.")
        st.caption("For this call, none of the digital-arrest signals (long duration, unknown caller, video intimidation, isolation) crossed the detection threshold.")
    else:
        for factor in last["factors"][:6]:
            st.markdown(f"- **{factor}**")
        st.caption(f"{len(last['factors'])} headline risk signal(s) shown (capped at 3 by the API). Full rule evidence below.")

    # ============ 5 · RULE EVIDENCE ============
    st.markdown('<div class="section-title">5 · RULE EVIDENCE (EXPLICIT SAFETY SIGNALS)</div>', unsafe_allow_html=True)
    active = [item for item in last["safety_rule_contributions"] if item.get("active")]
    if active:
        rules_df = pd.DataFrame(
            [
                {
                    "Signal": item.get("reason", "Signal"),
                    "Weight": f"{item.get('weight', 0) * 100:.1f}%",
                    "Evidence type": "Counter-evidence (reduces risk)" if item.get("weight", 0) < 0 else "Risk signal",
                }
                for item in active
            ]
        )
        st.dataframe(rules_df, width='stretch', hide_index=True)
        st.caption(
            f"Rule contribution (sum capped at 100%): {last['rule_contribution']:.1f}%. "
            "These are explicit, non-ML signals - each is gated by whether its telemetry was observed."
        )
    else:
        st.info("No explicit rule signals fired for this snapshot.")

    # ============ 6 · WHAT SHOULD HAPPEN ============
    st.markdown('<div class="section-title">6 · WHAT SHOULD HAPPEN?</div>', unsafe_allow_html=True)
    rec = INTERVENTIONS[level]
    st.markdown(f"**{rec['title']}**")
    for step in rec["steps"]:
        st.markdown(f"- {step}")

    # ============ 7 · INTERVENTION & DELIVERY ============
    intervention = st.session_state.get("intervention")
    if intervention and "error" not in intervention:
        render_intervention(intervention)
    elif intervention:
        st.error(f"Intervention check failed: {intervention['error']}")

    # ============ 8 · RISK EVOLUTION ============
    st.markdown('<div class="section-title">8 · RISK EVOLUTION</div>', unsafe_allow_html=True)
    evolution = pd.DataFrame(
        [{"Time (min)": row["t"], "Risk Score": row["score"]} for row in timeline]
    )
    evolution["HIGH ceiling (49.9)"] = 49.9
    evolution["CRITICAL ceiling (74.9)"] = 74.9
    st.line_chart(evolution.set_index("Time (min)"), height=300)
    st.caption(
        "The two flat lines mark the gating ceilings. The fused score cannot rise above 49.9 while rule "
        "evidence is below 50%, nor above 74.9 while rule evidence is below 75%. Watch the Digital Arrest "
        "scenario: ML alone pushes toward 99.9% at stage 3, but the ceiling holds the score at 74.9 (HIGH) "
        "until the rule evidence crosses 75% at stage 4."
    )
    c_low, c_high = st.columns(2)
    c_low.metric("Start of call", f"{timeline[0]['score']:.0f} / 100")
    c_high.metric("End of call", f"{timeline[-1]['score']:.0f} / 100")

    # ============ 9 · BEHAVIOR TIMELINE ============
    st.markdown('<div class="section-title">9 · BEHAVIOR TIMELINE</div>', unsafe_allow_html=True)
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
    st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
    for row in timeline:
        st.caption(f"**t={row['t']} min - {row['label']}:** {row['note']}")

    # ============ 10 · EXPLANATION ============
    st.markdown('<div class="section-title">10 · ENGINE EXPLANATION</div>', unsafe_allow_html=True)
    st.info(last["explanation"])
    st.markdown(
        f"Risk moved from **{timeline[0]['score']:.0f}/100** at t={timeline[0]['t']} min "
        f"to **{timeline[-1]['score']:.0f}/100** at t={timeline[-1]['t']} min across "
        f"{len(timeline)} scored snapshot(s)."
    )
    st.write(last["alert_message"])

    # ============ 11 · INCIDENT REPORT (PDF) ============
    st.markdown('<div class="section-title">11 · INCIDENT REPORT</div>', unsafe_allow_html=True)
    if st.button("Generate Incident Report (PDF)", width='stretch'):
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
        st.success(
            f"Report generated - Risk {meta.get('risk_score')}/100 "
            f"({meta.get('risk_level', '').upper()})"
        )
        st.download_button(
            "Download Incident Report (PDF)",
            data=st.session_state["report_bytes"],
            file_name=st.session_state["report_filename"],
            mime="application/pdf",
            width='stretch',
        )
else:
    st.info("Run a scenario to analyze an escalating digital-arrest call, a normal call, or a random simulator snapshot.")
    st.markdown(
        """
        **What you can run:**
        - **Digital Arrest Scenario** - signals accumulate over a ~2.5 hour call (unknown caller, then video intimidation, then authority claims, then full isolation), and the risk score escalates as each signal stacks up. Watch the gating ceiling hold the score at 74.9 until rule evidence crosses 75%.
        - **Normal Call Scenario** - a short, known caller with normal device activity stays at low risk throughout.
        - **Random Simulator Snapshot** - a single random snapshot generated by the Python AndroidDeviceSimulator (scam or normal profile).
        - Toggle **"Simulated gaps"** to see how missing telemetry is handled honestly: absent device fields are reported and never treated as behavioral signals.
        """
    )

st.divider()

# ============ HISTORICAL INCIDENTS ============
st.markdown('<div class="section-title">HISTORICAL INCIDENTS</div>', unsafe_allow_html=True)
st.caption("Recent risk assessments recorded in SQLite by the backend. Every /api/score call logs one entry.")
try:
    incidents_response = requests.get(f"{API_BASE}/api/incidents?limit=50", timeout=10)
    incidents_response.raise_for_status()
    incidents = incidents_response.json().get("incidents", [])
    if incidents:
        incidents_df = pd.DataFrame(
            [
                {
                    "Time": row.get("timestamp", "")[:19].replace("T", " "),
                    "Risk Score": row.get("risk_score"),
                    "Level": str(row.get("risk_level", "")).upper(),
                    "Alert Status": row.get("alert_status", ""),
                    "Explanation": row.get("explanation", ""),
                }
                for row in incidents
            ]
        )
        st.dataframe(incidents_df, width='stretch', hide_index=True)
    else:
        st.info("No incidents recorded yet. Run a scenario to create one.")
except Exception:
    st.error("Could not reach the backend. Start it with `python run.py`.")

st.divider()
st.markdown(
    "Helpline: 1930 | Report at [cybercrime.gov.in](https://cybercrime.gov.in)"
)
st.caption(
    "LUMINA is a research prototype. All telemetry shown is SIMULATED (scripted scenarios / Python "
    "AndroidDeviceSimulator); no real device data is captured. All alerts are evaluated and logged by the "
    "backend but NOT delivered in demo mode - no SMS is sent."
)
