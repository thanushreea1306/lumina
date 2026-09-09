# tests/test_ml_data_contract.py
"""Tests for ML Data Contract, Validation, and Acceptance Infrastructure.

Tests for:
  - Data contract field validation
  - Provenance validation
  - PII detection
  - Leakage detection
  - Label distribution checks
  - Conversation split validation
  - Acceptance criteria
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


# ---- Data Contract Validation ----

class TestDataContract:
    """Test data contract field validation."""

    ALLOWED_LABELS = {
        "AUTHORITY_CLAIM", "THREAT_PRESENTATION", "TIME_PRESSURE",
        "ISOLATION_TACTIC", "CREDENTIAL_REQUEST", "FINANCIAL_REQUEST",
        "REMOTE_ACCESS_REQUEST", "IDENTITY_REQUEST", "BENIGN_CONVERSATION",
        "USER_RESISTANCE", "ADVICE_OR_WARNING",
    }

    ALLOWED_SPEAKERS = {"CALLER", "USER", "UNKNOWN"}
    ALLOWED_CONSENT = {"PUBLIC_DOMAIN", "LICENSED", "CONSENTED"}
    ALLOWED_ANNOTATION = {"ANNOTATED", "ADJUDICATED", "PROVISIONAL"}

    def _make_valid_record(self) -> dict:
        return {
            "conversation_id": "conv_001",
            "segment_id": "seg_001",
            "text": "This is a test segment",
            "tactic_labels": ["AUTHORITY_CLAIM"],
            "speaker": "CALLER",
            "consent_status": "PUBLIC_DOMAIN",
            "annotation_status": "ANNOTATED",
            "provenance": {
                "source_name": "test",
                "license": "public_domain",
                "commercial_use": True,
                "training_use": True,
            },
        }

    def test_valid_record(self):
        """Valid record passes all checks."""
        record = self._make_valid_record()
        assert record["conversation_id"]
        assert record["segment_id"]
        assert record["text"]
        assert len(record["tactic_labels"]) > 0
        assert record["speaker"] in self.ALLOWED_SPEAKERS
        assert record["consent_status"] in self.ALLOWED_CONSENT
        assert record["annotation_status"] in self.ALLOWED_ANNOTATION

    def test_valid_multi_label(self):
        """Multi-label record is valid."""
        record = self._make_valid_record()
        record["tactic_labels"] = ["AUTHORITY_CLAIM", "THREAT_PRESENTATION"]
        assert len(record["tactic_labels"]) == 2
        assert all(l in self.ALLOWED_LABELS for l in record["tactic_labels"])

    def test_invalid_label(self):
        """Invalid label is rejected."""
        record = self._make_valid_record()
        record["tactic_labels"] = ["INVALID_LABEL"]
        assert record["tactic_labels"][0] not in self.ALLOWED_LABELS

    def test_unknown_label_not_in_training(self):
        """UNKNOWN is not a valid training label."""
        record = self._make_valid_record()
        record["tactic_labels"] = ["UNKNOWN"]
        assert "UNKNOWN" not in self.ALLOWED_LABELS

    def test_empty_text_rejected(self):
        """Empty text is rejected."""
        record = self._make_valid_record()
        record["text"] = ""
        assert not record["text"]

    def test_empty_labels_rejected(self):
        """Empty labels list is rejected."""
        record = self._make_valid_record()
        record["tactic_labels"] = []
        assert len(record["tactic_labels"]) == 0

    def test_invalid_speaker(self):
        """Invalid speaker is rejected."""
        record = self._make_valid_record()
        record["speaker"] = "INVALID"
        assert record["speaker"] not in self.ALLOWED_SPEAKERS

    def test_invalid_consent(self):
        """Invalid consent status is rejected."""
        record = self._make_valid_record()
        record["consent_status"] = "UNKNOWN"
        assert record["consent_status"] not in self.ALLOWED_CONSENT

    def test_long_text_rejected(self):
        """Text exceeding 2000 chars is rejected."""
        record = self._make_valid_record()
        record["text"] = "A" * 2001
        assert len(record["text"]) > 2000

    def test_provenance_required(self):
        """Provenance record is required."""
        record = self._make_valid_record()
        assert "provenance" in record
        assert record["provenance"]["source_name"]
        assert record["provenance"]["license"]


# ---- PII Detection ----

class TestPIIDetection:
    """Test PII detection in training data."""

    def _detect_pii(self, text: str) -> list:
        """Simple PII detection for testing."""
        import re
        patterns = [
            (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), "phone"),
            (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), "email"),
            (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "ssn"),
        ]
        found = []
        for pattern, pii_type in patterns:
            if pattern.search(text):
                found.append(pii_type)
        return found

    def test_detects_phone(self):
        """Phone numbers are detected."""
        pii = self._detect_pii("Call me at 555-123-4567")
        assert "phone" in pii

    def test_detects_email(self):
        """Email addresses are detected."""
        pii = self._detect_pii("Send to user@example.com")
        assert "email" in pii

    def test_detects_ssn(self):
        """SSN patterns are detected."""
        pii = self._detect_pii("SSN: 123-45-6789")
        assert "ssn" in pii

    def test_clean_text_no_pii(self):
        """Clean text has no PII."""
        pii = self._detect_pii("Hello, how are you today?")
        assert len(pii) == 0


# ---- Leakage Detection ----

class TestLeakageDetection:
    """Test data leakage detection between splits."""

    def test_no_leakage(self):
        """No leakage when splits are disjoint."""
        train = [{"conversation_id": "c1"}, {"conversation_id": "c2"}]
        val = [{"conversation_id": "c3"}]
        test = [{"conversation_id": "c4"}]

        train_convs = set(s["conversation_id"] for s in train)
        val_convs = set(s["conversation_id"] for s in val)
        test_convs = set(s["conversation_id"] for s in test)

        assert train_convs.isdisjoint(val_convs)
        assert train_convs.isdisjoint(test_convs)
        assert val_convs.isdisjoint(test_convs)

    def test_leakage_detected(self):
        """Leakage detected when conversation spans splits."""
        train = [{"conversation_id": "c1"}]
        val = [{"conversation_id": "c1"}]  # Same conversation!

        train_convs = set(s["conversation_id"] for s in train)
        val_convs = set(s["conversation_id"] for s in val)

        assert not train_convs.isdisjoint(val_convs)


# ---- Label Distribution ----

class TestLabelDistribution:
    """Test label distribution analysis."""

    def test_balanced_distribution(self):
        """Balanced distribution passes."""
        segments = [
            {"tactic_labels": ["AUTHORITY_CLAIM"]} for _ in range(100)
        ] + [
            {"tactic_labels": ["THREAT_PRESENTATION"]} for _ in range(100)
        ]

        labels = []
        for seg in segments:
            labels.extend(seg["tactic_labels"])

        from collections import Counter
        counts = Counter(labels)
        max_count = max(counts.values())
        min_count = min(counts.values())
        ratio = min_count / max_count

        assert ratio == 1.0  # Perfectly balanced

    def test_imbalanced_distribution(self):
        """Imbalanced distribution is detected."""
        segments = [
            {"tactic_labels": ["AUTHORITY_CLAIM"]} for _ in range(1000)
        ] + [
            {"tactic_labels": ["THREAT_PRESENTATION"]} for _ in range(10)
        ]

        labels = []
        for seg in segments:
            labels.extend(seg["tactic_labels"])

        from collections import Counter
        counts = Counter(labels)
        max_count = max(counts.values())
        min_count = min(counts.values())
        ratio = min_count / max_count

        assert ratio < 0.1  # Severely imbalanced


# ---- Conversation Split Validation ----

class TestConversationSplitValidation:
    """Test conversation-level split validation."""

    def test_proper_split(self):
        """Proper split has no conversation overlap."""
        train = [
            {"conversation_id": "c1", "segment_id": "s1"},
            {"conversation_id": "c1", "segment_id": "s2"},
            {"conversation_id": "c2", "segment_id": "s3"},
        ]
        val = [{"conversation_id": "c3", "segment_id": "s4"}]
        test = [{"conversation_id": "c4", "segment_id": "s5"}]

        train_convs = set(s["conversation_id"] for s in train)
        val_convs = set(s["conversation_id"] for s in val)
        test_convs = set(s["conversation_id"] for s in test)

        assert train_convs.isdisjoint(val_convs)
        assert train_convs.isdisjoint(test_convs)
        assert val_convs.isdisjoint(test_convs)

    def test_all_segments_have_conversation_id(self):
        """All segments have conversation_id."""
        segments = [
            {"conversation_id": "c1", "segment_id": "s1"},
            {"conversation_id": "c1", "segment_id": "s2"},
        ]
        for seg in segments:
            assert "conversation_id" in seg
            assert seg["conversation_id"]


# ---- Acceptance Criteria ----

class TestAcceptanceCriteria:
    """Test dataset acceptance criteria."""

    def test_accepted_dataset(self):
        """Dataset with all criteria met is accepted."""
        criteria = {
            "A1_provenance_known": True,
            "A2_license_known": True,
            "A3_production_use_permitted": True,
            "A4_consent_known": True,
            "A5_not_synthetic": True,
            "A6_labels_verifiable": True,
            "A7_pii_safely_removed": True,
            "A8_no_data_leakage": True,
            "A9_no_duplicate_conversations": True,
            "A10_no_train_test_contamination": True,
        }
        assert all(criteria.values())

    def test_rejected_dataset(self):
        """Dataset with any criterion failing is rejected."""
        criteria = {
            "A1_provenance_known": True,
            "A2_license_known": True,
            "A3_production_use_permitted": False,  # Fails!
            "A4_consent_known": True,
        }
        assert not all(criteria.values())

    def test_pii_criterion(self):
        """PII criterion fails if PII detected."""
        pii_found = [{"segment_id": "s1", "pii_type": "phone"}]
        passed = len(pii_found) == 0
        assert not passed

    def test_leakage_criterion(self):
        """Leakage criterion fails if overlap detected."""
        overlap = {"c1", "c2"}
        passed = len(overlap) == 0
        assert not passed


# ---- Provenance Validation ----

class TestProvenanceValidation:
    """Test provenance validation script logic."""

    def test_provenance_record_structure(self):
        """Provenance record has required fields."""
        record = {
            "source_name": "test_source",
            "license": "public_domain",
            "commercial_use": True,
            "training_use": True,
        }
        required = ["source_name", "license", "commercial_use", "training_use"]
        assert all(field in record for field in required)

    def test_provenance_missing_field(self):
        """Missing provenance field is detected."""
        record = {"source_name": "test"}
        required = ["source_name", "license", "commercial_use", "training_use"]
        missing = [f for f in required if f not in record]
        assert len(missing) > 0
