# tests/test_dashboard_app.py
"""Streamlit AppTest verification for the redesigned LUMINA dashboard.

Runs dashboard/app.py through streamlit.testing.v1.AppTest with the HTTP
backend mocked, so no live FastAPI server is required. These tests only cover
the presentation layer: the app renders the hero/empty state, full vs. gapped
telemetry is sent correctly, running a scenario renders the pipeline, risk,
intervention, timeline, incident table, and PDF-report flow - all without
raising exceptions.
"""

import sys
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

APP_PATH = str(ROOT / "dashboard" / "app.py")

TELEMETRY_FIELDS = [
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


def _score_response(payload):
    has_telemetry = "extra_telemetry" in payload
    missing = [] if has_telemetry else list(TELEMETRY_FIELDS)
    return {
        "risk_score": 81.2,
        "risk_level": "critical",
        "top_factors": [
            "Digital arrest indicators (isolation + persistence)",
            "Video call intimidation (weight 18%)",
            "Long call with unknown caller (threshold exceeded)",
            "Excessive screen-on time (weight 12%)",
        ],
        "alert_message": "LUMINA ALERT: A family member may be trapped in a digital-arrest call.",
        "explanation": "Rule contribution 80% crossed the 75% critical threshold.",
        "ml_probability": 92.0,
        "rule_contribution": 80.0,
        "ml_cap_applied": None,
        "safety_rule_contributions": [
            {"reason": "Unknown caller", "weight": 0.30, "active": True},
            {"reason": "Video call intimidation", "weight": 0.25, "active": True},
            {"reason": "Known family number", "weight": -0.2, "active": True},
        ],
        "missing_telemetry": missing,
        "model_status": "available",
    }


def _intervention_response(payload):
    body = _score_response(payload)
    body.update({
        "intervention_triggered": True,
        "delivery_status": "SIMULATED",
        "delivered": False,
        "alert_sent_to": ["+91-9999999999"],
        "reason": "demo mode - no real SMS delivery channel",
        "message": "LUMINA ALERT: ... (SIMULATED - not delivered)",
    })
    return body


class _FakeResponse:
    def __init__(self, status_code=200, json_body=None, content=None):
        self.status_code = status_code
        self._json = json_body
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json


@pytest.fixture
def patched_api(monkeypatch, captured_payloads):
    """Mock the HTTP backend so the dashboard runs fully offline."""

    def fake_get(url, *args, **kwargs):
        if url.endswith("/health"):
            return _FakeResponse(json_body={"model_status": "available", "status": "ok"})
        if "/api/incidents" in url:
            return _FakeResponse(json_body={
                "incidents": [{
                    "timestamp": "2026-08-12T10:30:00",
                    "risk_level": "critical",
                    "risk_score": 81.2,
                    "alert_status": "triggered",
                    "explanation": "Rule contribution 80% crossed the 75% critical threshold.",
                }]
            })
        if "/api/download-report/" in url:
            return _FakeResponse(content=b"%PDF-1.4\nfake-report")
        raise AssertionError(f"unexpected GET: {url}")

    def fake_post(url, *args, **kwargs):
        payload = kwargs.get("json", {})
        captured_payloads.append(payload)
        if url.endswith("/api/score"):
            return _FakeResponse(json_body=_score_response(payload))
        if url.endswith("/api/silent-intervention"):
            return _FakeResponse(json_body=_intervention_response(payload))
        if url.endswith("/api/generate-report"):
            return _FakeResponse(json_body={
                "pdf_path": "reports/lumina_incident.pdf",
                "risk_score": 81.2,
                "risk_level": "critical",
                "filename": "lumina_incident.pdf",
            })
        raise AssertionError(f"unexpected POST: {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)
    return fake_get


@pytest.fixture
def captured_payloads():
    return []


def _new_app():
    return AppTest.from_file(APP_PATH, default_timeout=60)


def _markdown_text(at):
    return "\n".join(md.value for md in at.markdown)


def _assert_no_exceptions(at):
    assert not at.exception, [e.value for e in at.exception]


def test_empty_state_renders_hero_modes_and_logo(patched_api):
    at = _new_app()
    at.run()
    _assert_no_exceptions(at)

    text = _markdown_text(at)
    assert "lumina-hero" in text
    assert "data:image/png;base64," in text
    assert "SYSTEM ONLINE" in text
    assert "LUMINA is standing by" not in text
    assert "Digital Arrest Scenario" in text
    assert "Normal Call Scenario" in text
    assert "Random Simulator Snapshot" in text

    labels = [b.label for b in at.button]
    assert "RUN DIGITAL ARREST SIMULATION" in labels
    assert "RESET" in labels
    assert not at.get("plotly_chart")
    assert not at.metric


def test_full_telemetry_sends_device_fields(patched_api, captured_payloads):
    at = _new_app()
    at.run()
    assert at.radio[0].value == "FULL TELEMETRY"
    at.button(key="run_scam").click()
    at.run()
    _assert_no_exceptions(at)

    score_payloads = [p for p in captured_payloads if "call_duration_min" in p]
    assert score_payloads
    assert "extra_telemetry" in score_payloads[0]
    assert set(TELEMETRY_FIELDS) <= set(score_payloads[0]["extra_telemetry"])


def test_simulated_gaps_omits_telemetry_and_reports_missing(patched_api, captured_payloads):
    at = _new_app()
    at.run()
    at.radio[0].set_value("SIMULATED GAPS")
    at.run()
    at.button(key="run_normal").click()
    at.run()
    _assert_no_exceptions(at)

    score_payloads = [p for p in captured_payloads if "call_duration_min" in p]
    assert score_payloads
    assert "extra_telemetry" not in score_payloads[0]

    text = _markdown_text(at)
    assert "Missing telemetry" in text
    assert "20/29" in text


def test_scenario_renders_pipeline_risk_intervention_and_timeline(patched_api):
    at = _new_app()
    at.run()
    at.button(key="run_scam").click()
    at.run()
    _assert_no_exceptions(at)

    text = _markdown_text(at)
    assert "pipe-row" in text
    assert "CRITICAL" in text
    assert "risk-hero critical" in text
    assert "INTERVENTION TRIGGERED" in text
    assert "IMMEDIATE FAMILY INTERVENTION REQUIRED" in text
    assert "Silent Intervention / Delivery" in text
    assert "timeline" in text

    assert at.metric
    assert at.get("plotly_chart")
    assert at.get("dataframe")


def test_incident_report_generation_flow(patched_api):
    at = _new_app()
    at.run()
    at.button(key="run_scam").click()
    at.run()
    at.button(key="gen_report").click()
    at.run()
    _assert_no_exceptions(at)

    download = at.get("download_button")
    assert len(download) == 1
    text = _markdown_text(at)
    assert "Report generated" in text


def test_incidents_table_shows_backend_records(patched_api):
    at = _new_app()
    at.run()
    _assert_no_exceptions(at)
    caption_text = "\n".join(c.value for c in at.caption)
    assert "1 most recent assessment" in caption_text
    assert "No incidents recorded yet" not in caption_text
