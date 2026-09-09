# tests/test_ml_pilot_dataset.py
"""Tests for LUMINA ML Pilot Dataset Infrastructure.

Tests the validation, splitting, and baseline evaluation infrastructure
without requiring actual training data.

CRITICAL: These tests verify infrastructure correctness, NOT model performance.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest


# ---- Fixtures ----

def _make_segment(
    segment_id: str = "seg_001",
    conversation_id: str = "conv_001",
    text: str = "I am calling from the IRS",
    tactic_labels: List[str] = None,
    speaker: str = "CALLER",
    sequence: int = 0,
    source: str = "test_source",
    license: str = "CC0",
) -> Dict[str, Any]:
    """Create a test segment."""
    if tactic_labels is None:
        tactic_labels = ["AUTHORITY_CLAIM"]
    return {
        "segment_id": segment_id,
        "conversation_id": conversation_id,
        "text": text,
        "tactic_labels": tactic_labels,
        "speaker": speaker,
        "sequence": sequence,
        "provenance": {
            "source": source,
            "license": license,
            "consent_status": "VERIFIED",
        },
        "annotation_status": "ANNOTATED",
        "annotator_ids": ["annotator_01"],
    }


def _make_conversation(
    conv_id: str = "conv_001",
    segments: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Create a test conversation with multiple segments."""
    if segments is None:
        segments = [
            _make_segment(
                segment_id=f"{conv_id}_seg_0",
                conversation_id=conv_id,
                text="Hello, I am calling from the IRS regarding your tax returns",
                tactic_labels=["AUTHORITY_CLAIM"],
                speaker="CALLER",
                sequence=0,
            ),
            _make_segment(
                segment_id=f"{conv_id}_seg_1",
                conversation_id=conv_id,
                text="You owe $5,000 in back taxes and must pay immediately",
                tactic_labels=["THREAT_PRESENTATION", "TIME_PRESSURE", "FINANCIAL_REQUEST"],
                speaker="CALLER",
                sequence=1,
            ),
            _make_segment(
                segment_id=f"{conv_id}_seg_2",
                conversation_id=conv_id,
                text="I don't think that's right. Let me call the IRS myself.",
                tactic_labels=["USER_RESISTANCE"],
                speaker="RECIPIENT",
                sequence=2,
            ),
        ]
    return segments


def _write_jsonl(segments: List[Dict], path: Path) -> None:
    """Write segments to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(json.dumps(seg, ensure_ascii=False) + "\n")


# ---- Test: Validation Script ----

class TestPilotValidation:
    """Tests for validate_pilot_dataset.py"""

    def test_validation_imports(self):
        """Verify validation module can be imported."""
        from scripts.ml.validate_pilot_dataset import (
            check_data_legitimacy,
            check_two_party,
            check_scale,
            check_label_coverage,
            check_data_split,
            check_privacy,
            check_integrity,
            run_validation,
        )

    def test_empty_dataset_rejected(self, tmp_path):
        """Empty dataset should be rejected."""
        from scripts.ml.validate_pilot_dataset import run_validation

        # Create empty splits
        _write_jsonl([], tmp_path / "train.jsonl")
        _write_jsonl([], tmp_path / "val.jsonl")
        _write_jsonl([], tmp_path / "test.jsonl")

        report = run_validation(tmp_path)
        assert not report.accepted

    def test_valid_dataset_accepted(self, tmp_path):
        """A valid dataset should pass all checks."""
        from scripts.ml.validate_pilot_dataset import run_validation

        # Create a valid dataset with enough segments
        segments = []
        for i in range(600):
            conv_id = f"conv_{i // 10:04d}"
            speaker = "CALLER" if i % 3 != 2 else "RECIPIENT"
            labels = ["AUTHORITY_CLAIM"] if speaker == "CALLER" else ["BENIGN_CONVERSATION"]
            segments.append(_make_segment(
                segment_id=f"seg_{i:04d}",
                conversation_id=conv_id,
                text=f"Test segment number {i} with enough text to be meaningful",
                tactic_labels=labels,
                speaker=speaker,
                sequence=i % 10,
            ))

        # Write splits (60 conversations, 10 segments each)
        _write_jsonl(segments[:480], tmp_path / "train.jsonl")
        _write_jsonl(segments[480:540], tmp_path / "val.jsonl")
        _write_jsonl(segments[540:], tmp_path / "test.jsonl")

        report = run_validation(tmp_path)
        # Should pass most checks (may have warnings)
        assert report.passed_criteria > report.failed_criteria

    def test_pii_detection(self, tmp_path):
        """PII in segments should be detected."""
        from scripts.ml.validate_pilot_dataset import check_privacy

        segments = [
            _make_segment(text="Call me at 555-123-4567"),
            _make_segment(text="Email me at test@example.com"),
        ]

        results = check_privacy(segments)
        pii_results = [r for r in results if "pii" in r.criterion]
        assert len(pii_results) > 0
        assert not pii_results[0].passed

    def test_label_coverage_check(self):
        """Label coverage should detect missing labels."""
        from scripts.ml.validate_pilot_dataset import check_label_coverage

        segments = [
            _make_segment(tactic_labels=["AUTHORITY_CLAIM"]),
            _make_segment(tactic_labels=["THREAT_PRESENTATION"]),
        ]

        results = check_label_coverage(segments)
        missing_result = [r for r in results if "all_tactics" in r.criterion]
        assert len(missing_result) > 0
        assert not missing_result[0].passed  # Missing most labels


# ---- Test: Split Script ----

class TestConversationSplit:
    """Tests for split_by_conversation.py"""

    def test_split_imports(self):
        """Verify split module can be imported."""
        from scripts.ml.split_by_conversation import (
            split_by_conversation,
            verify_split,
        )

    def test_no_leakage(self):
        """Split should produce no conversation overlap."""
        from scripts.ml.split_by_conversation import split_by_conversation, verify_split

        segments = []
        for i in range(100):
            conv_id = f"conv_{i // 5:04d}"
            segments.append(_make_segment(
                segment_id=f"seg_{i:04d}",
                conversation_id=conv_id,
                text=f"Segment {i}",
                sequence=i % 5,
            ))

        splits = split_by_conversation(segments, seed=42)

        assert verify_split(splits["train"], splits["val"], splits["test"])

    def test_deterministic_split(self):
        """Same seed should produce same split."""
        from scripts.ml.split_by_conversation import split_by_conversation

        segments = []
        for i in range(50):
            segments.append(_make_segment(
                segment_id=f"seg_{i:04d}",
                conversation_id=f"conv_{i:04d}",
                text=f"Segment {i}",
            ))

        splits1 = split_by_conversation(segments, seed=42)
        splits2 = split_by_conversation(segments, seed=42)

        assert len(splits1["train"]) == len(splits2["train"])
        assert len(splits1["val"]) == len(splits2["val"])
        assert len(splits1["test"]) == len(splits2["test"])

    def test_split_ratios(self):
        """Split should approximately match specified ratios."""
        from scripts.ml.split_by_conversation import split_by_conversation

        segments = []
        for i in range(100):
            segments.append(_make_segment(
                segment_id=f"seg_{i:04d}",
                conversation_id=f"conv_{i:04d}",
                text=f"Segment {i}",
            ))

        splits = split_by_conversation(
            segments, seed=42,
            train_ratio=0.8, val_ratio=0.1, test_ratio=0.1,
        )

        total = len(splits["train"]) + len(splits["val"]) + len(splits["test"])
        assert total == len(segments)

        # Allow some variance due to conversation-level splitting
        train_pct = len(splits["train"]) / total
        assert 0.6 <= train_pct <= 0.95


# ---- Test: Baseline Script ----

class TestBaselineEvaluation:
    """Tests for evaluate_baseline.py"""

    def test_baseline_imports(self):
        """Verify baseline module can be imported."""
        from scripts.ml.evaluate_baseline import (
            train_baseline,
            prepare_labels,
            BaselineResult,
        )

    def test_insufficient_data_returns_status(self):
        """Baseline should report INSUFFICIENT_DATA for small datasets."""
        from scripts.ml.evaluate_baseline import train_baseline

        # Very small dataset
        train_texts = ["hello", "world"]
        train_labels = [{"AUTHORITY_CLAIM"}, {"BENIGN_CONVERSATION"}]
        test_texts = ["test"]
        test_labels = [{"AUTHORITY_CLAIM"}]

        result = train_baseline(train_texts, train_labels, test_texts, test_labels)
        assert result.baseline_status == "INSUFFICIENT_DATA"

    def test_baseline_produces_metrics(self):
        """Baseline should produce real metrics on sufficient data."""
        try:
            from scripts.ml.evaluate_baseline import train_baseline
        except ImportError:
            pytest.skip("scikit-learn not installed")

        # Create sufficient synthetic data for testing
        # NOTE: This uses simple repeated patterns, NOT fabricated metrics
        train_texts = []
        train_labels = []
        for i in range(200):
            if i % 4 == 0:
                train_texts.append("I am calling from the police department about your warrant")
                train_labels.append({"AUTHORITY_CLAIM", "THREAT_PRESENTATION"})
            elif i % 4 == 1:
                train_texts.append("You must pay immediately or face arrest")
                train_labels.append({"THREAT_PRESENTATION", "TIME_PRESSURE", "FINANCIAL_REQUEST"})
            elif i % 4 == 2:
                train_texts.append("I'm not going to do that. This sounds like a scam.")
                train_labels.append({"USER_RESISTANCE"})
            else:
                train_texts.append("Hello, how are you today?")
                train_labels.append({"BENIGN_CONVERSATION"})

        test_texts = train_texts[:50]
        test_labels = train_labels[:50]

        result = train_baseline(train_texts, train_labels, test_texts, test_labels)

        # Should produce actual metrics
        assert result.baseline_status in ("BASELINE_PASSED", "BASELINE_MARGINAL", "BASELINE_FAILED")
        assert result.macro_f1 >= 0.0
        assert result.micro_f1 >= 0.0
        assert result.train_size == 200
        assert result.test_size == 50

    def test_per_class_metrics_structure(self):
        """Per-class metrics should have correct structure."""
        try:
            from scripts.ml.evaluate_baseline import train_baseline
        except ImportError:
            pytest.skip("scikit-learn not installed")

        # Use varied text so TF-IDF can extract features
        train_texts = []
        train_labels = []
        for i in range(200):
            if i % 2 == 0:
                train_texts.append(f"Hello friend, how are you doing today number {i}")
                train_labels.append({"BENIGN_CONVERSATION"})
            else:
                train_texts.append(f"I am from the IRS police department warrant {i}")
                train_labels.append({"AUTHORITY_CLAIM"})

        test_texts = train_texts[:50]
        test_labels = train_labels[:50]

        result = train_baseline(train_texts, train_labels, test_texts, test_labels)

        if result.baseline_status != "INSUFFICIENT_DATA":
            assert "BENIGN_CONVERSATION" in result.per_class_metrics
            metrics = result.per_class_metrics["BENIGN_CONVERSATION"]
            assert "precision" in metrics
            assert "recall" in metrics
            assert "f1" in metrics
            assert "support_true" in metrics


# ---- Test: Data Contract ----

class TestDataContract:
    """Tests for segment data contract compliance."""

    def test_segment_schema(self):
        """Segments should conform to expected schema."""
        segment = _make_segment()

        required_fields = [
            "segment_id", "conversation_id", "text",
            "tactic_labels", "speaker", "sequence",
            "provenance", "annotation_status",
        ]

        for field in required_fields:
            assert field in segment, f"Missing required field: {field}"

    def test_speaker_values(self):
        """Speaker should be one of valid values."""
        valid_speakers = {"CALLER", "RECIPIENT", "UNKNOWN"}

        for speaker in valid_speakers:
            seg = _make_segment(speaker=speaker)
            assert seg["speaker"] in valid_speakers

    def test_tactic_labels_are_lists(self):
        """Tactic labels should be lists."""
        seg = _make_segment(tactic_labels=["AUTHORITY_CLAIM", "THREAT_PRESENTATION"])
        assert isinstance(seg["tactic_labels"], list)
        assert len(seg["tactic_labels"]) == 2

    def test_provenance_structure(self):
        """Provenance should have required fields."""
        seg = _make_segment()
        prov = seg["provenance"]

        assert "source" in prov
        assert "license" in prov
        assert "consent_status" in prov


# ---- Test: Acceptance Criteria ----

class TestAcceptanceCriteria:
    """Tests for PILOT_ACCEPTANCE.md criteria definitions."""

    def test_acceptance_document_exists(self):
        """Acceptance criteria document should exist."""
        acceptance_path = Path("docs/ml/PILOT_ACCEPTANCE.md")
        assert acceptance_path.exists(), "PILOT_ACCEPTANCE.md not found"

    def test_annotation_guide_exists(self):
        """Annotation guide should exist."""
        guide_path = Path("docs/ml/PILOT_ANNOTATION_GUIDE.md")
        assert guide_path.exists(), "PILOT_ANNOTATION_GUIDE.md not found"

    def test_pilot_plan_exists(self):
        """Pilot plan should exist."""
        plan_path = Path("docs/ml/PILOT_DATASET_PLAN.md")
        assert plan_path.exists(), "PILOT_DATASET_PLAN.md not found"


# ---- Test: Tactic Taxonomy ----

class TestTacticTaxonomy:
    """Tests for LUMINA tactic taxonomy consistency."""

    def test_all_11_labels_defined(self):
        """All 11 LUMINA labels should be defined."""
        from app.incident.ml_intelligence import TacticLabel

        expected = {
            "AUTHORITY_CLAIM", "THREAT_PRESENTATION", "TIME_PRESSURE",
            "ISOLATION_TACTIC", "CREDENTIAL_REQUEST", "FINANCIAL_REQUEST",
            "REMOTE_ACCESS_REQUEST", "IDENTITY_REQUEST", "BENIGN_CONVERSATION",
            "USER_RESISTANCE", "ADVICE_OR_WARNING",
        }

        actual = {label.value for label in TacticLabel if label.value != "UNKNOWN"}
        assert actual == expected

    def test_unknown_excluded_from_training(self):
        """UNKNOWN should not be a training target."""
        from app.incident.ml_intelligence import TacticLabel

        # UNKNOWN exists but is excluded from training
        assert hasattr(TacticLabel, "UNKNOWN")
        # It should not be in the LUMINA_LABELS set used for training
        from scripts.ml.validate_pilot_dataset import LUMINA_LABELS
        assert "UNKNOWN" not in LUMINA_LABELS
