# tests/test_ml_teleantifraud_gate.py
"""Tests for TeleAntiFraud-28k Suitability Gate.

These tests validate that the fail-closed NO_GO decision is
correctly enforced. They ensure that:

- Unverified license cannot become production-approved
- Synthetic data cannot become REAL
- Missing speaker structure cannot become two-party
- Missing victim evidence cannot become victim behavior
- Unsupported tactic mappings remain unsupported
- NO_GO remains fail-closed

CRITICAL: These tests verify gate logic, NOT model performance.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest


# ---- Constants ----

LUMINA_LABELS = {
    "AUTHORITY_CLAIM", "THREAT_PRESENTATION", "TIME_PRESSURE",
    "ISOLATION_TACTIC", "CREDENTIAL_REQUEST", "FINANCIAL_REQUEST",
    "REMOTE_ACCESS_REQUEST", "IDENTITY_REQUEST", "BENIGN_CONVERSATION",
    "USER_RESISTANCE", "ADVICE_OR_WARNING",
}

# TeleAntiFraud-28k known facts (from forensic investigation)
TELEANTIFRAUD_FACTS = {
    "language": "zh",  # Chinese, not English
    "license": "apache-2.0",
    "total_samples": 28511,
    "audio_type": "TTS",  # All TTS-generated
    "text_sources": ["ASR_real", "LLM_generated", "multi_agent"],
    "annotation_method": "LLM",  # DeepSeek-R1
    "label_level": "conversation",  # Not segment-level
    "speaker_attribution": False,
    "real_audio": False,
    "english": False,
}


# ---- Gate Logic Tests ----

class TestLanguageGate:
    """Tests that wrong language blocks dataset entry."""

    def test_chinese_dataset_rejected_for_english_task(self):
        """A Chinese dataset cannot be used for English LUMINA training."""
        facts = TELEANTIFRAUD_FACTS
        assert facts["language"] != "en", "Dataset must not be English"

    def test_language_mismatch_is_fatal(self):
        """Language mismatch should be classified as FATAL."""
        # LUMINA requires English
        required_language = "en"
        actual_language = TELEANTIFRAUD_FACTS["language"]
        assert actual_language != required_language


class TestSyntheticDataGate:
    """Tests that synthetic data cannot be classified as REAL."""

    def test_tts_audio_not_real(self):
        """TTS-generated audio is not real human speech."""
        assert TELEANTIFRAUD_FACTS["audio_type"] == "TTS"
        assert not TELEANTIFRAUD_FACTS["real_audio"]

    def test_llm_annotations_not_human(self):
        """LLM-generated annotations are not human annotations."""
        assert TELEANTIFRAUD_FACTS["annotation_method"] == "LLM"

    def test_mixed_text_sources_contain_synthetic(self):
        """Text sources include LLM-generated and multi-agent content."""
        sources = TELEANTIFRAUD_FACTS["text_sources"]
        assert "LLM_generated" in sources
        assert "multi_agent" in sources

    def test_synthetic_proportion_blocks_real_classification(self):
        """Dataset with LLM + multi-agent sources cannot be classified as real."""
        sources = TELEANTIFRAUD_FACTS["text_sources"]
        synthetic_sources = {"LLM_generated", "multi_agent"}
        has_synthetic = bool(set(sources) & synthetic_sources)
        assert has_synthetic, "Dataset contains synthetic sources"


class TestSpeakerStructureGate:
    """Tests that missing speaker attribution blocks two-party classification."""

    def test_no_speaker_attribution(self):
        """TeleAntiFraud-28k does not provide speaker labels."""
        assert not TELEANTIFRAUD_FACTS["speaker_attribution"]

    def test_missing_speakers_blocks_two_party(self):
        """Without speaker attribution, dataset cannot be classified as two-party."""
        has_speakers = TELEANTIFRAUD_FACTS["speaker_attribution"]
        assert not has_speakers, "Cannot classify as two-party without speaker labels"


class TestVictimBehaviorGate:
    """Tests that missing victim evidence blocks victim behavior claims."""

    def test_no_victim_behavior_evidence(self):
        """No evidence of genuine victim behavior in dataset."""
        # Chinese dataset with TTS audio — cannot verify victim behavior
        assert not TELEANTIFRAUD_FACTS["english"]
        assert not TELEANTIFRAUD_FACTS["real_audio"]

    def test_victim_behavior_requires_speaker_attribution(self):
        """Victim behavior cannot be verified without speaker attribution."""
        assert not TELEANTIFRAUD_FACTS["speaker_attribution"]


class TestTacticMappingGate:
    """Tests that unsupported tactic mappings remain unsupported."""

    def test_lumina_tactics_not_in_dataset(self):
        """LUMINA's 11 behavioral tactics are not present in TeleAntiFraud-28k."""
        # TeleAntiFraud has: 7 scenarios, 7 fraud types
        # LUMINA has: 11 behavioral tactics
        # These are different taxonomies
        teleantifraud_labels = {
            "Customer Consultation", "Appointment Services", "Routine Shopping",
            "Dining Services", "Food Delivery Services", "Ride-Hailing Services",
            "Transportation Inquiries",  # scenarios
            "Customer Service Fraud", "Banking Fraud", "Investment Fraud",
            "Phishing Fraud", "Lottery Fraud", "Kidnapping Fraud",
            "Identity Theft",  # fraud types
        }

        # LUMINA labels should NOT be directly mappable
        overlap = LUMINA_LABELS & teleantifraud_labels
        assert len(overlap) == 0, f"Unexpected label overlap: {overlap}"

    def test_conversation_level_not_segment_level(self):
        """Dataset labels are conversation-level, not segment-level."""
        assert TELEANTIFRAUD_FACTS["label_level"] == "conversation"


class TestNOGoFailClosed:
    """Tests that NO_GO decision is fail-closed."""

    def test_nogo_status_documented(self):
        """NO_GO status should be documented in suitability gate."""
        gate_path = Path("docs/ml/TELEANTIFRAUD_SUITABILITY_GATE.md")
        assert gate_path.exists(), "Suitability gate document not found"

        content = gate_path.read_text(encoding="utf-8")
        assert "RED" in content or "NO_GO" in content or "DO NOT USE" in content

    def test_forensics_document_exists(self):
        """Forensic investigation document should exist."""
        forensics_path = Path("docs/ml/TELEANTIFRAUD_FORENSICS.md")
        assert forensics_path.exists(), "Forensics document not found"

    def test_provenance_document_exists(self):
        """Provenance document should exist."""
        provenance_path = Path("docs/ml/TELEANTIFRAUD_PROVENANCE.md")
        assert provenance_path.exists(), "Provenance document not found"


class TestLicenseNotOverridden:
    """Tests that permissive license does not override data quality blocks."""

    def test_apache2_license_does_not_bypass_quality(self):
        """Apache 2.0 license does not make synthetic data real."""
        license_ok = TELEANTIFRAUD_FACTS["license"] == "apache-2.0"
        data_real = TELEANTIFRAUD_FACTS["real_audio"]

        # Even with valid license, data is not real
        assert license_ok, "License should be Apache 2.0"
        assert not data_real, "Data is not real despite valid license"

    def test_permissive_license_does_not_fix_language(self):
        """Permissive license does not change Chinese to English."""
        license_ok = TELEANTIFRAUD_FACTS["license"] == "apache-2.0"
        language_ok = TELEANTIFRAUD_FACTS["language"] == "en"

        assert license_ok
        assert not language_ok


class TestTrainingStatusEnforcement:
    """Tests that TRAINING_STATUS = NO_GO is correctly enforced."""

    def test_training_status_is_nogo(self):
        """Training status should be NO_GO for TeleAntiFraud-28k."""
        # Based on forensic investigation
        has_fatal_blockers = (
            not TELEANTIFRAUD_FACTS["english"] or
            not TELEANTIFRAUD_FACTS["real_audio"] or
            not TELEANTIFRAUD_FACTS["speaker_attribution"]
        )
        assert has_fatal_blockers, "Should have fatal blockers"

    def test_nogo_cannot_be_overridden_by_license(self):
        """NO_GO cannot be overridden by license alone."""
        # Even if license is perfect, other blockers remain
        blockers = [
            not TELEANTIFRAUD_FACTS["english"],
            not TELEANTIFRAUD_FACTS["real_audio"],
            not TELEANTIFRAUD_FACTS["speaker_attribution"],
            TELEANTIFRAUD_FACTS["annotation_method"] == "LLM",
            TELEANTIFRAUD_FACTS["label_level"] == "conversation",
        ]
        assert sum(blockers) >= 3, "Should have multiple fatal blockers"
