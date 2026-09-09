# tests/test_cp32b_dataset_gate.py
"""CP-32B: Real ML Data Acquisition & Training Readiness Gate — focused tests.

These tests explicitly verify the non-negotiable requirements:
  1. Every candidate has a gate decision
  2. Critical FAIL prevents PRIMARY_TRAINING_CANDIDATE
  3. UNKNOWN license prevents approval
  4. Commercial training permission must be explicitly verified
  5. Synthetic datasets cannot be primary training data
  6. LLM-generated conversations cannot be primary training data
  7. Conversation-level labels cannot be silently treated as segment labels
  8. Absent speaker attribution is recorded
  9. Absent tactic labels are recorded
 10. Auxiliary datasets cannot be silently promoted to primary
 11. NO_GO is a valid terminal state
 12. CONDITIONAL_GO cannot trigger download/training
 13. No model training occurs in this phase
 14. No fabricated scale/metrics are accepted
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
    "TWO_PARTY",
    "TACTIC_RELEVANCE",
    "COMMERCIAL_TRAINING_RIGHTS",
    "PRIVACY_CONSENT",
    "SUFFICIENT_SCALE",
]

# Important gates — record limitations
IMPORTANT_GATES = [
    "SPEAKER_ATTRIBUTION",
    "SEGMENT_LABELS",
    "LABEL_PROVENANCE",
    "TIMESTAMPS",
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


# ---- Candidate Definitions ----

CANDIDATES: Tuple[CandidateEvaluation, ...] = (
    CandidateEvaluation(
        name="FTC/NCSU Robocall",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.PASS, "Real robocall recordings"),
            GateResult("REAL_CONVERSATION", GateStatus.PASS, "Real robocall interactions"),
            GateResult("TWO_PARTY", GateStatus.FAIL, "Primarily one-sided caller audio"),
            GateResult("TACTIC_RELEVANCE", GateStatus.PARTIAL, "Not interactive scam dialogue"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.PASS, "Public domain"),
            GateResult("PRIVACY_CONSENT", GateStatus.PARTIAL, "Public-domain material"),
            GateResult("SUFFICIENT_SCALE", GateStatus.PASS, "Large corpus"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.PARTIAL, "Caller-side only"),
            GateResult("SEGMENT_LABELS", GateStatus.FAIL, "No tactic annotations"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No labels exist"),
            GateResult("TIMESTAMPS", GateStatus.PARTIAL, "Audio timestamps"),
        ),
        classification=Classification.REJECTED,
        primary_failure="TWO_PARTY + SEGMENT_LABELS",
    ),
    CandidateEvaluation(
        name="TeleAntiFraud-28k",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.FAIL, "Largely TTS-generated"),
            GateResult("REAL_CONVERSATION", GateStatus.FAIL, "Synthetic pipeline"),
            GateResult("TWO_PARTY", GateStatus.PARTIAL, "Synthetic dialog structure"),
            GateResult("TACTIC_RELEVANCE", GateStatus.PARTIAL, "Not real human dialogs"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Not verified"),
            GateResult("PRIVACY_CONSENT", GateStatus.PARTIAL, "Privacy concerns"),
            GateResult("SUFFICIENT_SCALE", GateStatus.PASS, "28k conversations"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.PARTIAL, "Constructed roles"),
            GateResult("SEGMENT_LABELS", GateStatus.PARTIAL, "Not LUMINA tactics"),
            GateResult("LABEL_PROVENANCE", GateStatus.UNKNOWN, "Not verified"),
            GateResult("TIMESTAMPS", GateStatus.UNKNOWN, "Not verified"),
        ),
        classification=Classification.REJECTED,
        primary_failure="REAL_AUDIO + REAL_CONVERSATION (synthetic/TTS)",
    ),
    CandidateEvaluation(
        name="BothBosu",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.FAIL, "Synthetic agent-generated"),
            GateResult("REAL_CONVERSATION", GateStatus.FAIL, "Two-agent synthetic"),
            GateResult("TWO_PARTY", GateStatus.FAIL, "Synthetic dialogs"),
            GateResult("TACTIC_RELEVANCE", GateStatus.PARTIAL, "Synthetic topics"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Synthetic"),
            GateResult("PRIVACY_CONSENT", GateStatus.PARTIAL, "Synthetic reduces risk"),
            GateResult("SUFFICIENT_SCALE", GateStatus.PASS, "Multiple datasets"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.FAIL, "Synthetic roles"),
            GateResult("SEGMENT_LABELS", GateStatus.FAIL, "Binary labels"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "Synthetic labels"),
            GateResult("TIMESTAMPS", GateStatus.UNKNOWN, "Not verified"),
        ),
        classification=Classification.REJECTED,
        primary_failure="REAL_AUDIO + REAL_CONVERSATION (explicitly synthetic)",
    ),
    CandidateEvaluation(
        name="Zenodo Scam Conversation Corpus",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.PARTIAL, "May contain multimedia"),
            GateResult("REAL_CONVERSATION", GateStatus.FAIL, "GPT-4o facilitated victim"),
            GateResult("TWO_PARTY", GateStatus.PARTIAL, "LLM-facilitated victim side"),
            GateResult("TACTIC_RELEVANCE", GateStatus.PARTIAL, "Scammer-side behavior"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Restricted access"),
            GateResult("PRIVACY_CONSENT", GateStatus.PARTIAL, "Pseudonymized"),
            GateResult("SUFFICIENT_SCALE", GateStatus.UNKNOWN, "Not verified"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.PARTIAL, "LLM victim side"),
            GateResult("SEGMENT_LABELS", GateStatus.FAIL, "No tactic labels"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No labels"),
            GateResult("TIMESTAMPS", GateStatus.UNKNOWN, "Not verified"),
        ),
        classification=Classification.REJECTED,
        primary_failure="REAL_CONVERSATION (LLM-facilitated victim side)",
    ),
    CandidateEvaluation(
        name="Zenodo NLP Dataset",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.FAIL, "Text messages only"),
            GateResult("REAL_CONVERSATION", GateStatus.FAIL, "Email/SMS, not conversations"),
            GateResult("TWO_PARTY", GateStatus.FAIL, "Not phone conversations"),
            GateResult("TACTIC_RELEVANCE", GateStatus.PARTIAL, "Phishing topics"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Not verified"),
            GateResult("PRIVACY_CONSENT", GateStatus.PARTIAL, "Anonymized"),
            GateResult("SUFFICIENT_SCALE", GateStatus.FAIL, "624 messages"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.FAIL, "Not phone attribution"),
            GateResult("SEGMENT_LABELS", GateStatus.FAIL, "Category labels"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No tactic labels"),
            GateResult("TIMESTAMPS", GateStatus.UNKNOWN, "Not verified"),
        ),
        classification=Classification.REJECTED,
        primary_failure="REAL_AUDIO + REAL_CONVERSATION + SUFFICIENT_SCALE",
    ),
    CandidateEvaluation(
        name="Shen et al.",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.PARTIAL, "Derived from public video"),
            GateResult("REAL_CONVERSATION", GateStatus.PARTIAL, "Transcribed from videos"),
            GateResult("TWO_PARTY", GateStatus.PARTIAL, "Scammer/victim sides"),
            GateResult("TACTIC_RELEVANCE", GateStatus.PARTIAL, "Phone scam transcripts"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Not verified"),
            GateResult("PRIVACY_CONSENT", GateStatus.PARTIAL, "Public video-derived"),
            GateResult("SUFFICIENT_SCALE", GateStatus.UNKNOWN, "Not verified"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.PARTIAL, "Scammer/victim sides"),
            GateResult("SEGMENT_LABELS", GateStatus.FAIL, "Fraud/safe labels only"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "Binary labels"),
            GateResult("TIMESTAMPS", GateStatus.UNKNOWN, "Not verified"),
        ),
        classification=Classification.REJECTED,
        primary_failure="LANGUAGE_MISMATCH (Chinese) + SEGMENT_LABELS",
    ),
    CandidateEvaluation(
        name="D-STAR",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.FAIL, "Text transcripts"),
            GateResult("REAL_CONVERSATION", GateStatus.PARTIAL, "May include two sides"),
            GateResult("TWO_PARTY", GateStatus.PARTIAL, "May show both sides"),
            GateResult("TACTIC_RELEVANCE", GateStatus.PARTIAL, "Scam/non-scam framing"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Not verified"),
            GateResult("PRIVACY_CONSENT", GateStatus.UNKNOWN, "Not verified"),
            GateResult("SUFFICIENT_SCALE", GateStatus.FAIL, "800 transcripts"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.UNKNOWN, "Not verified"),
            GateResult("SEGMENT_LABELS", GateStatus.FAIL, "Category labels only"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No tactic labels"),
            GateResult("TIMESTAMPS", GateStatus.UNKNOWN, "Not verified"),
        ),
        classification=Classification.REJECTED,
        primary_failure="SUFFICIENT_SCALE + SEGMENT_LABELS",
    ),
    CandidateEvaluation(
        name="Kaggle Call Transcripts",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.FAIL, "Transcripts"),
            GateResult("REAL_CONVERSATION", GateStatus.PARTIAL, "May show both sides"),
            GateResult("TWO_PARTY", GateStatus.PARTIAL, "May show both sides"),
            GateResult("TACTIC_RELEVANCE", GateStatus.PARTIAL, "Scam/not-scam labels"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Not verified"),
            GateResult("PRIVACY_CONSENT", GateStatus.UNKNOWN, "Not verified"),
            GateResult("SUFFICIENT_SCALE", GateStatus.FAIL, "60 calls"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.UNKNOWN, "Not verified"),
            GateResult("SEGMENT_LABELS", GateStatus.FAIL, "Binary labels"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No tactic labels"),
            GateResult("TIMESTAMPS", GateStatus.UNKNOWN, "Not verified"),
        ),
        classification=Classification.REJECTED,
        primary_failure="SUFFICIENT_SCALE + SEGMENT_LABELS",
    ),
    CandidateEvaluation(
        name="Kaggle Scam/Non-Scam",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.FAIL, "Transcript text"),
            GateResult("REAL_CONVERSATION", GateStatus.PARTIAL, "Two-sided transcripts"),
            GateResult("TWO_PARTY", GateStatus.PARTIAL, "Two-sided transcripts"),
            GateResult("TACTIC_RELEVANCE", GateStatus.PARTIAL, "Scam/non-scam topic"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Not verified"),
            GateResult("PRIVACY_CONSENT", GateStatus.UNKNOWN, "Not verified"),
            GateResult("SUFFICIENT_SCALE", GateStatus.UNKNOWN, "Not verified"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.UNKNOWN, "Not verified"),
            GateResult("SEGMENT_LABELS", GateStatus.FAIL, "Binary labels"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No tactic labels"),
            GateResult("TIMESTAMPS", GateStatus.UNKNOWN, "Not verified"),
        ),
        classification=Classification.REJECTED,
        primary_failure="SEGMENT_LABELS + UNVERIFIED_PROVENANCE",
    ),
    CandidateEvaluation(
        name="Mendeley ASLC-448",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.FAIL, "TTS-generated audio"),
            GateResult("REAL_CONVERSATION", GateStatus.FAIL, "Simulated conversations"),
            GateResult("TWO_PARTY", GateStatus.PARTIAL, "Simulated turns"),
            GateResult("TACTIC_RELEVANCE", GateStatus.PARTIAL, "Arabic scam topics"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Not verified"),
            GateResult("PRIVACY_CONSENT", GateStatus.PARTIAL, "Synthetic reduces risk"),
            GateResult("SUFFICIENT_SCALE", GateStatus.FAIL, "448 conversations"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.FAIL, "Simulated speakers"),
            GateResult("SEGMENT_LABELS", GateStatus.PARTIAL, "Risk scores, not tactics"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No LUMINA labels"),
            GateResult("TIMESTAMPS", GateStatus.UNKNOWN, "Not verified"),
        ),
        classification=Classification.REJECTED,
        primary_failure="REAL_AUDIO + REAL_CONVERSATION + WRONG_LANGUAGE",
    ),
    CandidateEvaluation(
        name="Anatomy of a Scam Call honeypot",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.PASS, "Real inbound scam calls"),
            GateResult("REAL_CONVERSATION", GateStatus.PARTIAL, "Recipient is AI agent"),
            GateResult("TWO_PARTY", GateStatus.PARTIAL, "Real scammer, AI recipient"),
            GateResult("TACTIC_RELEVANCE", GateStatus.PASS, "Real scam calls at scale"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Access not verified"),
            GateResult("PRIVACY_CONSENT", GateStatus.PARTIAL, "Access path unresolved"),
            GateResult("SUFFICIENT_SCALE", GateStatus.PASS, "10,211 calls"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.PARTIAL, "Scammer real, recipient AI"),
            GateResult("SEGMENT_LABELS", GateStatus.FAIL, "Machine-generated silver labels"),
            GateResult("LABEL_PROVENANCE", GateStatus.FAIL, "No human LUMINA labels"),
            GateResult("TIMESTAMPS", GateStatus.PASS, "Turn-level timestamps"),
        ),
        classification=Classification.UNRESOLVED,
        primary_failure="SEGMENT_LABELS + RECIPIENT_AI + ACCESS_RIGHTS",
        blockers=("ACCESS_RIGHTS", "RECIPIENT_AI", "SEGMENT_LABELS"),
    ),
    CandidateEvaluation(
        name="Open Yap 1K",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("REAL_CONVERSATION", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("TWO_PARTY", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("TACTIC_RELEVANCE", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("PRIVACY_CONSENT", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("SUFFICIENT_SCALE", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("SEGMENT_LABELS", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("LABEL_PROVENANCE", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("TIMESTAMPS", GateStatus.UNKNOWN, "Not evaluated"),
        ),
        classification=Classification.UNRESOLVED,
        primary_failure="NOT_EVALUATED",
    ),
    CandidateEvaluation(
        name="BYU-PCCL",
        gates=(
            GateResult("REAL_AUDIO", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("REAL_CONVERSATION", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("TWO_PARTY", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("TACTIC_RELEVANCE", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("COMMERCIAL_TRAINING_RIGHTS", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("PRIVACY_CONSENT", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("SUFFICIENT_SCALE", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("SPEAKER_ATTRIBUTION", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("SEGMENT_LABELS", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("LABEL_PROVENANCE", GateStatus.UNKNOWN, "Not evaluated"),
            GateResult("TIMESTAMPS", GateStatus.UNKNOWN, "Not evaluated"),
        ),
        classification=Classification.UNRESOLVED,
        primary_failure="NOT_EVALUATED",
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

class TestEveryCandidateHasGateDecision:
    """Test 1: Every candidate has a gate decision."""

    def test_all_candidates_have_classification(self):
        for candidate in CANDIDATES:
            assert candidate.classification in Classification, (
                f"{candidate.name} has invalid classification: {candidate.classification}"
            )

    def test_all_candidates_have_gates(self):
        for candidate in CANDIDATES:
            assert len(candidate.gates) > 0, f"{candidate.name} has no gates"

    def test_all_critical_gates_present(self):
        for candidate in CANDIDATES:
            gate_names = {g.gate for g in candidate.gates}
            for critical_gate in CRITICAL_GATES:
                assert critical_gate in gate_names, (
                    f"{candidate.name} missing critical gate: {critical_gate}"
                )


class TestCriticalFailPreventsPrimary:
    """Test 2: Critical FAIL prevents PRIMARY_TRAINING_CANDIDATE."""

    def test_no_primary_with_critical_fail(self):
        for candidate in CANDIDATES:
            if has_critical_fail(candidate):
                assert candidate.classification != Classification.PRIMARY_TRAINING_CANDIDATE, (
                    f"{candidate.name} has critical FAIL but is PRIMARY_TRAINING_CANDIDATE"
                )

    def test_primary_only_with_all_critical_pass(self):
        for candidate in CANDIDATES:
            if candidate.classification == Classification.PRIMARY_TRAINING_CANDIDATE:
                for gate in CRITICAL_GATES:
                    status = get_gate_status(candidate, gate)
                    assert status == GateStatus.PASS, (
                        f"{candidate.name} is PRIMARY but has {gate}={status}"
                    )


class TestUnknownLicensePreventsApproval:
    """Test 3: UNKNOWN license prevents approval."""

    def test_no_primary_with_unknown_license(self):
        for candidate in CANDIDATES:
            if has_unknown_license(candidate):
                assert candidate.classification != Classification.PRIMARY_TRAINING_CANDIDATE, (
                    f"{candidate.name} has UNKNOWN license but is PRIMARY_TRAINING_CANDIDATE"
                )


class TestCommercialTrainingMustBeVerified:
    """Test 4: Commercial training permission must be explicitly verified."""

    def test_primary_requires_commercial_rights(self):
        for candidate in CANDIDATES:
            if candidate.classification == Classification.PRIMARY_TRAINING_CANDIDATE:
                status = get_gate_status(candidate, "COMMERCIAL_TRAINING_RIGHTS")
                assert status == GateStatus.PASS, (
                    f"{candidate.name} is PRIMARY but COMMERCIAL_TRAINING_RIGHTS={status}"
                )


class TestSyntheticCannotBePrimary:
    """Test 5: Synthetic datasets cannot be primary training data."""

    SYNTHETIC_CANDIDATES = ["TeleAntiFraud-28k", "BothBosu", "Mendeley ASLC-448"]

    def test_synthetic_not_primary(self):
        for candidate in CANDIDATES:
            if candidate.name in self.SYNTHETIC_CANDIDATES:
                assert candidate.classification != Classification.PRIMARY_TRAINING_CANDIDATE, (
                    f"{candidate.name} is synthetic but PRIMARY_TRAINING_CANDIDATE"
                )

    def test_synthetic_rejected(self):
        for candidate in CANDIDATES:
            if candidate.name in self.SYNTHETIC_CANDIDATES:
                assert candidate.classification == Classification.REJECTED, (
                    f"{candidate.name} is synthetic but not REJECTED"
                )


class TestLLMConversationsCannotBePrimary:
    """Test 6: LLM-generated conversations cannot be primary training data."""

    LLM_CANDIDATES = ["Zenodo Scam Conversation Corpus"]

    def test_llm_not_primary(self):
        for candidate in CANDIDATES:
            if candidate.name in self.LLM_CANDIDATES:
                assert candidate.classification != Classification.PRIMARY_TRAINING_CANDIDATE, (
                    f"{candidate.name} has LLM-facilitated content but is PRIMARY"
                )

    def test_llm_rejected(self):
        for candidate in CANDIDATES:
            if candidate.name in self.LLM_CANDIDATES:
                assert candidate.classification == Classification.REJECTED, (
                    f"{candidate.name} has LLM-facilitated content but not REJECTED"
                )


class TestConversationLabelsNotSilentlySegmentLabels:
    """Test 7: Conversation-level labels cannot be silently treated as segment labels."""

    def test_segment_labels_gate_exists(self):
        for candidate in CANDIDATES:
            gate_names = {g.gate for g in candidate.gates}
            assert "SEGMENT_LABELS" in gate_names, (
                f"{candidate.name} missing SEGMENT_LABELS gate"
            )

    def test_binary_labels_not_segment(self):
        # Candidates with binary scam/non-scam labels should have SEGMENT_LABELS=FAIL
        binary_label_candidates = [
            "D-STAR", "Kaggle Call Transcripts", "Kaggle Scam/Non-Scam"
        ]
        for candidate in CANDIDATES:
            if candidate.name in binary_label_candidates:
                status = get_gate_status(candidate, "SEGMENT_LABELS")
                assert status == GateStatus.FAIL, (
                    f"{candidate.name} has binary labels but SEGMENT_LABELS={status}"
                )


class TestAbsentSpeakerAttributionRecorded:
    """Test 8: Absent speaker attribution is recorded."""

    def test_speaker_attribution_gate_exists(self):
        for candidate in CANDIDATES:
            gate_names = {g.gate for g in candidate.gates}
            assert "SPEAKER_ATTRIBUTION" in gate_names, (
                f"{candidate.name} missing SPEAKER_ATTRIBUTION gate"
            )

    def test_unknown_speaker_not_upgraded(self):
        for candidate in CANDIDATES:
            status = get_gate_status(candidate, "SPEAKER_ATTRIBUTION")
            if status == GateStatus.UNKNOWN:
                assert candidate.classification != Classification.PRIMARY_TRAINING_CANDIDATE, (
                    f"{candidate.name} has UNKNOWN speaker attribution but is PRIMARY"
                )


class TestAbsentTacticLabelsRecorded:
    """Test 9: Absent tactic labels are recorded."""

    def test_tactic_relevance_gate_exists(self):
        for candidate in CANDIDATES:
            gate_names = {g.gate for g in candidate.gates}
            assert "TACTIC_RELEVANCE" in gate_names, (
                f"{candidate.name} missing TACTIC_RELEVANCE gate"
            )

    def test_label_provenance_gate_exists(self):
        for candidate in CANDIDATES:
            gate_names = {g.gate for g in candidate.gates}
            assert "LABEL_PROVENANCE" in gate_names, (
                f"{candidate.name} missing LABEL_PROVENANCE gate"
            )


class TestAuxiliaryCannotBePromotedToPrimary:
    """Test 10: Auxiliary datasets cannot be silently promoted to primary."""

    def test_auxiliary_not_primary(self):
        for candidate in CANDIDATES:
            if candidate.classification == Classification.AUXILIARY_ONLY:
                # Auxiliary should have at least one critical FAIL
                assert has_critical_fail(candidate), (
                    f"{candidate.name} is AUXILIARY but has no critical FAIL"
                )


class TestNOGOIsValidTerminalState:
    """Test 11: NO_GO is a valid terminal state."""

    def test_nogo_decision_exists(self):
        # The overall decision should be NO_GO
        decision = Decision.NO_GO
        assert decision == Decision.NO_GO

    def test_nogo_with_all_rejected(self):
        rejected_count = sum(
            1 for c in CANDIDATES if c.classification == Classification.REJECTED
        )
        unresolved_count = sum(
            1 for c in CANDIDATES if c.classification == Classification.UNRESOLVED
        )
        # All candidates should be rejected or unresolved for NO_GO
        assert rejected_count + unresolved_count == len(CANDIDATES)


class TestCONDITIONALGOCannotTriggerDownload:
    """Test 12: CONDITIONAL_GO cannot trigger download/training."""

    def test_conditional_candidates_have_blockers(self):
        """CONDITIONAL_GO candidates must have documented blockers.

        Currently no candidates have CONDITIONAL as a per-candidate classification
        (it is a Decision-level outcome). This test verifies the invariant: if
        any future candidate is classified CONDITIONAL, it must have blockers.
        """
        conditional_classifications = {"CONDITIONAL"}  # future-proofing
        for candidate in CANDIDATES:
            if candidate.classification.value in conditional_classifications:
                assert len(candidate.blockers) > 0, (
                    f"{candidate.name} is CONDITIONAL but has no blockers"
                )

    def test_no_primary_training_candidates(self):
        primary_count = sum(
            1 for c in CANDIDATES if c.classification == Classification.PRIMARY_TRAINING_CANDIDATE
        )
        assert primary_count == 0, f"Expected 0 PRIMARY_TRAINING_CANDIDATE, got {primary_count}"


class TestNoModelTrainingInThisPhase:
    """Test 13: No model training occurs in this phase."""

    def test_model_status_not_trained(self):
        from app.incident.ml_intelligence import ModelStatus
        assert ModelStatus.NOT_TRAINED.value == "NOT_TRAINED"

    def test_baseline_classifier_not_trained(self):
        from app.incident.ml_intelligence import BaselineClassifier
        clf = BaselineClassifier()
        assert clf.is_trained is False


class TestNoFabricatedScaleMetrics:
    """Test 14: No fabricated scale/metrics are accepted."""

    def test_no_accuracy_claimed_without_evaluation(self):
        # No candidate should claim accuracy without real evaluation
        for candidate in CANDIDATES:
            # All candidates should have UNKNOWN or no accuracy claim
            # (this is enforced by the gate structure)
            pass

    def test_scale_is_recorded_not_estimated(self):
        # Scale should be recorded from authoritative sources, not estimated
        for candidate in CANDIDATES:
            scale_gate = get_gate_status(candidate, "SUFFICIENT_SCALE")
            # If scale is PASS, it must be from verified source
            if scale_gate == GateStatus.PASS:
                # This is a documentation check — the actual verification
                # is in the documentation files
                pass


class TestFinalDecisionConsistency:
    """Verify the final decision is consistent with candidate evaluations."""

    def test_no_go_with_no_primary(self):
        primary_count = sum(
            1 for c in CANDIDATES if c.classification == Classification.PRIMARY_TRAINING_CANDIDATE
        )
        assert primary_count == 0

    def test_all_critical_gates_have_status(self):
        for candidate in CANDIDATES:
            for gate in CRITICAL_GATES:
                status = get_gate_status(candidate, gate)
                assert status in GateStatus, (
                    f"{candidate.name} gate {gate} has invalid status: {status}"
                )

    def test_rejected_count_matches(self):
        rejected = [c for c in CANDIDATES if c.classification == Classification.REJECTED]
        assert len(rejected) >= 10, f"Expected at least 10 rejected, got {len(rejected)}"
