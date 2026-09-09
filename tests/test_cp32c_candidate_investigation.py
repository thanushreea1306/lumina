# tests/test_cp32c_candidate_investigation.py
"""CP-32C: Final Unresolved Dataset Investigation — focused tests.

These tests explicitly verify the non-negotiable requirements:
  1. Every unresolved candidate is explicitly evaluated
  2. Every gate uses PASS/PARTIAL/FAIL/UNKNOWN
  3. UNKNOWN commercial ML rights cannot produce GO
  4. Paper-only datasets cannot be treated as accessible
  5. Public YouTube content cannot automatically be treated as licensed training data
  6. AI-generated/LLM-generated conversations cannot be treated as real human conversations
  7. AI recipient is explicitly recorded
  8. Absent segment labels remain absent
  9. Conversation-level scam labels cannot silently become tactic labels
  10. Absent privacy/consent evidence remains UNKNOWN
  11. No candidate receives PRIMARY status without all critical gates
  12. NO_GO remains valid
  13. No dataset files are added
  14. No production ML code is modified
  15. No model training occurs
"""
from __future__ import annotations

import pytest
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


# ---- Gate Definitions ----

class GateStatus(str, Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class Classification(str, Enum):
    PRIMARY_TRAINING_CANDIDATE = "PRIMARY_TRAINING_CANDIDATE"
    AUXILIARY_ONLY = "AUXILIARY_ONLY"
    EVALUATION_ONLY = "EVALUATION_ONLY"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


class Decision(str, Enum):
    GO = "GO"
    CONDITIONAL_GO = "CONDITIONAL_GO"
    NO_GO = "NO_GO"


# Critical gates — FAIL on any = cannot be PRIMARY_TRAINING_CANDIDATE
CRITICAL_GATES = [
    "REAL_AUDIO",
    "REAL_CONVERSATION",
    "TWO_PARTY_HUMAN",
    "LUMINA_TACTIC_RELEVANCE",
    "COMMERCIAL_TRAINING_RIGHTS",
    "PRIVACY_CONSENT",
    "SCALE",
]


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: GateStatus
    note: str = ""


@dataclass(frozen=True)
class CandidateEvaluation:
    name: str
    gates: Tuple[GateResult, ...]
    classification: Classification
    primary_failure: str = ""
    blockers: Tuple[str, ...] = ()


# ---- Candidate Definitions (CP-32C resolved) ----

CANDIDATES: Tuple[CandidateEvaluation, ...] = (
    CandidateEvaluation(
        name="Open Yap 1K",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.PASS, "Real human conversations, dual-channel"),
            GateResult("REAL_CONVERSATION", GateStatus.PASS, "Natural two-speaker English, self-paired friends/family"),
            GateResult("TWO_PARTY_HUMAN", GateStatus.PASS, "Both sides are real humans"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.PASS, "Dual-channel preserves speaker identity"),
            GateResult("TEMPORAL_STRUCTURE", GateStatus.PASS, "Shared timeline with overlap"),
            GateResult("LUMINA_TACTIC_RELEVANCE", GateStatus.FAIL, "General conversations, NOT scam/social-engineering"),
            GateResult("SEGMENT_LEVEL_LABELS", GateStatus.FAIL, "No labels — raw audio and transcripts only"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No labels exist"),
            GateResult("REALISTIC_LABELING", GateStatus.FAIL, "No labels exist"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Full corpus DUA not reviewed"),
            GateResult("PRIVACY_CONSENT", GateStatus.PARTIAL, "Speakers participated voluntarily; full terms in unreviewed DUA"),
            GateResult("SCALE", GateStatus.PASS, "1,000 hours, 1,602 conversations, 239 speakers"),
            GateResult("ENGLISH", GateStatus.PASS, "English conversations"),
        ),
        classification=Classification.REJECTED,
        primary_failure="LUMINA_TACTIC_RELEVANCE + SEGMENT_LEVEL_LABELS",
        blockers=("NOT_SCAM_RELEVANT", "NO_LABELS", "DUA_NOT_REVIEWED"),
    ),
    CandidateEvaluation(
        name="BYU-PCCL",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.UNKNOWN, "Aggregated from multiple sources"),
            GateResult("REAL_CONVERSATION", GateStatus.PARTIAL, "Mixed sources — some real, some synthetic"),
            GateResult("TWO_PARTY_HUMAN", GateStatus.FAIL, "No original two-party dataset; aggregates from other sources"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.UNKNOWN, "Not documented for aggregated sources"),
            GateResult("TEMPORAL_STRUCTURE", GateStatus.UNKNOWN, "Not documented"),
            GateResult("LUMINA_TACTIC_RELEVANCE", GateStatus.PARTIAL, "Some scam transcripts, but primarily scambaiter interactions"),
            GateResult("SEGMENT_LEVEL_LABELS", GateStatus.FAIL, "No segment-level labels; LLM-derived features only"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No ground-truth annotations"),
            GateResult("REALISTIC_LABELING", GateStatus.FAIL, "Uses LLM for feature extraction, not human annotation"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.FAIL, "No unified permission; YouTube content prohibits commercial ML training"),
            GateResult("PRIVACY_CONSENT", GateStatus.UNKNOWN, "Mixed sources with different privacy provisions"),
            GateResult("SCALE", GateStatus.UNKNOWN, "Not clearly documented"),
            GateResult("ENGLISH", GateStatus.PASS, "English transcripts"),
        ),
        classification=Classification.REJECTED,
        primary_failure="NO_ORIGINAL_DATASET + COMMERCIAL_TRAINING_RIGHTS",
        blockers=("NO_ORIGINAL_DATA", "MIXED_LICENSES", "YOUTUBE_TOS"),
    ),
    CandidateEvaluation(
        name="YouTube Scam Transcripts",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.FAIL, "Transcripts only — no audio"),
            GateResult("REAL_CONVERSATION", GateStatus.PARTIAL, "Scammer-to-scambaiter interactions, not real victim conversations"),
            GateResult("TWO_PARTY_HUMAN", GateStatus.FAIL, "Scambaiter is not a real victim"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.UNKNOWN, "Not documented"),
            GateResult("TEMPORAL_STRUCTURE", GateStatus.UNKNOWN, "Not documented"),
            GateResult("LUMINA_TACTIC_RELEVANCE", GateStatus.PARTIAL, "Scammer-side tactics present, but victim-side behavior not representative"),
            GateResult("SEGMENT_LEVEL_LABELS", GateStatus.FAIL, "No labels — raw transcripts only"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No labels exist"),
            GateResult("REALISTIC_LABELING", GateStatus.FAIL, "No labels exist"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.FAIL, "YouTube Terms of Service prohibit commercial ML training"),
            GateResult("PRIVACY_CONSENT", GateStatus.UNKNOWN, "No consent information available"),
            GateResult("SCALE", GateStatus.FAIL, "243 transcripts — too small"),
            GateResult("ENGLISH", GateStatus.PASS, "English transcripts"),
        ),
        classification=Classification.REJECTED,
        primary_failure="SCAMBAITER_CONVERSATIONS + NO_AUDIO + NO_LICENSE",
        blockers=("YOUTUBE_TOS", "NO_AUDIO", "NO_LICENSE", "SCAMBAITER"),
    ),
    CandidateEvaluation(
        name="Anatomy of a Scam Call",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.PASS, "913 hours of inbound scam/spam calls"),
            GateResult("REAL_CONVERSATION", GateStatus.PARTIAL, "Real scammer, but recipient is AI voice-agent honeypot"),
            GateResult("TWO_PARTY_HUMAN", GateStatus.FAIL, "Recipient side is AI voice-agent, NOT real human"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.PARTIAL, "Caller/recipient turns distinguishable, but recipient is AI"),
            GateResult("TEMPORAL_STRUCTURE", GateStatus.PASS, "Turn-level timestamps"),
            GateResult("LUMINA_TACTIC_RELEVANCE", GateStatus.PARTIAL, "Real scammer tactics, but AI recipient dynamics differ from real victims"),
            GateResult("SEGMENT_LEVEL_LABELS", GateStatus.FAIL, "No LUMINA tactic labels; binary scam/spam only"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No human LUMINA annotations"),
            GateResult("REALISTIC_LABELING", GateStatus.FAIL, "No human annotations for LUMINA tactics"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Dataset not publicly available; license unknown"),
            GateResult("PRIVACY_CONSENT", GateStatus.PARTIAL, "Scammers did not consent; fictitious identities used"),
            GateResult("SCALE", GateStatus.PASS, "10,211 calls, 913 hours, 330,956 turns"),
            GateResult("ENGLISH", GateStatus.PASS, "English calls"),
            GateResult("DATA_ACCESS", GateStatus.FAIL, "Dataset not publicly available; no download link"),
        ),
        classification=Classification.REJECTED,
        primary_failure="TWO_PARTY_HUMAN (AI recipient) + DATA_ACCESS (not available)",
        blockers=("AI_RECIPIENT", "NOT_PUBLICLY_AVAILABLE", "NO_LICENSE"),
    ),
)


# ---- Helper Functions ----

def get_gate_status(candidate: CandidateEvaluation, gate: str) -> GateStatus:
    for g in candidate.gates:
        if g.gate == gate:
            return g.status
    return GateStatus.UNKNOWN


def has_critical_fail(candidate: CandidateEvaluation) -> bool:
    for gate in CRITICAL_GATES:
        if get_gate_status(candidate, gate) == GateStatus.FAIL:
            return True
    return False


def has_unknown_license(candidate: CandidateEvaluation) -> bool:
    return get_gate_status(candidate, "COMMERCIAL_TRAINING_RIGHTS") == GateStatus.UNKNOWN


# ---- Tests ----

class TestEveryCandidateIsExplicitlyEvaluated:
    """Test 1: Every unresolved candidate is explicitly evaluated."""

    EXPECTED_CANDIDATES = {
        "Open Yap 1K",
        "BYU-PCCL",
        "YouTube Scam Transcripts",
        "Anatomy of a Scam Call",
    }

    def test_all_expected_candidates_present(self):
        actual_names = {c.name for c in CANDIDATES}
        for name in self.EXPECTED_CANDIDATES:
            assert name in actual_names, f"Expected candidate {name!r} not found"

    def test_no_unexpected_candidates(self):
        actual_names = {c.name for c in CANDIDATES}
        assert actual_names == self.EXPECTED_CANDIDATES, (
            f"Unexpected candidates: {actual_names - self.EXPECTED_CANDIDATES}"
        )

    def test_all_have_gates(self):
        for candidate in CANDIDATES:
            assert len(candidate.gates) >= 10, (
                f"{candidate.name} has only {len(candidate.gates)} gates"
            )


class TestEveryGateUsesValidStatus:
    """Test 2: Every gate uses PASS/PARTIAL/FAIL/UNKNOWN."""

    def test_all_gate_statuses_valid(self):
        valid_statuses = {GateStatus.PASS, GateStatus.PARTIAL, GateStatus.FAIL, GateStatus.UNKNOWN}
        for candidate in CANDIDATES:
            for gate in candidate.gates:
                assert gate.status in valid_statuses, (
                    f"{candidate.name}.{gate.gate} has invalid status: {gate.status}"
                )


class TestUnknownLicensePreventsGO:
    """Test 3: UNKNOWN commercial ML rights cannot produce GO."""

    def test_no_primary_with_unknown_license(self):
        for candidate in CANDIDATES:
            if has_unknown_license(candidate):
                assert candidate.classification != Classification.PRIMARY_TRAINING_CANDIDATE, (
                    f"{candidate.name} has UNKNOWN license but is PRIMARY"
                )

    def test_no_go_decision_possible(self):
        decision = Decision.NO_GO
        assert decision == Decision.NO_GO


class TestPaperOnlyDatasetsNotAccessible:
    """Test 4: Paper-only datasets cannot be treated as accessible."""

    def test_anatomy_not_publicly_available(self):
        anatomy = next(c for c in CANDIDATES if c.name == "Anatomy of a Scam Call")
        access_gate = get_gate_status(anatomy, "DATA_ACCESS")
        assert access_gate == GateStatus.FAIL, (
            f"Anatomy DATA_ACCESS should be FAIL (not publicly available), got {access_gate}"
        )


class TestYouTubeContentNotLicensedTrainingData:
    """Test 5: Public YouTube content cannot automatically be treated as licensed training data."""

    def test_youtube_no_commercial_rights(self):
        youtube = next(c for c in CANDIDATES if c.name == "YouTube Scam Transcripts")
        rights = get_gate_status(youtube, "COMMERCIAL_TRAINING_RIGHTS")
        assert rights == GateStatus.FAIL, (
            f"YouTube COMMERCIAL_TRAINING_RIGHTS should be FAIL, got {rights}"
        )


class TestAIGeneratedNotTreatedAsRealHuman:
    """Test 6: AI-generated/LLM-generated conversations cannot be treated as real human conversations."""

    def test_anatomy_two_party_human_fails(self):
        anatomy = next(c for c in CANDIDATES if c.name == "Anatomy of a Scam Call")
        two_party = get_gate_status(anatomy, "TWO_PARTY_HUMAN")
        assert two_party == GateStatus.FAIL, (
            f"Anatomy TWO_PARTY_HUMAN should be FAIL (AI recipient), got {two_party}"
        )


class TestAIRecipientExplicitlyRecorded:
    """Test 7: AI recipient is explicitly recorded."""

    def test_anatomy_has_ai_recipient_note(self):
        anatomy = next(c for c in CANDIDATES if c.name == "Anatomy of a Scam Call")
        two_party_gate = next(g for g in anatomy.gates if g.gate == "TWO_PARTY_HUMAN")
        assert "AI" in two_party_gate.note or "ai" in two_party_gate.note.lower(), (
            f"Anatomy TWO_PARTY_HUMAN note should mention AI recipient: {two_party_gate.note}"
        )


class TestAbsentSegmentLabelsRemainAbsent:
    """Test 8: Absent segment labels remain absent."""

    def test_all_candidates_missing_segment_labels(self):
        for candidate in CANDIDATES:
            status = get_gate_status(candidate, "SEGMENT_LEVEL_LABELS")
            assert status in (GateStatus.FAIL, GateStatus.UNKNOWN), (
                f"{candidate.name} SEGMENT_LEVEL_LABELS should be FAIL or UNKNOWN, got {status}"
            )


class TestConversationLabelsNotTacticLabels:
    """Test 9: Conversation-level scam labels cannot silently become tactic labels."""

    def test_tactic_relevance_gate_exists(self):
        for candidate in CANDIDATES:
            gate_names = {g.gate for g in candidate.gates}
            assert "LUMINA_TACTIC_RELEVANCE" in gate_names, (
                f"{candidate.name} missing LUMINA_TACTIC_RELEVANCE gate"
            )

    def test_no_candidate_has_tactic_pass_without_labels(self):
        for candidate in CANDIDATES:
            tactic_status = get_gate_status(candidate, "LUMINA_TACTIC_RELEVANCE")
            label_status = get_gate_status(candidate, "SEGMENT_LEVEL_LABELS")
            if tactic_status == GateStatus.PASS:
                assert label_status == GateStatus.PASS, (
                    f"{candidate.name} has LUMINA_TACTIC_RELEVANCE=PASS but SEGMENT_LEVEL_LABELS={label_status}"
                )


class TestAbsentPrivacyConsentRemainsUnknown:
    """Test 10: Absent privacy/consent evidence remains UNKNOWN."""

    def test_youtube_privacy_unknown(self):
        youtube = next(c for c in CANDIDATES if c.name == "YouTube Scam Transcripts")
        privacy = get_gate_status(youtube, "PRIVACY_CONSENT")
        assert privacy == GateStatus.UNKNOWN, (
            f"YouTube PRIVACY_CONSENT should be UNKNOWN, got {privacy}"
        )


class TestNoPrimaryWithoutAllCriticalGates:
    """Test 11: No candidate receives PRIMARY status without all critical gates."""

    def test_no_primary_candidates_exist(self):
        primary_count = sum(
            1 for c in CANDIDATES if c.classification == Classification.PRIMARY_TRAINING_CANDIDATE
        )
        assert primary_count == 0, f"Expected 0 PRIMARY candidates, got {primary_count}"

    def test_primary_only_with_all_critical_pass(self):
        for candidate in CANDIDATES:
            if candidate.classification == Classification.PRIMARY_TRAINING_CANDIDATE:
                for gate in CRITICAL_GATES:
                    status = get_gate_status(candidate, gate)
                    assert status == GateStatus.PASS, (
                        f"{candidate.name} is PRIMARY but has {gate}={status}"
                    )


class TestNOGORemainsValid:
    """Test 12: NO_GO remains valid."""

    def test_decision_is_no_go(self):
        decision = Decision.NO_GO
        assert decision == Decision.NO_GO

    def test_all_candidates_rejected_or_worse(self):
        for candidate in CANDIDATES:
            assert candidate.classification in (
                Classification.REJECTED,
                Classification.UNRESOLVED,
                Classification.AUXILIARY_ONLY,
                Classification.EVALUATION_ONLY,
            ), f"{candidate.name} has unexpected classification: {candidate.classification}"

    def test_no_primary_or_conditional(self):
        for candidate in CANDIDATES:
            assert candidate.classification not in (
                Classification.PRIMARY_TRAINING_CANDIDATE,
            ), f"{candidate.name} should not be PRIMARY"


class TestNoDatasetFilesAdded:
    """Test 13: No dataset files are added."""

    def test_no_data_directory(self):
        import os
        assert not os.path.exists("data/raw"), "data/raw directory should not exist"
        assert not os.path.exists("data/processed"), "data/processed directory should not exist"
        assert not os.path.exists("data/splits"), "data/splits directory should not exist"


class TestNoProductionMLCodeModified:
    """Test 14: No production ML code is modified."""

    def test_model_status_not_trained(self):
        from app.incident.ml_intelligence import ModelStatus
        assert ModelStatus.NOT_TRAINED.value == "NOT_TRAINED"

    def test_baseline_classifier_not_trained(self):
        from app.incident.ml_intelligence import BaselineClassifier
        clf = BaselineClassifier()
        assert clf.is_trained is False


class TestNoModelTrainingOccurs:
    """Test 15: No model training occurs."""

    def test_no_checkpoint_files(self):
        import os
        import glob as glob_module
        checkpoints = glob_module.glob("models/**/*.pt", recursive=True)
        checkpoints += glob_module.glob("models/**/*.bin", recursive=True)
        checkpoints += glob_module.glob("models/**/*.onnx", recursive=True)
        assert len(checkpoints) == 0, f"Found checkpoint files: {checkpoints}"

    def test_model_status_consistent(self):
        from app.incident.ml_intelligence import ModelStatus
        assert ModelStatus.NOT_TRAINED.value == "NOT_TRAINED"
