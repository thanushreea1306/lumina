# tests/test_telemetry_ml_inference.py
"""Regression tests: missing/null telemetry must never be fed to ML as an
observed 0.0/False, and explicit zero must remain a real observation.

The deployed model is an 11-feature call-behavior schema (features.pkl).
Telemetry-only fields and their is_missing_* flags are excluded from ML
inference by construction, so absent/null telemetry cannot artificially raise
the ML probability. The safety-rule layer continues to consume the
is_missing_* flags exactly as before.
"""

import pytest

from app.core.features import extract_features
from app.core.risk_engine import RiskEngine, _telemetry_in_schema

BASE_CALL = {
    "call_duration_min": 45,
    "is_unknown_number": 0,
    "is_video_call": 0,
    "hour_of_day": 14,
    "caller_call_history": 20,
    "outgoing_activity_ratio": 0.7,
}

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

MISSING_FLAGS = [f"is_missing_{name}" for name in TELEMETRY_FIELDS]

NULL_TELEMETRY = {name: None for name in TELEMETRY_FIELDS}

ZERO_TELEMETRY = {
    "screen_time_on_call_percent": 0,
    "num_app_switches": 0,
    "num_home_presses": 0,
    "has_sms_activity": False,
    "has_social_app_activity": False,
    "location_change": 0,
    "screen_brightness": 0,
    "screen_on_continuous_hours": 0,
    "persistence_hours": 0,
}

POSITIVE_TELEMETRY = {
    "screen_time_on_call_percent": 95,
    "num_app_switches": 8,
    "num_home_presses": 5,
    "has_sms_activity": True,
    "has_social_app_activity": True,
    "location_change": 500,
    "screen_brightness": 60,
    "screen_on_continuous_hours": 0.5,
    "persistence_hours": 0.2,
}


@pytest.fixture(scope="module")
def engine():
    eng = RiskEngine()
    eng.load()
    assert eng.model_status == "available"
    return eng


def _run(engine, telemetry):
    payload = {**BASE_CALL, **telemetry}
    features = extract_features(payload)
    return engine._ml_probability(features), features


# ---- 1. telemetry absent -------------------------------------------------

def test_telemetry_absent_is_missing(engine):
    ml, features = _run(engine, {})
    assert all(features[flag] == 1 for flag in MISSING_FLAGS)
    assert ml is not None


# ---- 2. telemetry null ---------------------------------------------------

def test_telemetry_null_is_missing_not_observed(engine):
    ml_null, features_null = _run(engine, NULL_TELEMETRY)
    ml_absent, _ = _run(engine, {})
    assert all(features_null[flag] == 1 for flag in MISSING_FLAGS)
    assert ml_null == pytest.approx(ml_absent, abs=1e-12)


# ---- 3. telemetry explicitly zero ----------------------------------------

def test_telemetry_explicit_zero_is_observed(engine):
    ml, features = _run(engine, ZERO_TELEMETRY)
    assert all(features[flag] == 0 for flag in MISSING_FLAGS)
    assert features["screen_time_on_call_percent"] == 0.0
    assert features["num_app_switches"] == 0
    assert features["has_sms_activity"] == 0
    assert ml is not None


# ---- 4. telemetry positive -----------------------------------------------

def test_telemetry_positive_is_observed(engine):
    ml, features = _run(engine, POSITIVE_TELEMETRY)
    assert all(features[flag] == 0 for flag in MISSING_FLAGS)
    assert features["screen_time_on_call_percent"] == 95.0
    assert features["num_app_switches"] == 8
    assert features["has_social_app_activity"] == 1
    assert ml is not None


# ---- absent/null vs explicit zero in the ML path -------------------------

def test_ml_probability_is_invariant_to_telemetry_presence(engine):
    """The deployed 11-feature model has no telemetry inputs.

    Absent, null, explicit-zero and positive telemetry must all yield the
    same ML probability: missing telemetry is never coerced into an observed
    0.0 model input, so it cannot inflate (or deflate) the ML risk.
    """
    probabilities = {}
    for name, telemetry in (
        ("absent", {}),
        ("null", NULL_TELEMETRY),
        ("zero", ZERO_TELEMETRY),
        ("positive", POSITIVE_TELEMETRY),
    ):
        ml, _ = _run(engine, telemetry)
        probabilities[name] = ml

    values = list(probabilities.values())
    assert values[0] is not None
    assert all(v == pytest.approx(values[0], abs=1e-12) for v in values)


def test_ml_input_excludes_telemetry_only_fields(engine):
    """ML input columns come only from the deployed model schema and never
    include a telemetry-only field or is_missing_* flag."""
    _, features = _run(engine, ZERO_TELEMETRY)
    row = engine._model_input_row(features)
    assert list(row.columns) == engine.model_features
    assert all(col not in engine.model_features for col in TELEMETRY_FIELDS + MISSING_FLAGS)


# ---- rules still use is_missing_* flags exactly as before ----------------

def _contributions(engine, telemetry):
    result = engine.score({**BASE_CALL, **telemetry}, mode="demo")
    reasons = [c["reason"] for c in result["safety_rule_contributions"]]
    return reasons, result["missing_telemetry"]


def test_rules_treat_absent_and_null_as_missing(engine):
    for telemetry in ({}, NULL_TELEMETRY):
        reasons, missing = _contributions(engine, telemetry)
        assert set(missing) == set(TELEMETRY_FIELDS)
        assert not any("No app switching" in r for r in reasons)
        assert not any("No SMS activity" in r for r in reasons)


def test_rules_treat_explicit_zero_as_observed(engine):
    reasons, missing = _contributions(engine, ZERO_TELEMETRY)
    assert missing == []
    assert any("No app switching" in r for r in reasons)
    assert any("No SMS activity" in r for r in reasons)


def test_rules_treat_positive_telemetry_as_observed(engine):
    reasons, missing = _contributions(engine, POSITIVE_TELEMETRY)
    assert missing == []
    assert any("Screen locked to the call" in r for r in reasons)


# ---- schema guard --------------------------------------------------------

REAL_11 = [
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
]


def test_schema_guard_rejects_telemetry_in_model_schema():
    assert _telemetry_in_schema(REAL_11) == []
    assert _telemetry_in_schema(REAL_11 + ["screen_time_on_call_percent"]) == [
        "screen_time_on_call_percent"
    ]
    assert _telemetry_in_schema(["is_missing_persistence_hours"] + REAL_11[:1]) == [
        "is_missing_persistence_hours"
    ]
    assert _telemetry_in_schema(None) == []
