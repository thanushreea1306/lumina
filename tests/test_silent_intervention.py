# tests/test_silent_intervention.py
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.panic_trigger import PanicTrigger


@pytest.fixture(autouse=True)
def no_real_delivery_configured(monkeypatch):
    monkeypatch.delenv("LUMINA_TRUSTED_CONTACTS", raising=False)
    monkeypatch.setenv("LUMINA_ALERT_MODE", "demo")


@pytest.fixture
def client():
    return TestClient(app)


def _low_call():
    return {
        "call_duration_min": 5,
        "is_unknown_number": 0,
        "is_video_call": 0,
        "hour_of_day": 14,
        "caller_call_history": 10,
        "outgoing_activity_ratio": 0.8,
        "day_of_week": 2,
    }


def _critical_call():
    return {
        "call_duration_min": 180,
        "is_unknown_number": 1,
        "is_video_call": 1,
        "hour_of_day": 10,
        "caller_call_history": 0,
        "outgoing_activity_ratio": 0.02,
        "day_of_week": 2,
        "extra_telemetry": {
            "screen_time_on_call_percent": 95,
            "num_app_switches": 0,
            "num_home_presses": 0,
            "has_sms_activity": 0,
            "has_social_app_activity": 0,
            "location_change": 5,
            "screen_brightness": 90,
            "screen_on_continuous_hours": 6,
        },
    }


# ---------- unit level ----------


def test_low_risk_never_triggers_intervention():
    result = PanicTrigger().trigger_silent_intervention(
        "Meena", 0.0, [], risk_level="low"
    )
    assert result["intervention_triggered"] is False
    assert result["delivered"] is False
    assert result["delivery_status"] == "NOT_TRIGGERED"
    assert result["alert_sent_to"] == []
    assert result["message"] is None


def test_medium_risk_never_triggers_intervention():
    result = PanicTrigger().trigger_silent_intervention(
        "Meena", 35.0, ["signal"], risk_level="medium"
    )
    assert result["intervention_triggered"] is False
    assert result["delivery_status"] == "NOT_TRIGGERED"


def test_high_risk_simulated_when_no_contacts_configured():
    result = PanicTrigger().trigger_silent_intervention(
        "Meena", 67.0, ["long call"], risk_level="high"
    )
    assert result["intervention_triggered"] is True
    assert result["delivered"] is False
    assert result["delivery_status"] == "SIMULATED"
    assert result["alert_sent_to"] == []
    assert "LUMINA SAFETY ALERT" in result["message"]
    assert "1930" in result["message"]


def test_critical_keeps_human_in_the_loop_message():
    result = PanicTrigger().trigger_silent_intervention(
        "Meena", 95.0, ["arrest threat", "urgency"], risk_level="critical"
    )
    assert result["intervention_triggered"] is True
    assert "Meena" in result["message"]
    assert "CRITICAL" in result["message"]
    assert "dial 1930" in result["message"]
    assert "arrest threat" in result["message"]


def test_no_fake_recipient_presented_as_delivered_contact():
    result = PanicTrigger().trigger_silent_intervention(
        "Meena", 95.0, ["signal"], risk_level="critical"
    )
    assert result["alert_sent_to"] == []
    assert result["delivered"] is False
    assert "trusted_contact_1" not in json.dumps(result)
    assert "trusted_contact_2" not in json.dumps(result)


def test_configured_contacts_listed_but_marked_simulated(monkeypatch):
    monkeypatch.setenv("LUMINA_TRUSTED_CONTACTS", "+910000000000, +910000000001")
    result = PanicTrigger().trigger_silent_intervention(
        "Meena", 95.0, ["signal"], risk_level="high"
    )
    assert result["intervention_triggered"] is True
    assert result["alert_sent_to"] == ["+910000000000", "+910000000001"]
    assert result["delivered"] is False
    assert result["delivery_status"] == "SIMULATED"


# ---------- API level ----------


def test_api_low_risk_never_claims_intervention(client):
    response = client.post(
        "/api/silent-intervention", json=_low_call(), params={"victim_name": "Ada"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intervention_triggered"] is False
    assert body["delivered"] is False
    assert body["delivery_status"] == "NOT_TRIGGERED"
    assert body["alert_sent_to"] == []


def test_api_high_risk_intervention_is_explicitly_simulated(client):
    response = client.post(
        "/api/silent-intervention", json=_critical_call(), params={"victim_name": "Ada"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intervention_triggered"] is True
    assert body["risk_level"] in {"high", "critical"}
    assert body["delivered"] is False
    assert body["delivery_status"] == "SIMULATED"
    assert "trusted_contact_1" not in json.dumps(body)
    assert "trusted_contact_2" not in json.dumps(body)
    assert "LUMINA SAFETY ALERT" in body["message"]
