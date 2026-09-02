# tests/test_dashboard_app.py
"""Streamlit AppTest verification for the LUMINA dashboard.

Runs dashboard/app.py through streamlit.testing.v1.AppTest with the HTTP
backend mocked, so no live FastAPI server is required. These tests cover the
presentation layer only:

- the honest empty state (no simulated scenario buttons, no device radio),
- model evidence is read from the saved benchmark JSON (not hardcoded),
- the incidents table renders backend records,
- no exceptions are raised while rendering.
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


def _score_response(payload):
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
        "missing_telemetry": [],
        "model_status": "available",
    }


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
def patched_api(monkeypatch):
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
        raise AssertionError(f"unexpected GET: {url}")

    def fake_post(url, *args, **kwargs):
        raise AssertionError(f"unexpected POST: {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)
    return fake_get


def _new_app():
    return AppTest.from_file(APP_PATH, default_timeout=60)


def _markdown_text(at):
    return "\n".join(md.value for md in at.markdown)


def _assert_no_exceptions(at):
    assert not at.exception, [e.value for e in at.exception]


def test_empty_state_renders_hero_and_honest_overview(patched_api):
    at = _new_app()
    at.run()
    _assert_no_exceptions(at)

    text = _markdown_text(at)
    assert "lumina-hero" in text
    assert "SYSTEM ONLINE" in text
    assert "AWAITING ON-DEVICE DATA" in text
    assert "Awaiting Real Device Data" in text
    assert "No active call is being monitored" in text

    assert "Digital Arrest Scenario" not in text
    assert "Normal Call Scenario" not in text
    assert "Random Simulator Snapshot" not in text
    assert "AndroidDeviceSimulator" not in text

    labels = [b.label for b in at.button]
    assert not any("RUN" in label for label in labels)
    assert not any("Simulate" in label for label in labels)
    assert not any("SIMULATION" in label for label in labels)

    assert not at.radio, [r.value for r in at.radio]
    assert not at.metric
    assert not at.get("plotly_chart")


def test_model_evidence_reads_truthful_benchmark_values(patched_api):
    at = _new_app()
    at.run()
    _assert_no_exceptions(at)

    text = _markdown_text(at)
    assert "91.04% acc" in text          # calibrated accuracy (0.9104) from audit_metrics.json
    assert "0.9330 AUC" in text          # calibrated roc_auc (0.9330)
    assert "0.4671 ROC-AUC" in text      # stress overall roc_auc (0.4671)
    assert "19.49%" in text              # short-call recall (0.1949) from stress per_slice
    assert "32%" in text                 # dominant feature importance (~0.3217)

    # The old hardcoded claims must be gone.
    assert "99.88%" not in text
    assert "~60%" not in text
    assert "0.824" not in text
    assert "0.53%" not in text
    assert "1.00 AUC" not in text


def test_incidents_table_shows_backend_records(patched_api):
    at = _new_app()
    at.run()
    _assert_no_exceptions(at)
    caption_text = "\n".join(c.value for c in at.caption)
    assert "1 most recent assessment" in caption_text
    assert "No incidents recorded yet" not in caption_text