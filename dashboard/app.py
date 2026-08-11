# dashboard/app.py
import os

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

ALERT_STATUS = {
    "critical": ("[CRITICAL] ALERT TRIGGERED", "A family alert would be sent to trusted contacts immediately. High-risk digital-arrest pattern confirmed."),
    "high": ("[HIGH] ALERT TRIGGERED", "A family alert would be sent to trusted contacts. Closely monitor the call."),
    "medium": ("[MEDIUM] MONITOR", "Risk indicators present but no alert fired - keep monitoring."),
    "low": ("[LOW] NO ALERT", "No alert needed. Call behavior looks normal."),
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
    </style>
    """,
    unsafe_allow_html=True,
)


def _to_body(signals: dict) -> dict:
    body = {key: signals.get(key, 0) for key in CALL_KEYS}
    body["day_of_week"] = signals.get("day_of_week", 2)
    body["extra_telemetry"] = {key: signals.get(key, 0) for key in TELEMETRY_KEYS}
    return body


def score_snapshot(signals: dict) -> dict:
    response = requests.post(f"{API_BASE}/api/score", json=_to_body(signals), timeout=30)
    response.raise_for_status()
    return response.json()


def run_scenario(scenario, name: str) -> list:
    timeline = []
    progress = st.progress(0, text=f"Running {name}...")
    for i, snap in enumerate(scenario):
        progress.progress((i + 1) / len(scenario), text=f"Scoring: {snap['label']}")
        result = score_snapshot(snap["signals"])
        timeline.append(
            {
                "t": snap["t"],
                "label": snap["label"],
                "note": snap["note"],
                "signals": snap["signals"],
                "score": result["risk_score"],
                "level": result["risk_level"],
                "factors": result.get("top_factors", []),
                "alert_message": result.get("alert_message", ""),
                "explanation": result.get("explanation", ""),
            }
        )
    progress.empty()
    return timeline


def reset_state():
    for key in ["timeline", "scenario_name", "report_bytes", "report_filename", "report_meta"]:
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


st.markdown('<div class="main-header">LUMINA</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="main-sub">Digital Arrest Protection - detecting when someone is trapped inside a scam call, before they ask for help.</div>',
    unsafe_allow_html=True,
)

# ============ SCENARIO CONTROLS ============
c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    run_scam = st.button("RUN DIGITAL ARREST SCENARIO", type="primary", width='stretch')
with c2:
    run_normal = st.button("RUN NORMAL CALL SCENARIO", width='stretch')
with c3:
    if st.button("Reset", width='stretch'):
        reset_state()
        st.rerun()

if run_scam:
    try:
        st.session_state["timeline"] = run_scenario(DIGITAL_ARREST_SCENARIO, "Digital Arrest Scenario")
        st.session_state["scenario_name"] = "Digital Arrest Scenario"
    except Exception as exc:
        st.error(f"Backend call failed: {exc}. Start it with `python run.py`.")

if run_normal:
    try:
        st.session_state["timeline"] = run_scenario(NORMAL_CALL_SCENARIO, "Normal Call Scenario")
        st.session_state["scenario_name"] = "Normal Call Scenario"
    except Exception as exc:
        st.error(f"Backend call failed: {exc}. Start it with `python run.py`.")

timeline = st.session_state.get("timeline")

# ============ TOP: CURRENT RISK ============
if timeline:
    last = timeline[-1]
    level = last["level"]
    score = last["score"]

    st.markdown(risk_banner(level, score), unsafe_allow_html=True)
    st.caption(f"Latest assessment at {last['t']} min - {st.session_state.get('scenario_name', '')}")

    # ============ WHY WAS THIS DETECTED? ============
    st.markdown('<div class="section-title">WHY WAS THIS DETECTED?</div>', unsafe_allow_html=True)
    if level == "low":
        st.success("No significant risk indicators - this matches normal call behavior.")
        st.caption("For this call, none of the digital-arrest signals (long duration, unknown caller, video intimidation, isolation) crossed the detection threshold.")
    else:
        for factor in last["factors"][:6]:
            st.markdown(f"- **{factor}**")
        st.caption(f"{len(last['factors'])} risk signal(s) active at this moment.")

    # ============ WHAT SHOULD HAPPEN? ============
    st.markdown('<div class="section-title">WHAT SHOULD HAPPEN?</div>', unsafe_allow_html=True)
    rec = INTERVENTIONS[level]
    st.markdown(f"**{rec['title']}**")
    for step in rec["steps"]:
        st.markdown(f"- {step}")

    # ============ RISK EVOLUTION ============
    st.markdown('<div class="section-title">RISK EVOLUTION</div>', unsafe_allow_html=True)
    evolution = pd.DataFrame(
        [{"Time (min)": row["t"], "Risk Score": row["score"]} for row in timeline]
    )
    st.line_chart(evolution.set_index("Time (min)"), height=300)
    c_low, c_high = st.columns(2)
    c_low.metric("Start of call", f"{timeline[0]['score']:.0f} / 100")
    c_high.metric("End of call", f"{timeline[-1]['score']:.0f} / 100")

    # ============ BEHAVIOR TIMELINE ============
    st.markdown('<div class="section-title">BEHAVIOR TIMELINE</div>', unsafe_allow_html=True)
    rows = []
    for row in timeline:
        signals = row["signals"]
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
                "Risk": f"{row['score']:.0f}",
                "Level": row["level"].upper(),
            }
        )
    st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
    for row in timeline:
        st.caption(f"**t={row['t']} min - {row['label']}:** {row['note']}")

    # ============ EXPLANATION ============
    st.markdown('<div class="section-title">EXPLANATION</div>', unsafe_allow_html=True)
    st.info(last["explanation"])
    st.markdown(
        f"Risk moved from **{timeline[0]['score']:.0f}/100** at t={timeline[0]['t']} min "
        f"to **{timeline[-1]['score']:.0f}/100** at t={timeline[-1]['t']} min across "
        f"{len(timeline)} scored snapshots."
    )
    st.write(last["alert_message"])

    # ============ ALERT STATUS ============
    st.markdown('<div class="section-title">ALERT STATUS</div>', unsafe_allow_html=True)
    status_title, status_desc = ALERT_STATUS[level]
    if level in ("critical", "high"):
        st.error(f"{status_title} - {status_desc}")
    elif level == "medium":
        st.warning(f"{status_title} - {status_desc}")
    else:
        st.success(f"{status_title} - {status_desc}")

    # ============ INCIDENT REPORT (PDF) ============
    st.markdown('<div class="section-title">INCIDENT REPORT</div>', unsafe_allow_html=True)
    if st.button("Generate Incident Report (PDF)", width='stretch'):
        try:
            with st.spinner("Generating PDF report..."):
                response = requests.post(
                    f"{API_BASE}/api/generate-report",
                    json=_to_body(last["signals"]),
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
    st.info("Run a scenario to analyze an escalating digital-arrest call or a normal call.")
    st.markdown(
        """
        **What the scenarios show:**
        - **Digital Arrest Scenario** - signals accumulate over a ~2.5 hour call (unknown caller, then video intimidation, then authority claims, then full isolation), and the risk score escalates as each signal stacks up.
        - **Normal Call Scenario** - a short, known caller with normal device activity stays at low risk throughout.
        """
    )

st.divider()

# ============ HISTORICAL INCIDENTS ============
st.markdown('<div class="section-title">HISTORICAL INCIDENTS</div>', unsafe_allow_html=True)
st.caption("Recent risk assessments recorded in SQLite by the backend.")
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
    "Helpline: 1930 | Report at [cybercrime.gov.in](https://cybercrime.gov.in) | "
    "LUMINA is a research prototype - demo-mode alerts are simulated, not real SMS."
)
