# tests/test_panic_trigger.py
import pytest

from app.services.panic_trigger import PanicTrigger


@pytest.fixture
def detector():
    return PanicTrigger()


def test_scam_text_is_detected(detector):
    transcript = (
        "This is CBI officer Sharma. You are under digital arrest for money "
        "laundering. Pay a fine of 50000 within 24 hours or you will be arrested. "
        "Do not tell anyone about this call."
    )
    result = detector.detect_panic(transcript)

    assert result["panic_detected"] is True
    assert result["risk_level"] in {"high", "critical"}
    assert result["method"] == "rule-based"
    assert "digital arrest" in result["matched_evidence"]
    assert result["risk_indicators"]
    assert "arrest threats" in result["risk_indicators"]
    assert result["explanation"]


def test_benign_text_is_not_detected(detector):
    transcript = (
        "Hi, this is your electricity provider regarding your monthly bill. "
        "Please check your account in the official app for the bill due date "
        "and visit our website to pay."
    )
    result = detector.detect_panic(transcript)

    assert result["panic_detected"] is False
    assert result["risk_level"] == "low"
    assert result["risk_indicators"] == []
    assert result["matched_evidence"] == []
    assert result["method"] == "rule-based"


def test_mixed_text_with_scam_phrases_is_detected(detector):
    transcript = (
        "Your electricity bill is due tomorrow, so pay within 24 hours or you "
        "are under arrest for money laundering."
    )
    result = detector.detect_panic(transcript)

    assert result["panic_detected"] is True
    assert result["risk_indicators"]
    assert "urgency" in result["risk_indicators"]
    assert "arrest threats" in result["risk_indicators"]
    assert result["matched_evidence"]
    assert result["method"] == "rule-based"


def test_empty_transcript_is_low_risk(detector):
    result = detector.detect_panic("")
    assert result["panic_detected"] is False
    assert result["risk_level"] == "low"
    assert result["method"] == "rule-based"
