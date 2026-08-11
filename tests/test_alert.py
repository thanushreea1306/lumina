# tests/test_alert.py
import pytest

from app.services import alert
from app.services.alert import AlertGuard, reset_abuse_guard, send_family_alert

FEATURES = {
    "call_duration_min": 120,
    "is_unknown_number": 1,
    "is_video_call": 1,
    "hour_of_day": 14,
}


@pytest.fixture(autouse=True)
def fresh_guard():
    reset_abuse_guard()
    yield
    reset_abuse_guard()


def test_demo_mode_returns_simulated_delivery():
    result = send_family_alert(
        elder_name="Meena",
        risk_level="high",
        duration=120,
        features=FEATURES,
        now=1000.0,
    )
    assert result["delivery_status"] == "SIMULATED DELIVERY"
    assert result["alert"] is not None
    assert "Meena" in result["alert"]
    assert result["recipient"] == "simulated_recipient"
    assert "timestamp" in result
    assert "reason" in result
    assert result["reason"].startswith("demo mode")


def test_cooldown_blocks_second_alert_for_same_victim():
    alert._guard = AlertGuard(cooldown_seconds=60, max_alerts_per_window=100)

    first = send_family_alert(
        elder_name="Meena", risk_level="high", duration=120,
        features=FEATURES, incident_id=1, now=1000.0,
    )
    assert first["delivery_status"] == "SIMULATED DELIVERY"

    second = send_family_alert(
        elder_name="Meena", risk_level="high", duration=120,
        features=FEATURES, incident_id=2, now=1000.5,
    )
    assert second["delivery_status"] == "BLOCKED"
    assert second["reason"] == "cooldown"
    assert second["alert"] is None

    after_window = send_family_alert(
        elder_name="Meena", risk_level="high", duration=120,
        features=FEATURES, incident_id=3, now=1000.0 + 60.0,
    )
    assert after_window["delivery_status"] == "SIMULATED DELIVERY"


def test_rate_limiting_blocks_after_max_alerts_per_window():
    alert._guard = AlertGuard(cooldown_seconds=0, max_alerts_per_window=3, window_seconds=60)

    for i in range(3):
        result = send_family_alert(
            elder_name="Ramesh", risk_level="high", duration=120,
            features=FEATURES, incident_id=100 + i, now=2000.0 + i,
        )
        assert result["delivery_status"] == "SIMULATED DELIVERY"

    blocked = send_family_alert(
        elder_name="Ramesh", risk_level="high", duration=120,
        features=FEATURES, incident_id=103, now=2000.0 + 3,
    )
    assert blocked["delivery_status"] == "BLOCKED"
    assert blocked["reason"] == "rate limit"

    after_window = send_family_alert(
        elder_name="Ramesh", risk_level="high", duration=120,
        features=FEATURES, incident_id=104, now=2000.0 + 60.0,
    )
    assert after_window["delivery_status"] == "SIMULATED DELIVERY"


def test_duplicate_incident_is_suppressed():
    first = send_family_alert(
        elder_name="Sita", risk_level="medium", duration=30,
        features=FEATURES, incident_id=999, now=3000.0,
    )
    assert first["delivery_status"] == "SIMULATED DELIVERY"

    dup = send_family_alert(
        elder_name="Sita", risk_level="high", duration=30,
        features=FEATURES, incident_id=999, now=3061.0,
    )
    assert dup["delivery_status"] == "BLOCKED"
    assert dup["reason"] == "duplicate incident"
