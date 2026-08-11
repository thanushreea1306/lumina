# tests/test_phase2_risk_cases.py
import pytest
from app.core.risk_engine import RiskEngine

@pytest.fixture
def engine():
    return RiskEngine()

def test_normal_call_low_risk(engine):
    """Short call, known caller, normal activity → LOW risk"""
    telemetry = {
        'call_duration_min': 5,
        'is_unknown_number': False,
        'is_video_call': False,
        'hour_of_day': 14,
        'caller_call_history': 15,
        'outgoing_activity_ratio': 0.8,
        'screen_time_on_call_percent': 30,
        'num_app_switches': 20,
        'num_home_presses': 10,
        'has_sms_activity': True,
        'has_social_app_activity': True,
        'location_change': 500,
        'screen_brightness': 40,
        'screen_on_continuous_hours': 1
    }
    result = engine.score(telemetry)
    assert result['risk_level'] == 'low'
    assert result['risk_score'] < 35

def test_scam_call_high_risk(engine):
    """Long call, unknown, video, isolation → CRITICAL"""
    telemetry = {
        'call_duration_min': 180,
        'is_unknown_number': True,
        'is_video_call': True,
        'hour_of_day': 10,
        'caller_call_history': 0,
        'outgoing_activity_ratio': 0.02,
        'screen_time_on_call_percent': 95,
        'num_app_switches': 0,
        'num_home_presses': 0,
        'has_sms_activity': False,
        'has_social_app_activity': False,
        'location_change': 5,
        'screen_brightness': 90,
        'screen_on_continuous_hours': 6
    }
    result = engine.score(telemetry)
    assert result['risk_level'] in ['high', 'critical']
    assert result['risk_score'] > 50

def test_long_but_known_caller(engine):
    """Long call but known caller and normal activity → NOT CRITICAL"""
    telemetry = {
        'call_duration_min': 120,
        'is_unknown_number': False,
        'is_video_call': True,
        'hour_of_day': 14,
        'caller_call_history': 20,
        'outgoing_activity_ratio': 0.6,
        'screen_time_on_call_percent': 40,
        'num_app_switches': 15,
        'num_home_presses': 8,
        'has_sms_activity': True,
        'has_social_app_activity': True,
        'location_change': 300,
        'screen_brightness': 50,
        'screen_on_continuous_hours': 2
    }
    result = engine.score(telemetry)
    assert result['risk_level'] != 'critical'
    assert result['risk_score'] < 70

def test_missing_telemetry(engine):
    """Missing telemetry should NOT falsely elevate risk"""
    telemetry = {
        'call_duration_min': 10,
        'is_unknown_number': False,
        'is_video_call': False,
        'hour_of_day': 14,
        'caller_call_history': 10,
        'outgoing_activity_ratio': 0.5
        # All other telemetry intentionally missing
    }
    result = engine.score(telemetry)
    # Should not be critical just because data is missing
    assert result['risk_level'] != 'critical'