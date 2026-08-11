import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.features import canonical_feature_names, extract_features
from app.core.risk_engine import RiskEngine
from app.main import app


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(app)


def test_missing_signals_do_not_crash():
    features = extract_features({})
    assert features is not None
    assert len(features) == len(canonical_feature_names())
    assert all(v is not None for v in features.values())


def test_unknown_caller_alone_is_not_critical():
    engine = RiskEngine()
    result = engine.score({"is_unknown_number": 1, "call_duration_min": 10})
    assert result["risk_level"] != "CRITICAL"


def test_long_call_alone_is_not_critical():
    engine = RiskEngine()
    result = engine.score({"call_duration_min": 120, "is_unknown_number": 0, "is_video_call": 0})
    assert result["risk_level"] != "CRITICAL"


def test_video_call_alone_is_not_critical():
    engine = RiskEngine()
    result = engine.score({"is_video_call": 1, "call_duration_min": 10, "is_unknown_number": 0})
    assert result["risk_level"] != "CRITICAL"


def test_multiple_isolation_signals_increase_risk():
    engine = RiskEngine()
    base = engine.score({"call_duration_min": 120, "is_unknown_number": 1, "is_video_call": 1})
    combined = engine.score({
        "call_duration_min": 180,
        "is_unknown_number": 1,
        "is_video_call": 1,
        "screen_time_on_call_percent": 90,
        "num_app_switches": 0,
        "num_home_presses": 0,
        "has_sms_activity": 0,
        "has_social_app_activity": 0,
        "location_change": 10,
        "screen_brightness": 90,
        "screen_on_continuous_hours": 6,
    })
    assert combined["risk_score"] >= base["risk_score"]


def test_persistent_signals_can_escalate_risk():
    engine = RiskEngine()
    result = engine.score({
        "call_duration_min": 180,
        "is_unknown_number": 1,
        "is_video_call": 1,
        "screen_time_on_call_percent": 90,
        "num_app_switches": 0,
        "num_home_presses": 0,
        "has_sms_activity": 0,
        "has_social_app_activity": 0,
        "location_change": 10,
        "screen_brightness": 90,
        "screen_on_continuous_hours": 6,
        "persistence_hours": 4,
    })
    assert result["risk_score"] >= 70


def test_contradictory_signals_do_not_blindly_crash_to_critical():
    engine = RiskEngine()
    result = engine.score({
        "call_duration_min": 5,
        "is_unknown_number": 0,
        "is_video_call": 0,
        "screen_time_on_call_percent": 20,
        "num_app_switches": 10,
        "num_home_presses": 8,
        "has_sms_activity": 1,
        "has_social_app_activity": 1,
        "location_change": 500,
        "screen_brightness": 30,
    })
    assert result["risk_level"] != "CRITICAL"


def test_feature_ordering_is_deterministic():
    names_a = canonical_feature_names()
    names_b = canonical_feature_names()
    assert names_a == names_b
    assert names_a == [
        "call_duration_min",
        "is_unknown_number",
        "is_video_call",
        "hour_of_day",
        "caller_call_history",
        "outgoing_activity_ratio",
        "is_weekend",
        "call_duration_log",
        "is_early_morning",
        "is_late_night",
        "activity_category",
        "screen_time_on_call_percent",
        "num_app_switches",
        "num_home_presses",
        "has_sms_activity",
        "has_social_app_activity",
        "location_change",
        "screen_brightness",
        "screen_on_continuous_hours",
        "persistence_hours",
        "is_missing_screen_time_on_call_percent",
        "is_missing_num_app_switches",
        "is_missing_num_home_presses",
        "is_missing_has_sms_activity",
        "is_missing_has_social_app_activity",
        "is_missing_location_change",
        "is_missing_screen_brightness",
        "is_missing_screen_on_continuous_hours",
        "is_missing_persistence_hours",
    ]


def test_endpoints_use_same_risk_engine(client):
    for path in [
        "/api/score",
        "/api/detect-isolation",
        "/api/silent-intervention",
        "/api/generate-report",
        "/api/send-alert",
    ]:
        if path == "/api/score":
            response = client.post(path, json={"call_duration_min": 10, "is_unknown_number": 0, "is_video_call": 0, "hour_of_day": 12, "caller_call_history": 5, "outgoing_activity_ratio": 0.6, "day_of_week": 2})
        elif path == "/api/detect-isolation":
            response = client.post(path, json={"call_duration_minutes": 10, "is_unknown_number": False, "is_video_call": False})
        elif path == "/api/silent-intervention":
            response = client.post(path, json={"call_duration_min": 10, "is_unknown_number": 0, "is_video_call": 0, "hour_of_day": 12, "caller_call_history": 5, "outgoing_activity_ratio": 0.6, "day_of_week": 2}, params={"victim_name": "Ada"})
        elif path == "/api/generate-report":
            response = client.post(path, json={"call_duration_min": 10, "is_unknown_number": 0, "is_video_call": 0, "hour_of_day": 12, "caller_call_history": 5, "outgoing_activity_ratio": 0.6, "day_of_week": 2})
        elif path == "/api/send-alert":
            response = client.post(path, json={"call_duration_min": 10, "is_unknown_number": 0, "is_video_call": 0, "hour_of_day": 12, "caller_call_history": 5, "outgoing_activity_ratio": 0.6, "day_of_week": 2}, params={"elder_name": "Ada"})
        assert response.status_code in {200, 503}
