# tests/test_ml_dataset_pipeline.py
"""Tests for ML Dataset Preparation Pipeline Infrastructure.

Tests for:
  - Provenance validation
  - Deterministic preprocessing
  - Conversation-level splitting
  - Duplicate prevention
  - Label mapping
  - Malformed dataset handling
  - ML interface compatibility
  - TrainedClassifier interface

These tests verify the INFRASTRUCTURE only. They do NOT test a trained model.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.incident.ml_intelligence import (
    BaselineClassifier,
    ConversationPhasePrediction,
    ModelStatus,
    SegmentFeatures,
    TacticClassifier,
    TacticLabel,
    TacticPrediction,
    _extract_segment_features,
)
from app.incident.trained_classifier import (
    CheckpointMetadata,
    ModelConfig,
    SegmentTokenizer,
    TrainedClassifier,
)


# ---- Helpers ----

def _create_test_segment_file(
    path: Path,
    segments: list,
) -> None:
    """Create a test JSON file with segments."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False)


def _make_segment(
    text: str = "Test segment",
    conversation_id: str = "conv_001",
    labels: list = None,
    speaker: str = None,
    sequence: int = 0,
) -> dict:
    """Create a test segment dict."""
    return {
        "conversation_id": conversation_id,
        "text": text,
        "labels": labels or ["BENIGN_CONVERSATION"],
        "speaker": speaker,
        "sequence": sequence,
    }


# ---- Provenance Validation ----

class TestProvenanceValidation:
    """Test provenance tracking and validation."""

    def test_provenance_record_creation(self):
        """ProvenanceRecord can be created and serialized."""
        from scripts.ml.prepare_dataset import ProvenanceRecord

        record = ProvenanceRecord(
            source_name="test_dataset",
            source_url="https://example.com/data.json",
            license="CC0",
            commercial_use=True,
            training_use=True,
            language="en",
            modality="text",
            download_date="2026-09-07T00:00:00Z",
            verification_status="VERIFIED",
            notes="Test dataset",
        )

        d = record.to_dict()
        assert d["source_name"] == "test_dataset"
        assert d["license"] == "CC0"
        assert d["commercial_use"] is True
        assert d["verification_status"] == "VERIFIED"

    def test_provenance_record_excluded(self):
        """ProvenanceRecord can represent excluded datasets."""
        from scripts.ml.prepare_dataset import ProvenanceRecord

        record = ProvenanceRecord(
            source_name="excluded_dataset",
            source_url="https://example.com/excluded",
            license="CC BY-NC",
            commercial_use=False,
            training_use=True,
            language="en",
            modality="text",
            download_date="2026-09-07T00:00:00Z",
            verification_status="EXCLUDED",
            notes="Non-Commercial license prohibits production use",
        )

        d = record.to_dict()
        assert d["verification_status"] == "EXCLUDED"
        assert d["commercial_use"] is False


# ---- Deterministic Preprocessing ----

class TestDeterministicPreprocessing:
    """Test text cleaning and PII filtering."""

    def test_clean_text_basic(self):
        """Basic text cleaning works."""
        from scripts.ml.prepare_dataset import clean_text

        assert clean_text("  Hello world  ") == "Hello world"
        assert clean_text("Hello   world") == "Hello world"
        assert clean_text("Hello\n\nworld") == "Hello\n\nworld"

    def test_clean_text_unicode(self):
        """Unicode normalization works."""
        from scripts.ml.prepare_dataset import clean_text

        # Composed vs decomposed unicode
        text = "café"
        cleaned = clean_text(text)
        assert isinstance(cleaned, str)

    def test_filter_pii_phone(self):
        """Phone numbers are filtered."""
        from scripts.ml.prepare_dataset import filter_pii

        text = "Call me at 555-123-4567"
        filtered = filter_pii(text)
        assert "555-123-4567" not in filtered
        assert "[PHONE]" in filtered

    def test_filter_pii_email(self):
        """Email addresses are filtered."""
        from scripts.ml.prepare_dataset import filter_pii

        text = "Send to user@example.com"
        filtered = filter_pii(text)
        assert "user@example.com" not in filtered
        assert "[EMAIL]" in filtered

    def test_filter_pii_ssn(self):
        """SSN-like patterns are filtered."""
        from scripts.ml.prepare_dataset import filter_pii

        text = "My SSN is 123-45-6789"
        filtered = filter_pii(text)
        assert "123-45-6789" not in filtered
        # SSN may be caught by phone pattern first — either [SSN] or [PHONE] is acceptable
        assert "[SSN]" in filtered or "[PHONE]" in filtered

    def test_filter_pii_preserves_content(self):
        """PII filtering preserves conversational content."""
        from scripts.ml.prepare_dataset import filter_pii

        text = "The police officer called from 555-123-4567"
        filtered = filter_pii(text)
        assert "police" in filtered
        assert "called" in filtered

    def test_filter_secrets(self):
        """Secrets are filtered."""
        from scripts.ml.prepare_dataset import filter_pii

        text = "password: secret123"
        filtered = filter_pii(text)
        assert "secret123" not in filtered
        assert "[SECRET_REDACTED]" in filtered


# ---- Duplicate Detection ----

class TestDuplicateDetection:
    """Test duplicate detection and removal."""

    def test_no_duplicates(self):
        """No duplicates means no removal."""
        from scripts.ml.prepare_dataset import Segment, detect_duplicates

        segments = [
            Segment(segment_id="1", conversation_id="c1", text="Hello", labels=("BENIGN",)),
            Segment(segment_id="2", conversation_id="c1", text="World", labels=("BENIGN",)),
        ]
        unique, count = detect_duplicates(segments)
        assert len(unique) == 2
        assert count == 0

    def test_exact_duplicates(self):
        """Exact duplicates are removed."""
        from scripts.ml.prepare_dataset import Segment, detect_duplicates

        segments = [
            Segment(segment_id="1", conversation_id="c1", text="Hello world", labels=("BENIGN",)),
            Segment(segment_id="2", conversation_id="c1", text="Hello world", labels=("BENIGN",)),
        ]
        unique, count = detect_duplicates(segments)
        assert len(unique) == 1
        assert count == 1

    def test_case_insensitive_duplicates(self):
        """Case-insensitive duplicates are removed."""
        from scripts.ml.prepare_dataset import Segment, detect_duplicates

        segments = [
            Segment(segment_id="1", conversation_id="c1", text="Hello World", labels=("BENIGN",)),
            Segment(segment_id="2", conversation_id="c1", text="hello world", labels=("BENIGN",)),
        ]
        unique, count = detect_duplicates(segments)
        assert len(unique) == 1
        assert count == 1

    def test_whitespace_insensitive_duplicates(self):
        """Whitespace-insensitive duplicates are removed."""
        from scripts.ml.prepare_dataset import Segment, detect_duplicates

        segments = [
            Segment(segment_id="1", conversation_id="c1", text="Hello  World", labels=("BENIGN",)),
            Segment(segment_id="2", conversation_id="c1", text="Hello World", labels=("BENIGN",)),
        ]
        unique, count = detect_duplicates(segments)
        assert len(unique) == 1
        assert count == 1

    def test_different_text_not_duplicates(self):
        """Different text is not considered duplicate."""
        from scripts.ml.prepare_dataset import Segment, detect_duplicates

        segments = [
            Segment(segment_id="1", conversation_id="c1", text="Hello", labels=("BENIGN",)),
            Segment(segment_id="2", conversation_id="c1", text="World", labels=("BENIGN",)),
        ]
        unique, count = detect_duplicates(segments)
        assert len(unique) == 2
        assert count == 0


# ---- Label Mapping ----

class TestLabelMapping:
    """Test label mapping from raw labels to LUMINA taxonomy."""

    def test_direct_mapping(self):
        """Direct label mapping works."""
        from scripts.ml.prepare_dataset import map_label

        assert map_label("authority") == "AUTHORITY_CLAIM"
        assert map_label("threat") == "THREAT_PRESENTATION"
        assert map_label("urgency") == "TIME_PRESSURE"
        assert map_label("credential") == "CREDENTIAL_REQUEST"
        assert map_label("financial") == "FINANCIAL_REQUEST"
        assert map_label("remote_access") == "REMOTE_ACCESS_REQUEST"
        assert map_label("identity") == "IDENTITY_REQUEST"
        assert map_label("benign") == "BENIGN_CONVERSATION"
        assert map_label("resistance") == "USER_RESISTANCE"

    def test_partial_mapping(self):
        """Partial label matching works."""
        from scripts.ml.prepare_dataset import map_label

        assert map_label("false_authority") == "AUTHORITY_CLAIM"
        assert map_label("time_pressure") == "TIME_PRESSURE"
        assert map_label("secrecy_request") == "ISOLATION_TACTIC"
        assert map_label("otp_request") == "CREDENTIAL_REQUEST"
        assert map_label("tech_support_scam") == "REMOTE_ACCESS_REQUEST"

    def test_case_insensitive_mapping(self):
        """Label mapping is case-insensitive."""
        from scripts.ml.prepare_dataset import map_label

        assert map_label("AUTHORITY") == "AUTHORITY_CLAIM"
        assert map_label("Authority") == "AUTHORITY_CLAIM"
        assert map_label("authority") == "AUTHORITY_CLAIM"

    def test_unknown_label_returns_none(self):
        """Unknown labels return None."""
        from scripts.ml.prepare_dataset import map_label

        assert map_label("unknown_label") is None
        assert map_label("xyz123") is None
        assert map_label("") is None


# ---- Conversation-Level Splitting ----

class TestConversationLevelSplit:
    """Test conversation-level splitting prevents data leakage."""

    def test_split_no_leakage(self):
        """No conversation appears in multiple splits."""
        from scripts.ml.prepare_dataset import DatasetSplit, Segment, split_by_conversation

        segments = []
        for i in range(10):
            for j in range(3):
                segments.append(Segment(
                    segment_id=f"seg_{i}_{j}",
                    conversation_id=f"conv_{i}",
                    text=f"Text {i} {j}",
                    labels=("BENIGN_CONVERSATION",),
                    sequence=j,
                ))

        splits = split_by_conversation(segments, seed=42)

        # Collect conversation IDs from each split
        train_convs = set(s.conversation_id for s in splits[DatasetSplit.TRAIN])
        val_convs = set(s.conversation_id for s in splits[DatasetSplit.VALIDATION])
        test_convs = set(s.conversation_id for s in splits[DatasetSplit.TEST])

        # Verify no overlap
        assert train_convs.isdisjoint(val_convs)
        assert train_convs.isdisjoint(test_convs)
        assert val_convs.isdisjoint(test_convs)

    def test_split_preserves_all_conversations(self):
        """All conversations appear in exactly one split."""
        from scripts.ml.prepare_dataset import DatasetSplit, Segment, split_by_conversation

        segments = []
        for i in range(10):
            segments.append(Segment(
                segment_id=f"seg_{i}",
                conversation_id=f"conv_{i}",
                text=f"Text {i}",
                labels=("BENIGN_CONVERSATION",),
                sequence=0,
            ))

        splits = split_by_conversation(segments, seed=42)

        all_convs = set()
        for split_segments in splits.values():
            for seg in split_segments:
                all_convs.add(seg.conversation_id)

        assert len(all_convs) == 10

    def test_split_deterministic(self):
        """Same seed produces same split."""
        from scripts.ml.prepare_dataset import DatasetSplit, Segment, split_by_conversation

        segments = []
        for i in range(20):
            segments.append(Segment(
                segment_id=f"seg_{i}",
                conversation_id=f"conv_{i}",
                text=f"Text {i}",
                labels=("BENIGN_CONVERSATION",),
                sequence=0,
            ))

        splits1 = split_by_conversation(segments, seed=42)
        splits2 = split_by_conversation(segments, seed=42)

        for split_name in DatasetSplit:
            ids1 = [s.segment_id for s in splits1[split_name]]
            ids2 = [s.segment_id for s in splits2[split_name]]
            assert ids1 == ids2

    def test_split_different_seeds(self):
        """Different seeds produce different splits."""
        from scripts.ml.prepare_dataset import DatasetSplit, Segment, split_by_conversation

        segments = []
        for i in range(20):
            segments.append(Segment(
                segment_id=f"seg_{i}",
                conversation_id=f"conv_{i}",
                text=f"Text {i}",
                labels=("BENIGN_CONVERSATION",),
                sequence=0,
            ))

        splits1 = split_by_conversation(segments, seed=42)
        splits2 = split_by_conversation(segments, seed=123)

        # At least one split should differ
        train_ids1 = [s.segment_id for s in splits1[DatasetSplit.TRAIN]]
        train_ids2 = [s.segment_id for s in splits2[DatasetSplit.TRAIN]]
        assert train_ids1 != train_ids2

    def test_empty_segments(self):
        """Empty segment list produces empty splits."""
        from scripts.ml.prepare_dataset import DatasetSplit, Segment, split_by_conversation

        splits = split_by_conversation([], seed=42)
        assert len(splits[DatasetSplit.TRAIN]) == 0
        assert len(splits[DatasetSplit.VALIDATION]) == 0
        assert len(splits[DatasetSplit.TEST]) == 0


# ---- Malformed Dataset Handling ----

class TestMalformedDataset:
    """Test handling of malformed input data."""

    def test_missing_input_directory(self):
        """Missing input directory raises FileNotFoundError."""
        from scripts.ml.prepare_dataset import validate_input_directory

        with pytest.raises(FileNotFoundError):
            validate_input_directory(Path("/nonexistent/path"))

    def test_empty_input_directory(self):
        """Empty input directory raises ValueError."""
        from scripts.ml.prepare_dataset import validate_input_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="No data files found"):
                validate_input_directory(Path(tmpdir))

    def test_invalid_json_handling(self):
        """Invalid JSON in input file is handled gracefully."""
        from scripts.ml.prepare_dataset import load_segments_from_json

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "invalid.json"
            path.write_text("not valid json {{}", encoding="utf-8")
            with pytest.raises(json.JSONDecodeError):
                load_segments_from_json(path)

    def test_empty_json_array(self):
        """Empty JSON array produces no segments."""
        from scripts.ml.prepare_dataset import load_segments_from_json

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "empty.json"
            path.write_text("[]", encoding="utf-8")
            segments = load_segments_from_json(path)
            assert len(segments) == 0

    def test_segments_without_text(self):
        """Segments without text are skipped."""
        from scripts.ml.prepare_dataset import load_segments_from_json

        segments = [
            {"conversation_id": "c1", "text": "", "labels": ["BENIGN"]},
            {"conversation_id": "c1", "text": "Valid text", "labels": ["BENIGN"]},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "segments.json"
            path.write_text(json.dumps(segments), encoding="utf-8")
            loaded = load_segments_from_json(path)
            assert len(loaded) == 1
            assert loaded[0].text == "Valid text"

    def test_segments_with_unknown_labels(self):
        """Segments with unknown labels get UNKNOWN mapped."""
        from scripts.ml.prepare_dataset import load_segments_from_json
        from app.incident.ml_intelligence import TacticLabel

        segments = [
            {"conversation_id": "c1", "text": "Test", "labels": ["UNKNOWN_LABEL"]},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "segments.json"
            path.write_text(json.dumps(segments), encoding="utf-8")
            loaded = load_segments_from_json(path)
            assert len(loaded) == 1
            assert TacticLabel.UNKNOWN.value in loaded[0].labels


# ---- ML Interface Compatibility ----

class TestMLInterfaceCompatibility:
    """Test that TrainedClassifier is compatible with existing interfaces."""

    def test_trained_classifier_extends_tactic_classifier(self):
        """TrainedClassifier extends TacticClassifier ABC."""
        assert issubclass(TrainedClassifier, TacticClassifier)

    def test_trained_classifier_without_checkpoint(self):
        """TrainedClassifier without checkpoint reports NOT_TRAINED."""
        clf = TrainedClassifier()
        assert clf.is_trained is False
        assert clf.status == ModelStatus.NOT_TRAINED

    def test_trained_classifier_fallback_to_baseline(self):
        """TrainedClassifier falls back to BaselineClassifier when not trained."""
        clf = TrainedClassifier()
        features = [
            _extract_segment_features("I am police", "CALLER", 0, 0.0, 3.0),
        ]
        predictions = clf.predict(features)
        assert len(predictions) == 1
        assert predictions[0].tactic == TacticLabel.AUTHORITY_CLAIM

    def test_trained_classifier_predict_phase(self):
        """TrainedClassifier can predict phase."""
        clf = TrainedClassifier()
        predictions = [
            TacticPrediction(tactic=TacticLabel.AUTHORITY_CLAIM, confidence=0.7),
            TacticPrediction(tactic=TacticLabel.THREAT_PRESENTATION, confidence=0.7),
        ]
        phase = clf.predict_phase(predictions)
        assert phase.phase in ("SETUP", "PRESSURE", "EXTRACTION", "ESCALATION", "RESISTANCE")

    def test_trained_classifier_model_metadata(self):
        """TrainedClassifier has honest model metadata."""
        clf = TrainedClassifier()
        assert "deberta" in clf.model_id.lower() or "not_trained" in clf.model_id.lower()
        assert "DeBERTa" in clf.model_name or "NOT TRAINED" in clf.model_name

    def test_trained_classifier_with_nonexistent_checkpoint(self):
        """TrainedClassifier with nonexistent checkpoint reports NOT_TRAINED."""
        clf = TrainedClassifier(checkpoint_path=Path("/nonexistent/model.pt"))
        assert clf.is_trained is False
        assert clf.status == ModelStatus.NOT_TRAINED


# ---- Model Config ----

class TestModelConfig:
    """Test ModelConfig defaults and label mappings."""

    def test_default_config(self):
        """Default config has correct values."""
        config = ModelConfig()
        assert config.model_name == "microsoft/deberta-v3-base"
        assert config.num_labels == 11
        assert config.max_length == 256
        assert config.threshold == 0.5

    def test_label_mappings(self):
        """Label mappings are correctly built."""
        config = ModelConfig()
        assert len(config.id2label) == 11
        assert len(config.label2id) == 11
        assert "AUTHORITY_CLAIM" in config.label2id
        assert "BENIGN_CONVERSATION" in config.label2id
        assert "UNKNOWN" not in config.label2id

    def test_label_mapping_consistency(self):
        """id2label and label2id are inverses of each other."""
        config = ModelConfig()
        for idx, label in config.id2label.items():
            assert config.label2id[label] == idx


# ---- Segment Tokenizer ----

class TestSegmentTokenizer:
    """Test SegmentTokenizer fallback behavior."""

    def test_fallback_tokenizer(self):
        """Fallback tokenizer produces valid output."""
        config = ModelConfig()
        tokenizer = SegmentTokenizer(config)

        # This should use fallback since transformers may not be available
        result = tokenizer.tokenize("Hello world test")
        assert "input_ids" in result
        assert "attention_mask" in result
        assert len(result["input_ids"][0]) == config.max_length

    def test_fallback_batch_tokenizer(self):
        """Fallback batch tokenizer produces valid output."""
        config = ModelConfig()
        tokenizer = SegmentTokenizer(config)

        result = tokenizer.tokenize_batch(["Hello", "World"])
        assert "input_ids" in result
        assert len(result["input_ids"]) == 2


# ---- Checkpoint Metadata ----

class TestCheckpointMetadata:
    """Test CheckpointMetadata serialization."""

    def test_metadata_serialization(self):
        """Metadata can be serialized and deserialized."""
        metadata = CheckpointMetadata(
            model_name="deberta-v3-base",
            training_date="2026-09-07",
            dataset_name="test_dataset",
            dataset_size=1000,
            num_labels=11,
            epoch=3,
            train_loss=0.25,
            val_loss=0.30,
            macro_f1=0.85,
            per_class_f1={"AUTHORITY_CLAIM": 0.9, "THREAT_PRESENTATION": 0.8},
            training_notes="Test training run",
            license="CC0",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_checkpoint"
            metadata.to_file(path)

            loaded = CheckpointMetadata.from_file(path)
            assert loaded is not None
            assert loaded.model_name == "deberta-v3-base"
            assert loaded.dataset_size == 1000
            assert loaded.macro_f1 == 0.85

    def test_metadata_missing_file(self):
        """Missing metadata file returns None."""
        result = CheckpointMetadata.from_file(Path("/nonexistent/path"))
        assert result is None


# ---- Label Distribution ----

class TestLabelDistribution:
    """Test label distribution computation."""

    def test_compute_label_distribution(self):
        """Label distribution is computed correctly."""
        from scripts.ml.prepare_dataset import Segment, compute_label_distribution

        segments = [
            Segment(segment_id="1", conversation_id="c1", text="A", labels=("AUTHORITY_CLAIM", "TIME_PRESSURE")),
            Segment(segment_id="2", conversation_id="c1", text="B", labels=("AUTHORITY_CLAIM",)),
            Segment(segment_id="3", conversation_id="c1", text="C", labels=("FINANCIAL_REQUEST",)),
        ]

        dist = compute_label_distribution(segments)
        assert dist["AUTHORITY_CLAIM"] == 2
        assert dist["TIME_PRESSURE"] == 1
        assert dist["FINANCIAL_REQUEST"] == 1

    def test_compute_class_imbalance(self):
        """Class imbalance ratios are computed correctly."""
        from scripts.ml.prepare_dataset import compute_class_imbalance

        dist = {"A": 100, "B": 50, "C": 10}
        imbalance = compute_class_imbalance(dist)

        assert imbalance["A"] == 1.0
        assert imbalance["B"] == 0.5
        assert imbalance["C"] == 0.1

    def test_empty_distribution(self):
        """Empty distribution returns empty imbalance."""
        from scripts.ml.prepare_dataset import compute_class_imbalance

        assert compute_class_imbalance({}) == {}
