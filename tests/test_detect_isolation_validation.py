# tests/test_detect_isolation_validation.py
"""API-boundary validation for POST /api/detect-isolation.

The endpoint body is validated by IsolationTelemetryRequest: malformed
payloads and wrong types must be rejected with a clean FastAPI 422 response,
never a raw 500 from deep feature/rule code. Explicit null stays missing
telemetry; explicit 0 / False stay real observations.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.risk_engine import RiskEngine
from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


FULL_VALID = {
    "call_duration_minutes": 120,
    "is_unknown_number": True,
    "is_video_call": True,
    "hour_of_day": 22,
    "caller_call_history": 0,
    "outgoing_activity_ratio": 0.1,
    "day_of_week": 3,
    "is_weekend": False,
    "screen_time_on_call_percent": 95,
    "num_app_switches": 0,
    "num_home_presses": 0,
    "has_sms_activity": False,
    "has_social_app_activity": False,
    "location_change": 2,
    "screen_brightness": 100,
    "screen_on_continuous_hours": 5,
    "persistence_hours": 3,
}

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


def _post(client, payload):
    return client.post("/api/detect-isolation", json=payload)


# ---- valid payloads -------------------------------------------------------

def test_valid_full_payload_200(client):
    response = _post(client, FULL_VALID)
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "CRITICAL"
    assert body["isolation_score"] >= 90
    assert body["model_status"] == "available"


def test_minimal_payload_200(client):
    response = _post(client, {
        "call_duration_minutes": 10,
        "is_unknown_number": False,
        "is_video_call": False,
    })
    assert response.status_code == 200
    assert response.json()["risk_level"] == "LOW"


def test_empty_payload_200(client):
    response = _post(client, {})
    assert response.status_code == 200
    assert response.json()["risk_level"] == "LOW"


def test_call_duration_min_alias_accepted(client):
    minutes = _post(client, {"call_duration_minutes": 10}).json()["isolation_score"]
    alias = _post(client, {"call_duration_min": 10}).json()["isolation_score"]
    assert alias == minutes


# ---- optional / null / zero / positive -----------------------------------

def test_missing_optional_telemetry_is_missing(client):
    response = _post(client, {
        "call_duration_minutes": 10,
        "is_unknown_number": False,
        "is_video_call": False,
    })
    assert response.status_code == 200
    explanation = response.json()["explanation"]
    assert "Telemetry unavailable" in explanation


def test_explicit_null_telemetry_is_missing(client):
    response = _post(client, {
        "call_duration_minutes": 10,
        "is_unknown_number": False,
        "is_video_call": False,
        **{key: None for key in TELEMETRY_KEYS},
    })
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "LOW"
    assert not any("SMS" in f for f in body["risk_factors"])
    assert not any("app switching" in f for f in body["risk_factors"])
    assert "not treated as behavioral signals" in body["explanation"]


def test_explicit_zero_telemetry_observed(client):
    response = _post(client, {
        "call_duration_minutes": 10,
        "is_unknown_number": False,
        "is_video_call": False,
        **{key: 0 if key != "has_social_app_activity" else False for key in TELEMETRY_KEYS},
    })
    assert response.status_code == 200
    body = response.json()
    assert any("No SMS activity" in f for f in body["risk_factors"])
    assert any("app switching" in f for f in body["risk_factors"])
    assert body["isolation_score"] > 0
    assert "not treated as behavioral signals" not in body["explanation"]


def test_positive_telemetry_observed(client):
    response = _post(client, {
        "call_duration_minutes": 10,
        "is_unknown_number": False,
        "is_video_call": False,
        **{key: 95 if key == "screen_time_on_call_percent" else (
            5 if key == "num_app_switches" else 3 if key == "num_home_presses" else
            500 if key == "location_change" else 60 if key == "screen_brightness" else
            1.0 if key == "screen_on_continuous_hours" else 0.2 if key == "persistence_hours" else True)
           for key in TELEMETRY_KEYS},
    })
    assert response.status_code == 200
    body = response.json()
    assert any("Screen locked to the call" in f for f in body["risk_factors"])
    assert not any("No SMS activity" in f for f in body["risk_factors"])


# ---- wrong types ----------------------------------------------------------

@pytest.mark.parametrize(
    "payload",
    [
        {"num_app_switches": "many"},
        {"num_home_presses": "several"},
        {"has_sms_activity": "sometimes"},
        {"has_social_app_activity": 2},
        {"call_duration_minutes": "abc"},
        {"outgoing_activity_ratio": {"x": 1}},
        {"hour_of_day": "late"},
        {"screen_time_on_call_percent": [90]},
        {"location_change": None, "num_app_switches": 3.7},
        {"is_unknown_number": 2},
        {"caller_call_history": "lots"},
    ],
)
def test_wrong_types_rejected_422(client, payload):
    response = _post(client, payload)
    assert response.status_code == 422


# ---- malformed requests ---------------------------------------------------

@pytest.mark.parametrize(
    "payload_kwargs",
    [
        {"json": []},
        {"json": "text"},
        {"json": 123},
        {"json": True},
        {"content": b"null", "headers": {"Content-Type": "application/json"}},
    ],
)
def test_malformed_bodies_rejected_422(client, payload_kwargs):
    response = client.post("/api/detect-isolation", **payload_kwargs)
    assert response.status_code == 422


def test_missing_body_rejected_422(client):
    response = client.post("/api/detect-isolation")
    assert response.status_code == 422


def test_validation_error_is_fastapi_422_shape(client):
    response = _post(client, {"num_app_switches": "many"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list) and detail
    assert all({"loc", "msg", "type"} <= set(item) for item in detail)


# ---- behavior parity with the engine -------------------------------------

def test_endpoint_matches_direct_engine_score(client):
    engine = RiskEngine()
    engine.load()
    expected = engine.score(dict(FULL_VALID))["risk_score"]

    response = _post(client, FULL_VALID)
    assert response.status_code == 200
    assert response.json()["isolation_score"] == expected
