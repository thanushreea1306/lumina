# tests/test_fusion_gating.py
"""Regression tests for gated ML+safety-rule fusion and counter-evidence rule."""

import pytest

from app.core.risk_engine import RiskEngine


def _known_long_payload(duration):
    return {
        "call_duration_min": duration,
        "is_unknown_number": 0,
        "is_video_call": 0,
        "hour_of_day": 14,
        "caller_call_history": 20,
        "outgoing_activity_ratio": 0.7,
        "screen_time_on_call_percent": 30,
        "num_app_switches": 12,
        "num_home_presses": 6,
        "has_sms_activity": True,
        "has_social_app_activity": True,
        "location_change": 200,
        "screen_brightness": 40,
        "screen_on_continuous_hours": 1.0,
        "persistence_hours": 0.5,
    }


def _known_video_long():
    return {
        "call_duration_min": 120,
        "is_unknown_number": 0,
        "is_video_call": 1,
        "hour_of_day": 14,
        "caller_call_history": 20,
        "outgoing_activity_ratio": 0.7,
    }


def _da_stage(stage):
    stages = {
        1: {
            "call_duration_min": 2, "is_unknown_number": 1, "is_video_call": 0,
            "hour_of_day": 10, "caller_call_history": 0, "outgoing_activity_ratio": 0.60,
            "screen_time_on_call_percent": 30, "num_app_switches": 5, "num_home_presses": 4,
            "has_sms_activity": True, "has_social_app_activity": True, "location_change": 120,
            "screen_brightness": 35, "screen_on_continuous_hours": 0, "persistence_hours": 0,
        },
        2: {
            "call_duration_min": 25, "is_unknown_number": 1, "is_video_call": 1,
            "hour_of_day": 10, "caller_call_history": 0, "outgoing_activity_ratio": 0.45,
            "screen_time_on_call_percent": 55, "num_app_switches": 3, "num_home_presses": 2,
            "has_sms_activity": True, "has_social_app_activity": True, "location_change": 60,
            "screen_brightness": 50, "screen_on_continuous_hours": 0, "persistence_hours": 0,
        },
        3: {
            "call_duration_min": 55, "is_unknown_number": 1, "is_video_call": 1,
            "hour_of_day": 10, "caller_call_history": 0, "outgoing_activity_ratio": 0.25,
            "screen_time_on_call_percent": 70, "num_app_switches": 1, "num_home_presses": 1,
            "has_sms_activity": False, "has_social_app_activity": False, "location_change": 25,
            "screen_brightness": 70, "screen_on_continuous_hours": 0, "persistence_hours": 0,
        },
        4: {
            "call_duration_min": 95, "is_unknown_number": 1, "is_video_call": 1,
            "hour_of_day": 10, "caller_call_history": 0, "outgoing_activity_ratio": 0.10,
            "screen_time_on_call_percent": 90, "num_app_switches": 0, "num_home_presses": 0,
            "has_sms_activity": False, "has_social_app_activity": False, "location_change": 10,
            "screen_brightness": 90, "screen_on_continuous_hours": 2, "persistence_hours": 1,
        },
        5: {
            "call_duration_min": 165, "is_unknown_number": 1, "is_video_call": 1,
            "hour_of_day": 10, "caller_call_history": 0, "outgoing_activity_ratio": 0.03,
            "screen_time_on_call_percent": 98, "num_app_switches": 0, "num_home_presses": 0,
            "has_sms_activity": False, "has_social_app_activity": False, "location_change": 2,
            "screen_brightness": 100, "screen_on_continuous_hours": 5, "persistence_hours": 3,
        },
    }
    return stages[stage]


def _full_isolation_fingerprint():
    return {
        "call_duration_min": 180, "is_unknown_number": 1, "is_video_call": 1,
        "hour_of_day": 10, "caller_call_history": 0, "outgoing_activity_ratio": 0.02,
        "screen_time_on_call_percent": 98, "num_app_switches": 0, "num_home_presses": 0,
        "has_sms_activity": False, "has_social_app_activity": False, "location_change": 2,
        "screen_brightness": 95, "screen_on_continuous_hours": 6, "persistence_hours": 4,
    }


# ---------- A. Known legitimate long calls ----------

@pytest.mark.parametrize("duration", [65, 75, 90, 120])
def test_known_long_call_with_normal_activity_is_not_high_or_critical(duration):
    engine = RiskEngine()
    result = engine.score(_known_long_payload(duration))
    assert result["risk_level"] not in {"high", "critical"}


# ---------- B. ML escalation ceiling ----------

def test_ml_cannot_manufacture_high_when_rules_below_50():
    engine = RiskEngine()
    result = engine.score({
        "call_duration_min": 120,
        "is_unknown_number": 0,
        "is_video_call": 0,
        "hour_of_day": 14,
        "caller_call_history": 20,
        "outgoing_activity_ratio": 0.7,
        "has_social_app_activity": False,
        "num_app_switches": 5,
    })
    assert result["rule_contribution"] < 50
    assert result["risk_level"] not in {"high", "critical"}
    assert result["risk_score"] < 50


def test_ml_cannot_manufacture_critical_when_rules_below_75():
    engine = RiskEngine()
    result = engine.score({
        "call_duration_min": 165,
        "is_unknown_number": 1,
        "is_video_call": 1,
        "hour_of_day": 10,
        "caller_call_history": 2,
        "outgoing_activity_ratio": 0.6,
        "has_social_app_activity": False,
    })
    assert 50 <= result["rule_contribution"] < 75
    assert result["risk_level"] in ("high", "medium")
    assert result["risk_score"] <= 74.9


def test_rules_at_or_above_75_can_remain_critical():
    engine = RiskEngine()
    result = engine.score(_full_isolation_fingerprint())
    assert result["rule_contribution"] >= 75
    assert result["risk_level"] == "critical"
    assert result["risk_score"] >= 75


# ---------- C. Counter-evidence ----------

def test_counter_evidence_reduces_rule_score():
    engine = RiskEngine()
    with_social = engine.score({**_known_video_long(), "has_social_app_activity": True})
    absent_social = engine.score(_known_video_long())
    assert absent_social["rule_contribution"] - with_social["rule_contribution"] == pytest.approx(15.0)
    reasons = [c["reason"] for c in with_social["safety_rule_contributions"] if c.get("active")]
    assert any("Counter-evidence" in r for r in reasons)


def test_counter_evidence_not_for_unknown_caller():
    engine = RiskEngine()
    result = engine.score({
        **_known_video_long(),
        "is_unknown_number": 1,
        "has_social_app_activity": True,
    })
    reasons = [c["reason"] for c in result["safety_rule_contributions"] if c.get("active")]
    assert not any("Counter-evidence" in r for r in reasons)
    assert result["rule_contribution"] == pytest.approx(50.0)


def test_counter_evidence_not_for_low_outgoing():
    engine = RiskEngine()
    result = engine.score({
        **_known_video_long(),
        "outgoing_activity_ratio": 0.3,
        "has_social_app_activity": True,
    })
    reasons = [c["reason"] for c in result["safety_rule_contributions"] if c.get("active")]
    assert not any("Counter-evidence" in r for r in reasons)


def test_counter_evidence_not_when_social_missing():
    engine = RiskEngine()
    result = engine.score(_known_video_long())
    reasons = [c["reason"] for c in result["safety_rule_contributions"] if c.get("active")]
    assert not any("Counter-evidence" in r for r in reasons)
    assert "has_social_app_activity" in result["missing_telemetry"]


def test_counter_evidence_not_when_social_explicit_false():
    engine = RiskEngine()
    result = engine.score({**_known_video_long(), "has_social_app_activity": False})
    reasons = [c["reason"] for c in result["safety_rule_contributions"] if c.get("active")]
    assert not any("Counter-evidence" in r for r in reasons)
    assert "has_social_app_activity" not in result["missing_telemetry"]


# ---------- D. Digital-arrest preservation ----------

def test_da_early_stages_stay_low_or_medium():
    engine = RiskEngine()
    for stage in (1, 2):
        result = engine.score(_da_stage(stage))
        assert result["risk_level"] in {"low", "medium"}


def test_da_stage3_remains_high():
    engine = RiskEngine()
    result = engine.score(_da_stage(3))
    assert result["risk_level"] == "high"


def test_da_stages_4_and_5_remain_critical():
    engine = RiskEngine()
    for stage in (4, 5):
        result = engine.score(_da_stage(stage))
        assert result["risk_level"] == "critical"


def test_full_isolation_fingerprint_remains_critical():
    engine = RiskEngine()
    result = engine.score(_full_isolation_fingerprint())
    assert result["risk_level"] == "critical"


# ---------- E. Existing safety behavior ----------

def test_null_social_telemetry_treated_as_missing_for_counter_evidence():
    engine = RiskEngine()
    result = engine.score({**_known_video_long(), "has_social_app_activity": None})
    assert "has_social_app_activity" in result["missing_telemetry"]
    reasons = [c["reason"] for c in result["safety_rule_contributions"] if c.get("active")]
    assert not any("Counter-evidence" in r for r in reasons)


def test_ml_unavailable_fallback_stays_rules_only(monkeypatch):
    engine = RiskEngine()
    engine.load()
    monkeypatch.setattr(engine, "_ml_probability", lambda features: None)
    result = engine.score({
        "call_duration_min": 120,
        "is_unknown_number": 1,
        "is_video_call": 1,
    })
    assert result["ml_probability"] is None
    assert result["risk_score"] == result["rule_contribution"]
    assert result["ml_cap_applied"] is None


# ---------- /api/send-alert delivery semantics ----------

@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _alert_payload():
    return {
        "call_duration_min": 10,
        "is_unknown_number": 0,
        "is_video_call": 0,
        "hour_of_day": 12,
        "caller_call_history": 5,
        "outgoing_activity_ratio": 0.6,
        "day_of_week": 2,
    }


def test_api_send_alert_simulated_is_not_delivered(client):
    response = client.post(
        "/api/send-alert",
        json=_alert_payload(),
        params={"elder_name": "Simulated Ada"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["delivery_status"] == "SIMULATED DELIVERY"
    assert body["alert_sent"] is False
    assert body["delivered"] is False


@pytest.mark.parametrize("delivery_status", ["SIMULATED DELIVERY", "FAILED", "BLOCKED"])
def test_api_send_alert_never_claims_delivery_without_sent(client, monkeypatch, delivery_status):
    import app.main as main

    def fake_send(**kwargs):
        return {
            "delivery_status": delivery_status,
            "alert": None,
            "recipient": "test",
            "reason": "not actually sent",
            "timestamp": "",
        }

    monkeypatch.setattr(main, "send_family_alert", fake_send)
    response = client.post(
        "/api/send-alert",
        json=_alert_payload(),
        params={"elder_name": f"Ada-{delivery_status}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["delivery_status"] == delivery_status
    assert body["alert_sent"] is False
    assert body["delivered"] is False


def test_api_send_alert_delivered_only_when_sent(client, monkeypatch):
    import app.main as main

    def fake_send(**kwargs):
        return {
            "delivery_status": "SENT",
            "alert": "message",
            "recipient": "test",
            "reason": "sent via twilio",
            "timestamp": "",
        }

    monkeypatch.setattr(main, "send_family_alert", fake_send)
    response = client.post(
        "/api/send-alert",
        json=_alert_payload(),
        params={"elder_name": "Sent Ada"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["delivery_status"] == "SENT"
    assert body["alert_sent"] is True
    assert body["delivered"] is True
