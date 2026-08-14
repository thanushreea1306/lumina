import base64
import re
import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.report_generator import RECOMMENDED_ACTIONS, generate_fir_report, recommended_actions


def _pdf_text(path) -> str:
    raw = Path(path).read_bytes()
    chunks = []
    for m in re.finditer(rb"stream\r?\n", raw):
        start = m.end()
        end = raw.find(b"endstream", start)
        if end == -1:
            continue
        data = raw[start:end].rstrip()
        if data.endswith(b"~>"):
            data = data[:-2]
        try:
            decompressed = zlib.decompress(base64.a85decode(data))
        except Exception:
            try:
                decompressed = zlib.decompress(data)
            except Exception:
                continue
        chunks.append(decompressed)
    return b"\n".join(chunks).decode("latin-1")


def _base_features():
    return {
        "call_duration_min": 10,
        "is_unknown_number": 0,
        "is_video_call": 0,
        "hour_of_day": 14,
        "caller_call_history": 10,
        "outgoing_activity_ratio": 0.5,
    }


def _risk_data(level: str, score: float):
    return {"risk_level": level, "risk_score": score, "top_factors": ["None"]}


def test_recommended_actions_matches_spec():
    assert recommended_actions("LOW") == RECOMMENDED_ACTIONS["LOW"] == [
        "No significant risk detected.",
        "Continue normal precautions.",
        "Do not share sensitive information with unknown callers.",
    ]
    assert recommended_actions("MEDIUM") == RECOMMENDED_ACTIONS["MEDIUM"] == [
        "Independently verify the caller.",
        "Do not share OTPs, passwords, banking information, or money.",
        "Consider informing a trusted contact if suspicious behavior continues.",
    ]
    assert recommended_actions("HIGH") == RECOMMENDED_ACTIONS["HIGH"] == [
        "Contact a trusted person and independently verify the situation.",
        "Avoid sending money or sensitive information.",
        "If the situation appears fraudulent, report it.",
    ]
    assert recommended_actions("CRITICAL") == RECOMMENDED_ACTIONS["CRITICAL"] == [
        "Contact a trusted person immediately using another channel.",
        "Do not send money or sensitive information.",
        "If a digital-arrest scam is confirmed, report to 1930 and cybercrime.gov.in.",
    ]


def test_recommended_actions_case_insensitive_and_unknown_falls_back_to_low():
    assert recommended_actions("low") == RECOMMENDED_ACTIONS["LOW"]
    assert recommended_actions("cRiTiCaL") == RECOMMENDED_ACTIONS["CRITICAL"]
    assert recommended_actions("bogus") == RECOMMENDED_ACTIONS["LOW"]


def test_low_report_has_calm_recommendations(tmp_path):
    out = tmp_path / "low.pdf"
    path = generate_fir_report(_base_features(), _risk_data("LOW", 0.0), output_path=str(out))
    text = _pdf_text(path)

    assert "Risk Level: LOW" in text
    assert "Risk Score: 0.0/100" in text
    assert "No significant risk detected." in text
    assert "Continue normal precautions." in text
    assert "Do not share sensitive information with unknown callers." in text


def test_low_report_has_no_emergency_recommendations(tmp_path):
    out = tmp_path / "low_no_emergency.pdf"
    path = generate_fir_report(_base_features(), _risk_data("LOW", 0.0), output_path=str(out))
    text = _pdf_text(path)

    for emergency_phrase in [
        "Call the person on another line immediately",
        "Visit their home if possible",
        "If confirmed scam, dial 1930",
        "Report at cybercrime.gov.in",
        "Share this report with local police",
        "Contact a trusted person immediately",
    ]:
        assert emergency_phrase not in text, f"LOW report must not recommend: {emergency_phrase}"


def test_critical_report_has_emergency_recommendations(tmp_path):
    out = tmp_path / "critical.pdf"
    path = generate_fir_report(_base_features(), _risk_data("CRITICAL", 85.0), output_path=str(out))
    text = _pdf_text(path)

    assert "Risk Level: CRITICAL" in text
    assert "Contact a trusted person immediately using another channel." in text
    assert "Do not send money or sensitive information." in text
    assert "If a digital-arrest scam is confirmed, report to 1930 and cybercrime.gov.in." in text


def test_critical_report_keeps_existing_emergency_stance_and_legal_notice(tmp_path):
    out = tmp_path / "critical_keep.pdf"
    path = generate_fir_report(_base_features(), _risk_data("CRITICAL", 85.0), output_path=str(out))
    text = _pdf_text(path)

    assert "LEGAL NOTICE:" in text
    assert "Digital arrest has NO legal standing in India." in text
    assert "dial 1930" in text or "1930" in text
    assert "cybercrime.gov.in" in text
    assert "No significant risk detected." not in text


def test_top_factors_rendered_as_separate_bullets(tmp_path):
    out = tmp_path / "top_factors_separate.pdf"
    factors = [
        "Very long call (165 min) is a sustained isolation signal.",
        "Unknown caller with no verification history is a common scam tactic.",
        "Video call is often used to intimidate and monitor the victim.",
    ]
    risk_data = {"risk_level": "CRITICAL", "risk_score": 100.0, "top_factors": factors}
    path = generate_fir_report(_base_features(), risk_data, output_path=str(out))
    text = _pdf_text(path).replace(r"\(", "(").replace(r"\)", ")")

    assert "Top Factors" in text
    for factor in factors:
        assert r"\177 " + factor in text, f"top factor not rendered as its own bullet: {factor}"
    assert ", ".join(factors) not in text, "top factors must be separate bullets, not one joined paragraph"


def test_top_factor_wraps_without_truncation(tmp_path):
    out = tmp_path / "top_factors_wrap.pdf"
    long_factor = (
        "This is a deliberately very long explanatory factor that must wrap naturally "
        "across multiple lines within the page width without being clipped or truncated."
    )
    risk_data = {"risk_level": "HIGH", "risk_score": 74.9, "top_factors": [long_factor]}
    path = generate_fir_report(_base_features(), risk_data, output_path=str(out))
    text = _pdf_text(path)

    for word in long_factor.split():
        assert word in text, f"wrapped top factor lost word: {word}"
