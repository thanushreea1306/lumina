# tests/test_model_loading.py
import shutil
import sys
from pathlib import Path

import joblib
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.risk_engine import RiskEngine

ARTIFACTS = ROOT / "models" / "saved"

REAL_NAMES = [
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

BASIC_TELEMETRY = {
    "call_duration_min": 10,
    "is_unknown_number": False,
    "is_video_call": False,
    "hour_of_day": 14,
    "caller_call_history": 10,
    "outgoing_activity_ratio": 0.5,
}

SCORE_PAYLOAD = {
    "call_duration_min": 10,
    "is_unknown_number": 0,
    "is_video_call": 0,
    "hour_of_day": 14,
    "caller_call_history": 10,
    "outgoing_activity_ratio": 0.5,
    "day_of_week": 2,
}


@pytest.fixture
def artifact_dir(tmp_path):
    target = tmp_path / "models" / "saved"
    target.mkdir(parents=True)
    for name in ("risk_classifier.pkl", "scaler.pkl", "features.pkl"):
        shutil.copy(ARTIFACTS / name, target / name)
    return target


@pytest.fixture
def make_engine(artifact_dir):
    def _make():
        engine = RiskEngine()
        engine.model_path = str(artifact_dir / "risk_classifier.pkl")
        engine.scaler_path = str(artifact_dir / "scaler.pkl")
        engine.features_path = str(artifact_dir / "features.pkl")
        return engine

    return _make


def test_missing_model_is_unavailable(artifact_dir, make_engine):
    (artifact_dir / "risk_classifier.pkl").unlink()
    engine = make_engine()
    engine.load()
    assert engine.model_status == "unavailable"
    assert engine.error_detail
    result = engine.score(BASIC_TELEMETRY)
    assert result["model_status"] == "unavailable"
    assert result["ml_probability"] is None
    assert result["error_detail"]
    assert result["risk_score"] == result["rule_contribution"]


def test_missing_scaler_is_unavailable(artifact_dir, make_engine):
    (artifact_dir / "scaler.pkl").unlink()
    engine = make_engine()
    engine.load()
    assert engine.model_status == "unavailable"
    result = engine.score(BASIC_TELEMETRY)
    assert result["model_status"] == "unavailable"
    assert result["ml_probability"] is None
    assert result["risk_score"] == result["rule_contribution"]


def test_missing_features_is_degraded(artifact_dir, make_engine):
    (artifact_dir / "features.pkl").unlink()
    engine = make_engine()
    engine.load()
    assert engine.model_status == "degraded"
    assert engine.error_detail
    result = engine.score(BASIC_TELEMETRY)
    assert result["model_status"] == "degraded"
    assert result["ml_probability"] is None
    assert result["error_detail"]
    assert result["risk_score"] == result["rule_contribution"]


def test_feature_count_mismatch_is_degraded(artifact_dir, make_engine):
    joblib.dump(list(REAL_NAMES) + ["extra_feature"], artifact_dir / "features.pkl")
    engine = make_engine()
    engine.load()
    assert engine.model_status == "degraded"
    assert "mismatch" in engine.error_detail
    result = engine.score(BASIC_TELEMETRY)
    assert result["model_status"] == "degraded"
    assert result["ml_probability"] is None


def test_reordered_features_is_degraded(artifact_dir, make_engine):
    joblib.dump(list(reversed(REAL_NAMES)), artifact_dir / "features.pkl")
    engine = make_engine()
    engine.load()
    assert engine.model_status == "degraded"
    assert "ordering" in engine.error_detail
    result = engine.score(BASIC_TELEMETRY)
    assert result["model_status"] == "degraded"
    assert result["ml_probability"] is None


def test_scaler_transform_failure_is_degraded(make_engine, monkeypatch):
    engine = make_engine()
    engine.load()
    assert engine.model_status == "available"

    def boom(X):
        raise RuntimeError("transform boom")

    monkeypatch.setattr(engine.scaler, "transform", boom)
    result = engine.score(BASIC_TELEMETRY)
    assert result["model_status"] == "degraded"
    assert result["ml_probability"] is None
    assert result["error_detail"]
    assert result["risk_score"] == result["rule_contribution"]


def test_predict_proba_failure_is_degraded(make_engine, monkeypatch):
    engine = make_engine()
    engine.load()
    assert engine.model_status == "available"

    def boom(X):
        raise RuntimeError("predict boom")

    monkeypatch.setattr(engine.model, "predict_proba", boom)
    result = engine.score(BASIC_TELEMETRY)
    assert result["model_status"] == "degraded"
    assert result["ml_probability"] is None
    assert result["error_detail"]
    assert result["risk_score"] == result["rule_contribution"]


def test_valid_artifacts_available_with_real_ml(make_engine):
    engine = make_engine()
    engine.load()
    assert engine.model_status == "available"
    assert engine.error_detail is None
    result = engine.score(BASIC_TELEMETRY)
    assert result["model_status"] == "available"
    assert result["error_detail"] is None
    assert result["ml_probability"] is not None
    assert 0.0 <= result["ml_probability"] <= 100.0
    assert 0.0 <= result["risk_score"] <= 100.0


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def test_api_score_exposes_model_status(client):
    response = client.post("/api/score", json=SCORE_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["model_status"] == "available"
    assert body["model_used"] == body["model_status"]
    assert "error_detail" in body
    assert body["ml_probability"] is not None


def test_api_detect_isolation_reports_consistent_status(client):
    import app.main as main

    response = client.post(
        "/api/detect-isolation",
        json={"call_duration_minutes": 10, "is_unknown_number": False, "is_video_call": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model_status"] == main.risk_engine.model_status


def test_health_reports_consistent_status(client):
    import app.main as main

    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["model_status"] == main.risk_engine.model_status
    assert body["model_loaded"] == (main.risk_engine.model_status == "available")
