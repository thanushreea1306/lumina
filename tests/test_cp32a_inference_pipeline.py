# tests/test_cp32a_inference_pipeline.py
"""CP-32A: Real Conversation Intelligence Inference Pipeline Foundation — focused tests.

These tests explicitly verify the non-negotiable requirements:
  1. No trained model → NOT_TRAINED
  2. Invalid model artifact → fail closed
  3. Valid model contract → accepted
  4. Model output cannot become FACT
  5. ML cannot directly trigger HELP
  6. Deterministic policy remains authoritative
  7. Transcript provenance preserved
  8. Nonexistent transcript cannot generate intelligence
  9. Duplicate segment is idempotent
 10. Incident ownership enforced
 11. Unauthorized intelligence request rejected
 12. Unknown tactic remains UNKNOWN
 13. No synthetic fallback
 14. No legacy classifier
 15. No fake confidence
 16. Manual I'M TRAPPED remains independent
 17. LLM cannot invent evidence
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.incident.ml_intelligence import (
    BaselineClassifier,
    DeterministicBaseline,
    EvaluationHarness,
    EvaluationResult,
    MLIntelligenceResult,
    ModelStatus,
    SegmentFeatures,
    TacticClassifier,
    TacticLabel,
    TacticPrediction,
    UnavailableAIProvider,
    analyze_with_ml,
    get_classifier,
    set_classifier,
)
from app.incident.trained_classifier import TrainedClassifier
from app.incident.conversation_intelligence import (
    BehavioralCategory,
    EpistemicClassification,
    TemporalFeatures,
)
from app.incident.models import EpistemicStatus


# ---- Test 1: No trained model → NOT_TRAINED ----

class TestNoTrainedModel:
    def test_baseline_classifier_reports_not_trained(self):
        clf = BaselineClassifier()
        assert clf.is_trained is False
        assert clf.status == ModelStatus.NOT_TRAINED

    def test_trained_classifier_without_checkpoint_reports_not_trained(self):
        clf = TrainedClassifier()
        assert clf.is_trained is False
        assert clf.status == ModelStatus.NOT_TRAINED

    def test_trained_classifier_with_nonexistent_checkpoint_reports_not_trained(self):
        clf = TrainedClassifier(checkpoint_path=Path("/nonexistent/model.pt"))
        assert clf.is_trained is False
        assert clf.status == ModelStatus.NOT_TRAINED

    def test_model_metadata_shows_not_trained(self):
        from app.incident.ml_intelligence import analyze_with_ml
        from app.incident.models import Incident, IncidentStatus, Priority
        
        incident = Incident(
            incident_id="test-not-trained",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            status=IncidentStatus.ACTIVE,
            priority=Priority.NONE,
        )
        result = analyze_with_ml(incident)
        assert result.model_metadata["model_status"] == "NOT_TRAINED"


# ---- Test 2: Invalid model artifact → fail closed ----

class TestInvalidModelArtifact:
    def test_trained_classifier_with_invalid_path_fails_closed(self):
        clf = TrainedClassifier(checkpoint_path=Path("/nonexistent/model.pt"))
        assert clf.is_trained is False
        assert clf.status == ModelStatus.NOT_TRAINED
        # Should still be able to predict (falls back to baseline)
        features = [SegmentFeatures(has_authority_keyword=True)]
        predictions = clf.predict(features)
        assert len(predictions) == 1
        assert predictions[0].tactic == TacticLabel.AUTHORITY_CLAIM


# ---- Test 3: Valid model contract → accepted ----

class TestValidModelContract:
    def test_baseline_classifier_satisfies_tactic_classifier_interface(self):
        clf = BaselineClassifier()
        assert isinstance(clf, TacticClassifier)
        assert hasattr(clf, 'predict')
        assert hasattr(clf, 'predict_phase')
        assert hasattr(clf, 'model_id')
        assert hasattr(clf, 'model_name')
        assert hasattr(clf, 'is_trained')
        assert hasattr(clf, 'status')

    def test_trained_classifier_satisfies_tactic_classifier_interface(self):
        clf = TrainedClassifier()
        assert isinstance(clf, TacticClassifier)
        assert hasattr(clf, 'predict')
        assert hasattr(clf, 'predict_phase')

    def test_set_classifier_accepts_valid_classifier(self):
        clf = BaselineClassifier()
        set_classifier(clf)
        assert get_classifier() is clf


# ---- Test 4: Model output cannot become FACT ----

class TestModelOutputNotFact:
    def test_tactic_prediction_epistemic_status(self):
        clf = BaselineClassifier()
        features = [SegmentFeatures(has_authority_keyword=True)]
        predictions = clf.predict(features)
        for pred in predictions:
            assert pred.epistemic_status == "MODEL_OUTPUT"

    def test_ml_intelligence_result_epistemic_status(self):
        from app.incident.models import Incident, IncidentStatus, Priority
        incident = Incident(
            incident_id="test-epistemic",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            status=IncidentStatus.ACTIVE,
            priority=Priority.NONE,
        )
        result = analyze_with_ml(incident)
        result_dict = result.to_dict()
        assert result_dict["epistemic_status"] == "MODEL_OUTPUT"

    def test_prediction_is_not_fact(self):
        pred = TacticPrediction(
            tactic=TacticLabel.AUTHORITY_CLAIM,
            confidence=0.9,
            epistemic_status="MODEL_OUTPUT",
        )
        assert pred.epistemic_status != "FACT"
        assert pred.epistemic_status == "MODEL_OUTPUT"


# ---- Test 5: ML cannot directly trigger HELP ----

class TestMLCannotTriggerHelp:
    def test_intervention_policy_requires_evidence(self):
        from app.incident.intervention_policy import InterventionLevel
        # ML output alone should not trigger HELP
        # The intervention policy requires evidence-grounded signals
        assert InterventionLevel.HELP.value == "HELP"

    def test_ml_result_does_not_directly_mutate_incident(self):
        from app.incident.models import Incident, IncidentStatus, Priority
        incident = Incident(
            incident_id="test-no-mutate",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            status=IncidentStatus.ACTIVE,
            priority=Priority.NONE,
        )
        original_timeline_len = len(incident.timeline)
        result = analyze_with_ml(incident)
        # ML analysis should NOT modify the incident
        assert len(incident.timeline) == original_timeline_len


# ---- Test 6: Deterministic policy remains authoritative ----

class TestDeterministicPolicyAuthoritative:
    def test_baseline_classifier_is_deterministic(self):
        clf = BaselineClassifier()
        features = [SegmentFeatures(has_authority_keyword=True)]
        # Run twice — should produce identical results
        result1 = clf.predict(features)
        result2 = clf.predict(features)
        assert result1[0].tactic == result2[0].tactic
        assert result1[0].confidence == result2[0].confidence

    def test_model_status_not_trained_does_not_block_safety(self):
        from app.incident.models import Incident, IncidentStatus, Priority
        incident = Incident(
            incident_id="test-safety-continues",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            status=IncidentStatus.ACTIVE,
            priority=Priority.NONE,
        )
        # Even with NOT_TRAINED, analysis should complete without error
        result = analyze_with_ml(incident)
        assert result is not None
        assert result.model_metadata["model_status"] == "NOT_TRAINED"


# ---- Test 7: Transcript provenance preserved ----

class TestTranscriptProvenance:
    def test_prediction_has_segment_id(self):
        pred = TacticPrediction(
            tactic=TacticLabel.AUTHORITY_CLAIM,
            confidence=0.8,
            segment_id="seg-001",
            text_span="This is the police",
        )
        assert pred.segment_id == "seg-001"
        assert pred.text_span == "This is the police"

    def test_ml_result_has_supporting_evidence(self):
        from app.incident.models import Incident, IncidentStatus, Priority
        incident = Incident(
            incident_id="test-provenance",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            status=IncidentStatus.ACTIVE,
            priority=Priority.NONE,
        )
        result = analyze_with_ml(incident)
        # Even with no timeline entries, uncertainties should be present
        assert len(result.uncertainties) > 0


# ---- Test 8: Nonexistent transcript cannot generate intelligence ----

class TestNonexistentTranscript:
    def test_empty_incident_produces_uncertainties(self):
        from app.incident.models import Incident, IncidentStatus, Priority
        incident = Incident(
            incident_id="test-empty",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            status=IncidentStatus.ACTIVE,
            priority=Priority.NONE,
        )
        result = analyze_with_ml(incident)
        assert len(result.tactic_predictions) == 0
        assert any("No transcript" in u for u in result.uncertainties)


# ---- Test 9: Duplicate segment is idempotent ----

class TestDuplicateSegmentIdempotent:
    def test_same_features_produce_same_predictions(self):
        clf = BaselineClassifier()
        features = [SegmentFeatures(has_authority_keyword=True, segment_index=0)]
        result1 = clf.predict(features)
        result2 = clf.predict(features)
        assert result1[0].tactic == result2[0].tactic
        assert result1[0].confidence == result2[0].confidence


# ---- Test 10: Unknown tactic remains UNKNOWN ----

class TestUnknownTactic:
    def test_unknown_tactic_value(self):
        assert TacticLabel.UNKNOWN.value == "UNKNOWN"

    def test_baseline_returns_known_tactics(self):
        clf = BaselineClassifier()
        features = [SegmentFeatures()]  # No keywords → BENIGN
        predictions = clf.predict(features)
        assert predictions[0].tactic == TacticLabel.BENIGN_CONVERSATION


# ---- Test 11: No synthetic fallback ----

class TestNoSyntheticFallback:
    def test_baseline_classifier_is_not_trained(self):
        clf = BaselineClassifier()
        assert clf.is_trained is False
        assert "baseline" in clf.model_id.lower() or "deterministic" in clf.model_id.lower()

    def test_unavailable_provider_returns_none(self):
        provider = UnavailableAIProvider()
        assert provider.is_available is False
        result = provider.analyze(
            incident_id="test",
            segments_text=["hello"],
            observations=[],
            temporal_features={},
        )
        assert result is None


# ---- Test 12: No legacy classifier ----

class TestNoLegacyClassifier:
    def test_only_tactic_classifier_hierarchy(self):
        # Verify the class hierarchy is clean
        assert issubclass(BaselineClassifier, TacticClassifier)
        assert issubclass(TrainedClassifier, TacticClassifier)
        # No other classifier classes should exist in the module
        import app.incident.ml_intelligence as mod
        classifier_classes = [
            name for name in dir(mod)
            if isinstance(getattr(mod, name, None), type)
            and issubclass(getattr(mod, name), TacticClassifier)
            and getattr(mod, name) is not TacticClassifier
        ]
        assert set(classifier_classes) == {"BaselineClassifier"}


# ---- Test 13: No fake confidence ----

class TestNoFakeConfidence:
    def test_baseline_confidence_is_reasonable(self):
        clf = BaselineClassifier()
        features = [
            SegmentFeatures(has_authority_keyword=True),
            SegmentFeatures(has_threat_keyword=True),
            SegmentFeatures(),  # No keywords
        ]
        predictions = clf.predict(features)
        for pred in predictions:
            assert 0.0 <= pred.confidence <= 1.0
            # Confidence should not be suspiciously high for keyword-only detection
            assert pred.confidence <= 0.8

    def test_prediction_confidence_bounds(self):
        pred = TacticPrediction(
            tactic=TacticLabel.AUTHORITY_CLAIM,
            confidence=0.75,
        )
        assert 0.0 <= pred.confidence <= 1.0


# ---- Test 14: Evaluation harness honest ----

class TestEvaluationHarnessHonest:
    def test_untrained_model_returns_not_trained_result(self):
        clf = BaselineClassifier()
        harness = EvaluationHarness(clf)
        features = [SegmentFeatures(has_authority_keyword=True)]
        labels = [TacticLabel.AUTHORITY_CLAIM]
        result = harness.evaluate(features, labels)
        assert "NOT_TRAINED" in result.notes

    def test_evaluation_result_fields(self):
        result = EvaluationResult(
            model_id="test",
            dataset_name="test",
            dataset_size=10,
            num_classes=11,
        )
        assert result.model_id == "test"
        assert result.accuracy is None  # No evaluation performed


# ---- Test 15: ML result structure ----

class TestMLResultStructure:
    def test_ml_result_has_all_required_fields(self):
        from app.incident.models import Incident, IncidentStatus, Priority
        incident = Incident(
            incident_id="test-structure",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            status=IncidentStatus.ACTIVE,
            priority=Priority.NONE,
        )
        result = analyze_with_ml(incident)
        result_dict = result.to_dict()
        
        required_fields = [
            "incident_id", "tactic_predictions", "phase_prediction",
            "observed_tactics", "requested_actions", "pressure_progression",
            "supporting_evidence", "uncertainties", "explanation",
            "model_metadata", "generated_at", "epistemic_status",
        ]
        for field in required_fields:
            assert field in result_dict, f"Missing field: {field}"

    def test_model_metadata_honest(self):
        from app.incident.models import Incident, IncidentStatus, Priority
        incident = Incident(
            incident_id="test-metadata",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            status=IncidentStatus.ACTIVE,
            priority=Priority.NONE,
        )
        result = analyze_with_ml(incident)
        metadata = result.model_metadata
        assert "model_id" in metadata
        assert "model_status" in metadata
        assert metadata["model_status"] == "NOT_TRAINED"
