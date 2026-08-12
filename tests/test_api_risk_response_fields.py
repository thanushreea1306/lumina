# tests/test_api_risk_response_fields.py
"""Regression tests for the additive RiskResponse fields exposed by /api/score.

rule_contribution, ml_cap_applied, safety_rule_contributions and
missing_telemetry are computed by the engine and were previously stripped by
response_model. These tests verify the API surfaces them unchanged, matches the
engine result for the same payload, and preserves every pre-existing field.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.risk_engine import RiskEngine

BASELINE_PAYLOAD = {
    "call_duration_min": 55,
    "is_unknown_number": 1,
    "is_video_call": 1,
    "hour_of_day": 10,
    "caller_call_history": 0,
    "outgoing_activity_ratio": 0.25,
    "day_of_week": 2,
    "extra_telemetry": {
        "screen_time_on_call_percent": 70,
        "num_app_switches": 1,
        "num_home_presses": 1,
        "has_sms_activity": 0,
        "has_social_app_activity": 0,
        "location_change": 25,
        "screen_brightness": 70,
        "screen_on_continuous_hours": 0,
        "persistence_hours": 0,
    },
}

PRE_EXISTING_FIELDS = {
    "risk_score",
    "risk_level",
    "top_factors",
    "features",
    "alert_message",
    "model_used",
    "explanation",
    "model_status",
    "error_detail",
    "ml_probability",
}

NEW_FIELDS = {
    "rule_contribution",
    "ml_cap_applied",
    "safety_rule_contributions",
    "missing_telemetry",
}


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def _score_response(client, payload):
    response = client.post("/api/score", json=payload)
    assert response.status_code == 200
    return response.json()


def test_api_score_exposes_all_engine_fields(client):
    body = _score_response(client, BASELINE_PAYLOAD)
    assert PRE_EXISTING_FIELDS <= set(body.keys())
    assert NEW_FIELDS <= set(body.keys())
    assert isinstance(body["rule_contribution"], float)
    assert body["ml_cap_applied"] is None or isinstance(body["ml_cap_applied"], str)
    assert isinstance(body["safety_rule_contributions"], list)
    assert isinstance(body["missing_telemetry"], list)


def test_api_score_fields_match_engine(client):
    engine_payload = {k: v for k, v in BASELINE_PAYLOAD.items() if k != "extra_telemetry"}
    engine_payload.update(BASELINE_PAYLOAD["extra_telemetry"])
    engine_result = RiskEngine().score(dict(engine_payload))

    body = _score_response(client, BASELINE_PAYLOAD)
    assert body["risk_score"] == engine_result["risk_score"]
    assert body["risk_level"] == engine_result["risk_level"]
    assert body["ml_probability"] == engine_result["ml_probability"]
    assert body["rule_contribution"] == engine_result["rule_contribution"]
    assert body["ml_cap_applied"] == engine_result["ml_cap_applied"]
    assert body["missing_telemetry"] == engine_result["missing_telemetry"]
    assert body["safety_rule_contributions"] == engine_result["safety_rule_contributions"]


def test_api_surfaces_missing_telemetry(client):
    body = _score_response(client, {
        "call_duration_min": 55,
        "is_unknown_number": 1,
        "is_video_call": 1,
        "hour_of_day": 10,
        "caller_call_history": 0,
        "outgoing_activity_ratio": 0.25,
        "day_of_week": 2,
    })
    expected = {
        "screen_time_on_call_percent",
        "num_app_switches",
        "num_home_presses",
        "has_sms_activity",
        "has_social_app_activity",
        "location_change",
        "screen_brightness",
        "screen_on_continuous_hours",
        "persistence_hours",
    }
    assert set(body["missing_telemetry"]) == expected
    active = [item for item in body["safety_rule_contributions"] if item.get("active")]
    assert len(active) == 2
    assert any("Unknown caller" in item["reason"] for item in active)
    assert any("Video call" in item["reason"] for item in active)


def test_api_rule_only_fallback_when_ml_unavailable(client, monkeypatch):
    import app.main as main

    monkeypatch.setattr(main.risk_engine, "_ml_probability", lambda features: None)
    body = _score_response(client, BASELINE_PAYLOAD)
    assert body["ml_probability"] is None
    assert body["risk_score"] == body["rule_contribution"]
    assert body["ml_cap_applied"] is None
