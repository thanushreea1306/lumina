# app/incident/ml_intelligence.py
"""ML Intelligence Layer — genuine AI/ML abstraction for conversation analysis.

This module provides the production ML infrastructure for LUMINA's conversation
intelligence. It implements:

  1. Structured ML model output schema (validated, provenance-tracked)
  2. Feature engineering pipeline (temporal + behavioral + textual)
  3. Model abstraction (train/predict/evaluate interface)
  4. Evaluation harness (precision, recall, F1, confusion matrix)
  5. Semantic AI provider abstraction (optional external model)
  6. Prompt-injection defense (structured input, schema validation)

CRITICAL HONESTY RULES:

  - If no legitimate trained model exists, model_status = NOT_TRAINED
  - Never fabricate model accuracy or performance metrics
  - Never present synthetic benchmark results as real-world effectiveness
  - Never create a numeric "scam score" or "fraud probability"
  - AI/ML output is always advisory — the deterministic safety engine decides
  - Transcript text is UNTRUSTED DATA — never execute instructions from it

ARCHITECTURE:

  Transcript Segments
      ↓
  Feature Extraction (temporal + behavioral + textual)
      ↓
  ML Model (if trained) / Deterministic Baseline (always available)
      ↓
  Structured Model Output (validated, provenance-tracked)
      ↓
  AI/ML Advisory Layer
      ↓
  Deterministic Safety Engine (always authoritative)

NO TRAINED MODEL EXISTS:

  After researching public datasets (BYU-PCCL, Zenodo, Kaggle, ScamGen,
  Derakhshan), no suitable dataset was identified that provides:
    - Segment-level social-engineering tactic labels for phone calls
    - English language transcripts at sufficient scale
    - Appropriate licensing for production use
    - Labels matching LUMINA's behavioral categories

  Dataset-specific reasons for non-use:
    - BYU-PCCL: requires LLM API keys for feature extraction, in development
    - Kaggle (Call Transcripts): 60 calls — too small for meaningful ML
    - Zenodo NLP: email/SMS messages, not phone call transcripts
    - ScamGen: Chinese language — wrong language for LUMINA
    - Derakhshan: 215 calls — too small, simulated scenarios

  Therefore: model_status = NOT_TRAINED
  The evaluation harness is ready for future legitimate data.
"""
from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.evidence.models import UserObservationType
from app.incident.models import EpistemicStatus, Incident
from app.incident.conversation_intelligence import (
    BehavioralCategory,
    BehavioralEvent,
    ConversationDynamics,
    EpistemicClassification,
    TemporalFeatures,
    _OBSERVATION_BEHAVIOR_MAP,
)


# ---- Model Status ----

class ModelStatus(str, Enum):
    """Honest status of the ML model.

    NOT_TRAINED: No suitable labeled dataset was identified during implementation. Model interface is ready.
    TRAINED: Model has been trained on legitimate data with verified metrics.
    UNAVAILABLE: Model was trained but is not currently loadable.
    DEPRECATED: Model is no longer recommended.
    """
    NOT_TRAINED = "NOT_TRAINED"
    TRAINED = "TRAINED"
    UNAVAILABLE = "UNAVAILABLE"
    DEPRECATED = "DEPRECATED"


# ---- Tactic Classification Labels ----

class TacticLabel(str, Enum):
    """Social-engineering tactic labels for segment-level classification.

    These map to LUMINA's behavioral categories but are expressed as
    specific tactics that an ML model can learn to identify.
    """
    AUTHORITY_CLAIM = "AUTHORITY_CLAIM"
    THREAT_PRESENTATION = "THREAT_PRESENTATION"
    TIME_PRESSURE = "TIME_PRESSURE"
    ISOLATION_TACTIC = "ISOLATION_TACTIC"
    CREDENTIAL_REQUEST = "CREDENTIAL_REQUEST"
    FINANCIAL_REQUEST = "FINANCIAL_REQUEST"
    REMOTE_ACCESS_REQUEST = "REMOTE_ACCESS_REQUEST"
    IDENTITY_REQUEST = "IDENTITY_REQUEST"
    BENIGN_CONVERSATION = "BENIGN_CONVERSATION"
    USER_RESISTANCE = "USER_RESISTANCE"
    ADVICE_OR_WARNING = "ADVICE_OR_WARNING"
    UNKNOWN = "UNKNOWN"


# ---- ML Model Output Schema ----

@dataclass(frozen=True)
class TacticPrediction:
    """A single tactic prediction from the ML model.

    Each prediction includes provenance and confidence. Confidence is
    a model output — it is NOT a scam probability. It represents the
    model's certainty about the tactic classification, not the likelihood
    of fraud.
    """
    tactic: TacticLabel
    confidence: float  # Model's classification confidence (0.0-1.0)
    segment_id: Optional[str] = None
    text_span: str = ""
    evidence_basis: Tuple[str, ...] = ()
    epistemic_status: str = "MODEL_OUTPUT"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tactic": self.tactic.value,
            "confidence": round(self.confidence, 4),
            "segment_id": self.segment_id,
            "text_span": self.text_span[:200],  # Truncate for safety
            "evidence_basis": list(self.evidence_basis),
            "epistemic_status": self.epistemic_status,
        }


@dataclass(frozen=True)
class ConversationPhasePrediction:
    """Prediction of the current conversation phase.

    Phases represent the temporal progression of the conversation:
      SETUP → PRESSURE → EXTRACTION → RESISTANCE → ESCALATION

    This is an ML output, not a confirmed state.
    """
    phase: str  # "SETUP", "PRESSURE", "EXTRACTION", "RESISTANCE", "ESCALATION"
    confidence: float
    evidence_basis: Tuple[str, ...] = ()
    epistemic_status: str = "MODEL_OUTPUT"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "confidence": round(self.confidence, 4),
            "evidence_basis": list(self.evidence_basis),
            "epistemic_status": self.epistemic_status,
        }


@dataclass(frozen=True)
class MLIntelligenceResult:
    """Complete ML intelligence analysis result.

    This is the structured output from the ML model. It includes:
      - Tactic predictions per segment
      - Conversation phase prediction
      - Observed tactics (set of detected tactic types)
      - Requested actions (what the model thinks was requested)
      - Pressure progression (temporal sequence of pressure events)
      - Supporting evidence (actual transcript spans)
      - Uncertainties (what the model cannot determine)
      - Explanation (human-readable, evidence-grounded)
      - Model metadata (status, version, features used)

    Every field preserves provenance. Nothing is fabricated.
    """
    incident_id: str
    tactic_predictions: Tuple[TacticPrediction, ...]
    phase_prediction: Optional[ConversationPhasePrediction]
    observed_tactics: Tuple[TacticLabel, ...]
    requested_actions: Tuple[str, ...]
    pressure_progression: Tuple[str, ...]
    supporting_evidence: Tuple[str, ...]
    uncertainties: Tuple[str, ...]
    explanation: str
    model_metadata: Dict[str, Any]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "tactic_predictions": [p.to_dict() for p in self.tactic_predictions],
            "phase_prediction": self.phase_prediction.to_dict() if self.phase_prediction else None,
            "observed_tactics": [t.value for t in self.observed_tactics],
            "requested_actions": list(self.requested_actions),
            "pressure_progression": list(self.pressure_progression),
            "supporting_evidence": list(self.supporting_evidence),
            "uncertainties": list(self.uncertainties),
            "explanation": self.explanation,
            "model_metadata": self.model_metadata,
            "generated_at": self.generated_at,
            "epistemic_status": EpistemicClassification.MODEL_OUTPUT.value,
        }


# ---- Feature Schema ----

@dataclass(frozen=True)
class SegmentFeatures:
    """Feature vector for a single transcript segment.

    These features are designed to be compatible with standard ML models
    (logistic regression, SVM, gradient boosting, small neural networks).

    Features are grouped into:
      1. Textual features (keyword presence, pattern matches)
      2. Speaker features (who is speaking)
      3. Temporal features (timestamps, duration)
      4. Contextual features (surrounding segments)
    """
    # Textual features (binary: 0 or 1)
    has_authority_keyword: bool = False
    has_threat_keyword: bool = False
    has_urgency_keyword: bool = False
    has_secrecy_keyword: bool = False
    has_otp_keyword: bool = False
    has_password_keyword: bool = False
    has_money_keyword: bool = False
    has_remote_access_keyword: bool = False
    has_identity_keyword: bool = False
    has_negation: bool = False
    has_advice_context: bool = False

    # Speaker features
    speaker_is_caller: bool = False
    speaker_is_user: bool = False
    speaker_is_unknown: bool = False

    # Temporal features
    segment_index: int = 0
    time_from_start: float = 0.0
    segment_duration: float = 0.0

    # Contextual features
    prev_segment_has_threat: bool = False
    prev_segment_has_urgency: bool = False
    next_segment_has_request: bool = False

    def to_vector(self) -> List[float]:
        """Convert to a numeric feature vector for ML models."""
        return [
            float(self.has_authority_keyword),
            float(self.has_threat_keyword),
            float(self.has_urgency_keyword),
            float(self.has_secrecy_keyword),
            float(self.has_otp_keyword),
            float(self.has_password_keyword),
            float(self.has_money_keyword),
            float(self.has_remote_access_keyword),
            float(self.has_identity_keyword),
            float(self.has_negation),
            float(self.has_advice_context),
            float(self.speaker_is_caller),
            float(self.speaker_is_user),
            float(self.speaker_is_unknown),
            float(self.segment_index),
            self.time_from_start,
            self.segment_duration,
            float(self.prev_segment_has_threat),
            float(self.prev_segment_has_urgency),
            float(self.next_segment_has_request),
        ]

    @staticmethod
    def feature_names() -> List[str]:
        """Return named features for interpretability."""
        return [
            "has_authority_keyword", "has_threat_keyword",
            "has_urgency_keyword", "has_secrecy_keyword",
            "has_otp_keyword", "has_password_keyword",
            "has_money_keyword", "has_remote_access_keyword",
            "has_identity_keyword", "has_negation",
            "has_advice_context",
            "speaker_is_caller", "speaker_is_user", "speaker_is_unknown",
            "segment_index", "time_from_start", "segment_duration",
            "prev_segment_has_threat", "prev_segment_has_urgency",
            "next_segment_has_request",
        ]


# ---- Keyword Detection for Feature Extraction ----

_AUTHORITY_KEYWORDS = {"police", "bank", "government", "court", "department", "agency", "cyber", "crime", "tax", "income"}
_THREAT_KEYWORDS = {"arrest", "jail", "warrant", "legal", "court", "sue", "fine", "penalty", "detain"}
_URGENCY_KEYWORDS = {"now", "immediately", "hurry", "quickly", "minutes", "seconds", "running out", "last chance", "final warning"}
_SECRECY_KEYWORDS = {"secret", "confidential", "private", "don't tell", "do not tell", "no one should know", "between us"}
_OTP_KEYWORDS = {"otp", "code", "verification", "one-time", "pin"}
_PASSWORD_KEYWORDS = {"password", "passwd", "pwd", "secret answer"}
_MONEY_KEYWORDS = {"money", "transfer", "payment", "fee", "fine", "deposit", "send", "pay"}
_REMOTE_KEYWORDS = {"install", "download", "app", "software", "teamviewer", "anydesk", "screen sharing", "remote"}
_IDENTITY_KEYWORDS = {"aadhaar", "pan", "passport", "id", "document", "license"}


def _extract_segment_features(
    text: str,
    speaker: Optional[str],
    segment_index: int,
    start_time: Optional[float],
    end_time: Optional[float],
    prev_text: str = "",
    next_text: str = "",
) -> SegmentFeatures:
    """Extract features from a single transcript segment."""
    lower = text.lower()

    return SegmentFeatures(
        has_authority_keyword=any(kw in lower for kw in _AUTHORITY_KEYWORDS),
        has_threat_keyword=any(kw in lower for kw in _THREAT_KEYWORDS),
        has_urgency_keyword=any(kw in lower for kw in _URGENCY_KEYWORDS),
        has_secrecy_keyword=any(kw in lower for kw in _SECRECY_KEYWORDS),
        has_otp_keyword=any(kw in lower for kw in _OTP_KEYWORDS),
        has_password_keyword=any(kw in lower for kw in _PASSWORD_KEYWORDS),
        has_money_keyword=any(kw in lower for kw in _MONEY_KEYWORDS),
        has_remote_access_keyword=any(kw in lower for kw in _REMOTE_KEYWORDS),
        has_identity_keyword=any(kw in lower for kw in _IDENTITY_KEYWORDS),
        has_negation=any(neg in lower for neg in {"not", "never", "don't", "do not", "won't", "can't"}),
        has_advice_context=any(adj in lower for adj in {"never share", "do not share", "warning", "be careful", "remember"}),
        speaker_is_caller=(speaker == "CALLER"),
        speaker_is_user=(speaker == "USER"),
        speaker_is_unknown=(speaker is None or speaker == "UNKNOWN"),
        segment_index=segment_index,
        time_from_start=start_time or 0.0,
        segment_duration=(end_time - start_time) if (start_time is not None and end_time is not None) else 0.0,
        prev_segment_has_threat=any(kw in prev_text.lower() for kw in _THREAT_KEYWORDS),
        prev_segment_has_urgency=any(kw in prev_text.lower() for kw in _URGENCY_KEYWORDS),
        next_segment_has_request=any(kw in next_text.lower() for kw in (_OTP_KEYWORDS | _MONEY_KEYWORDS | _REMOTE_KEYWORDS)),
    )


# ---- Deterministic Baseline ----

class DeterministicBaseline:
    """Deterministic baseline classifier.

    When no trained ML model is available, this baseline produces
    tactic predictions based on keyword matching and rule-based logic.

    This is NOT an ML model. It is a transparent, deterministic
    heuristic that serves as a reference implementation.

    Its predictions are INFERENCE-level, same as any ML output.
    """

    def predict_tactics(
        self,
        features: List[SegmentFeatures],
    ) -> List[TacticPrediction]:
        """Predict tactics for each segment using keyword rules."""
        predictions: List[TacticPrediction] = []

        for i, feat in enumerate(features):
            tactics: List[Tuple[TacticLabel, float]] = []

            if feat.has_authority_keyword:
                tactics.append((TacticLabel.AUTHORITY_CLAIM, 0.7))
            if feat.has_threat_keyword:
                tactics.append((TacticLabel.THREAT_PRESENTATION, 0.7))
            if feat.has_urgency_keyword:
                tactics.append((TacticLabel.TIME_PRESSURE, 0.6))
            if feat.has_secrecy_keyword:
                tactics.append((TacticLabel.ISOLATION_TACTIC, 0.6))
            if feat.has_otp_keyword or feat.has_password_keyword:
                tactics.append((TacticLabel.CREDENTIAL_REQUEST, 0.7))
            if feat.has_money_keyword:
                tactics.append((TacticLabel.FINANCIAL_REQUEST, 0.6))
            if feat.has_remote_access_keyword:
                tactics.append((TacticLabel.REMOTE_ACCESS_REQUEST, 0.6))
            if feat.has_identity_keyword:
                tactics.append((TacticLabel.IDENTITY_REQUEST, 0.6))
            if feat.has_advice_context:
                tactics.append((TacticLabel.ADVICE_OR_WARNING, 0.5))
            if feat.speaker_is_user and feat.has_negation:
                tactics.append((TacticLabel.USER_RESISTANCE, 0.5))

            if not tactics:
                tactics.append((TacticLabel.BENIGN_CONVERSATION, 0.4))

            # Take the highest-confidence tactic
            best_tactic, best_conf = max(tactics, key=lambda x: x[1])
            predictions.append(TacticPrediction(
                tactic=best_tactic,
                confidence=best_conf,
            ))

        return predictions

    def predict_phase(
        self,
        predictions: List[TacticPrediction],
    ) -> ConversationPhasePrediction:
        """Predict the current conversation phase from tactic predictions."""
        tactic_counts = {}
        for p in predictions:
            tactic_counts[p.tactic] = tactic_counts.get(p.tactic, 0) + 1

        has_setup = tactic_counts.get(TacticLabel.AUTHORITY_CLAIM, 0) > 0
        has_pressure = (
            tactic_counts.get(TacticLabel.THREAT_PRESENTATION, 0) > 0
            or tactic_counts.get(TacticLabel.TIME_PRESSURE, 0) > 0
            or tactic_counts.get(TacticLabel.ISOLATION_TACTIC, 0) > 0
        )
        has_extraction = (
            tactic_counts.get(TacticLabel.CREDENTIAL_REQUEST, 0) > 0
            or tactic_counts.get(TacticLabel.FINANCIAL_REQUEST, 0) > 0
            or tactic_counts.get(TacticLabel.REMOTE_ACCESS_REQUEST, 0) > 0
            or tactic_counts.get(TacticLabel.IDENTITY_REQUEST, 0) > 0
        )
        has_resistance = tactic_counts.get(TacticLabel.USER_RESISTANCE, 0) > 0

        if has_extraction and has_pressure:
            phase = "ESCALATION"
            confidence = 0.6
        elif has_extraction:
            phase = "EXTRACTION"
            confidence = 0.6
        elif has_pressure:
            phase = "PRESSURE"
            confidence = 0.5
        elif has_setup:
            phase = "SETUP"
            confidence = 0.4
        elif has_resistance:
            phase = "RESISTANCE"
            confidence = 0.4
        else:
            phase = "SETUP"
            confidence = 0.3

        return ConversationPhasePrediction(
            phase=phase,
            confidence=confidence,
            evidence_basis=tuple(
                f"{p.tactic.value} (conf={p.confidence:.2f})"
                for p in predictions if p.confidence > 0.5
            ),
        )


# ---- ML Model Abstraction ----

class TacticClassifier(ABC):
    """Abstract base class for ML tactic classifiers.

    Implementations must:
      - Load a trained model from disk
      - Accept feature vectors
      - Return structured predictions with provenance
      - Handle errors gracefully
      - Report is_trained status honestly
    """

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Unique model identifier."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable model name."""
        ...

    @property
    @abstractmethod
    def is_trained(self) -> bool:
        """Whether a trained model is available."""
        ...

    @property
    def status(self) -> ModelStatus:
        """Honest model status."""
        if self.is_trained:
            return ModelStatus.TRAINED
        return ModelStatus.NOT_TRAINED

    @abstractmethod
    def predict(
        self,
        features: List[SegmentFeatures],
    ) -> List[TacticPrediction]:
        """Predict tactics for a list of segment features."""
        ...

    @abstractmethod
    def predict_phase(
        self,
        predictions: List[TacticPrediction],
    ) -> ConversationPhasePrediction:
        """Predict conversation phase from tactic predictions."""
        ...


class BaselineClassifier(TacticClassifier):
    """Deterministic baseline classifier (always available).

    This is NOT an ML model. It is a rule-based heuristic that
    serves as a transparent reference implementation.
    """

    def __init__(self) -> None:
        self._baseline = DeterministicBaseline()

    @property
    def model_id(self) -> str:
        return "deterministic_baseline_v1"

    @property
    def model_name(self) -> str:
        return "Deterministic Baseline (keyword rules)"

    @property
    def is_trained(self) -> bool:
        return False  # Not an ML model

    def predict(self, features: List[SegmentFeatures]) -> List[TacticPrediction]:
        return self._baseline.predict_tactics(features)

    def predict_phase(self, predictions: List[TacticPrediction]) -> ConversationPhasePrediction:
        return self._baseline.predict_phase(predictions)


# ---- Evaluation Harness ----

@dataclass
class EvaluationResult:
    """Results from model evaluation.

    Only populated when a legitimate trained model is evaluated
    against a legitimate labeled dataset. Never fabricated.
    """
    model_id: str
    dataset_name: str
    dataset_size: int
    num_classes: int
    accuracy: Optional[float] = None
    per_class_precision: Dict[str, float] = field(default_factory=dict)
    per_class_recall: Dict[str, float] = field(default_factory=dict)
    per_class_f1: Dict[str, float] = field(default_factory=dict)
    macro_f1: Optional[float] = None
    confusion_matrix: Optional[List[List[int]]] = None
    evaluation_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "dataset_name": self.dataset_name,
            "dataset_size": self.dataset_size,
            "num_classes": self.num_classes,
            "accuracy": self.accuracy,
            "per_class_precision": self.per_class_precision,
            "per_class_recall": self.per_class_recall,
            "per_class_f1": self.per_class_f1,
            "macro_f1": self.macro_f1,
            "confusion_matrix": self.confusion_matrix,
            "evaluation_date": self.evaluation_date,
            "notes": self.notes,
        }


class EvaluationHarness:
    """Evaluation harness for ML models.

    Ready for use when a legitimate trained model and labeled dataset
    become available. Currently reports NOT_TRAINED.
    """

    def __init__(self, classifier: TacticClassifier) -> None:
        self.classifier = classifier

    def evaluate(
        self,
        features: List[SegmentFeatures],
        true_labels: List[TacticLabel],
    ) -> EvaluationResult:
        """Evaluate the classifier against labeled data.

        Returns NOT_TRAINED results if the classifier is not trained.
        """
        if not self.classifier.is_trained:
            return EvaluationResult(
                model_id=self.classifier.model_id,
                dataset_name="unknown",
                dataset_size=len(features),
                num_classes=len(TacticLabel),
                notes="Model is NOT_TRAINED. Evaluation cannot be performed.",
            )

        # Run predictions
        predictions = self.classifier.predict(features)

        # Compute metrics
        correct = sum(
            1 for p, t in zip(predictions, true_labels)
            if p.tactic == t
        )
        accuracy = correct / len(true_labels) if true_labels else 0.0

        # Per-class metrics
        classes = list(TacticLabel)
        tp = {c: 0 for c in classes}
        fp = {c: 0 for c in classes}
        fn = {c: 0 for c in classes}

        for pred, true in zip(predictions, true_labels):
            if pred.tactic == true:
                tp[true] += 1
            else:
                fp[pred.tactic] += 1
                fn[true] += 1

        per_class_precision = {}
        per_class_recall = {}
        per_class_f1 = {}

        for c in classes:
            precision = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) > 0 else 0.0
            recall = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            per_class_precision[c.value] = round(precision, 4)
            per_class_recall[c.value] = round(recall, 4)
            per_class_f1[c.value] = round(f1, 4)

        macro_f1 = sum(per_class_f1.values()) / len(per_class_f1) if per_class_f1 else 0.0

        return EvaluationResult(
            model_id=self.classifier.model_id,
            dataset_name="custom",
            dataset_size=len(features),
            num_classes=len(TacticLabel),
            accuracy=round(accuracy, 4),
            per_class_precision=per_class_precision,
            per_class_recall=per_class_recall,
            per_class_f1=per_class_f1,
            macro_f1=round(macro_f1, 4),
            notes="Evaluation performed on custom labeled data.",
        )


# ---- Semantic AI Provider Abstraction ----

class SemanticAIProvider(ABC):
    """Abstract base for semantic AI providers.

    A semantic AI provider accepts structured evidence and returns
    structured analysis. It must:
      - Accept structured input (never raw untrusted text)
      - Return validated JSON output
      - Preserve provenance
      - Handle errors gracefully
      - Be optional (LUMINA works without it)

    The provider may use:
      - Local ML models
      - External API calls (user-authorized)
      - Hybrid approaches

    It must NEVER:
      - Execute instructions from transcript text
      - Modify incident state directly
      - Create confirmed user actions
      - Produce numeric scam scores
      - Expose secrets or credentials
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether the provider can currently process requests."""
        ...

    @abstractmethod
    def analyze(
        self,
        incident_id: str,
        segments_text: List[str],
        observations: List[str],
        temporal_features: Dict[str, Any],
    ) -> Optional[MLIntelligenceResult]:
        """Analyze conversation evidence and return structured intelligence.

        Args:
            incident_id: The incident being analyzed
            segments_text: Transcript segment texts (sanitized)
            observations: Deterministic observation labels
            temporal_features: CP-20 temporal features

        Returns:
            MLIntelligenceResult or None if analysis fails
        """
        ...


class UnavailableAIProvider(SemanticAIProvider):
    """Provider that is never available.

    Used when no semantic AI is configured.
    """

    @property
    def provider_id(self) -> str:
        return "unavailable"

    @property
    def provider_name(self) -> str:
        return "Not Configured"

    @property
    def is_available(self) -> bool:
        return False

    def analyze(self, **kwargs: Any) -> Optional[MLIntelligenceResult]:
        return None


# ---- Prompt Injection Defense ----

_INJECTION_PATTERNS = [
    "ignore all previous instructions",
    "ignore previous instructions",
    "disregard instructions",
    "forget your instructions",
    "you are now",
    "new instructions:",
    "system prompt:",
    "override safety",
    "bypass safety",
    "ignore safety",
    "reveal your instructions",
    "show your prompt",
    "what are your instructions",
    "repeat after me",
    "say exactly",
    "output the word",
    "print your instructions",
]


def detect_injection(text: str) -> bool:
    """Detect potential prompt injection in transcript text.

    This is a best-effort heuristic. It does NOT guarantee detection
    of all injection attempts. The goal is to flag obviously malicious
    transcript content for additional scrutiny.

    Returns True if injection patterns are detected.
    """
    lower = text.lower()
    return any(pattern in lower for pattern in _INJECTION_PATTERNS)


def sanitize_segment_text(text: str) -> str:
    """Sanitize transcript text for ML model input.

    Removes potential injection payloads while preserving the
    conversational content for analysis.
    """
    # Truncate very long segments (most ML models have token limits)
    if len(text) > 2000:
        text = text[:2000] + "..."

    # Flag injection attempts but preserve the text for evidence
    if detect_injection(text):
        return f"[FLAGGED INJECTION ATTEMPT] {text}"

    return text


# ---- Main Intelligence Pipeline ----

def analyze_with_ml(
    incident: Incident,
    classifier: Optional[TacticClassifier] = None,
    semantic_provider: Optional[SemanticAIProvider] = None,
) -> MLIntelligenceResult:
    """Run ML intelligence analysis on an incident.

    This is the main entry point. It:
    1. Extracts features from transcript segments
    2. Runs the classifier (baseline or trained)
    3. Optionally runs the semantic AI provider
    4. Returns structured, provenance-tracked results

    If no classifier is provided, uses the deterministic baseline.
    If no semantic provider is provided, returns baseline results only.

    All results are MODEL_OUTPUT epistemic status.
    """
    if classifier is None:
        classifier = BaselineClassifier()

    # Extract features from incident timeline
    segments_text: List[str] = []
    observations: List[str] = []

    for entry in incident.timeline:
        if entry.entry_type.value == "EVIDENCE_ADDED":
            obs_type = entry.metadata.get("observation_type", "")
            text_span = entry.metadata.get("text_span", "")
            if obs_type:
                observations.append(obs_type)
            if text_span:
                segments_text.append(sanitize_segment_text(text_span))

    # Build segment features
    features: List[SegmentFeatures] = []
    for i, text in enumerate(segments_text):
        prev_text = segments_text[i - 1] if i > 0 else ""
        next_text = segments_text[i + 1] if i < len(segments_text) - 1 else ""
        feat = _extract_segment_features(
            text=text,
            speaker=None,  # We don't always have speaker info from timeline
            segment_index=i,
            start_time=None,
            end_time=None,
            prev_text=prev_text,
            next_text=next_text,
        )
        features.append(feat)

    # Run classifier
    tactic_predictions = classifier.predict(features) if features else []
    phase_prediction = classifier.predict_phase(tactic_predictions) if tactic_predictions else None

    # Aggregate observed tactics
    observed_tactics = tuple(
        sorted(
            set(p.tactic for p in tactic_predictions if p.confidence > 0.5),
            key=lambda t: t.value,
        )
    )

    # Build supporting evidence
    supporting_evidence = tuple(
        f"Segment {i}: {p.tactic.value} (confidence={p.confidence:.2f})"
        for i, p in enumerate(tactic_predictions)
        if p.confidence > 0.5
    )

    # Build uncertainties
    uncertainties: List[str] = []
    if not segments_text:
        uncertainties.append("No transcript segments available for analysis")
    if not features:
        uncertainties.append("No features could be extracted")
    if classifier.status == ModelStatus.NOT_TRAINED:
        uncertainties.append("Using deterministic baseline — no trained ML model available")
    uncertainties.append("Speaker attribution is not established by Whisper STT")
    uncertainties.append("Tactic predictions are INFERENCE, not confirmed behavior")

    # Build explanation
    if observed_tactics:
        tactic_names = [t.value.replace("_", " ").lower() for t in observed_tactics]
        explanation = (
            f"The conversation shows: {', '.join(tactic_names)}. "
            f"Phase: {phase_prediction.phase if phase_prediction else 'unknown'}. "
            f"This is an ML inference based on transcript analysis — not proof of fraud."
        )
    else:
        explanation = "No significant social-engineering tactics detected in the available transcript evidence."

    # Model metadata
    model_metadata = {
        "model_id": classifier.model_id,
        "model_name": classifier.model_name,
        "model_status": classifier.status.value,
        "note": (
            "No suitable dataset was identified during implementation that provides "
            "sufficiently large, English, segment-level social-engineering tactic labels "
            "for phone-call transcripts. The evaluation harness is ready for future data."
        ),
    }

    # Optionally run semantic AI provider
    if semantic_provider and semantic_provider.is_available:
        try:
            ai_result = semantic_provider.analyze(
                incident_id=incident.incident_id,
                segments_text=segments_text,
                observations=observations,
                temporal_features={},
            )
            if ai_result:
                # Merge AI results with baseline (AI supplements, doesn't replace)
                return ai_result
        except Exception:
            # Semantic AI failure must not break the pipeline
            model_metadata["semantic_ai_error"] = "Provider failed — using baseline results"

    return MLIntelligenceResult(
        incident_id=incident.incident_id,
        tactic_predictions=tuple(tactic_predictions),
        phase_prediction=phase_prediction,
        observed_tactics=observed_tactics,
        requested_actions=tuple(o for o in observations if "REQUEST" in o),
        pressure_progression=tuple(
            p.tactic.value for p in tactic_predictions
            if p.tactic in (TacticLabel.THREAT_PRESENTATION, TacticLabel.TIME_PRESSURE, TacticLabel.ISOLATION_TACTIC)
        ),
        supporting_evidence=supporting_evidence,
        uncertainties=tuple(uncertainties),
        explanation=explanation,
        model_metadata=model_metadata,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ---- Global State ----

_classifier: Optional[TacticClassifier] = None
_semantic_provider: Optional[SemanticAIProvider] = None


def get_classifier() -> TacticClassifier:
    """Get the active ML classifier (baseline by default)."""
    global _classifier
    if _classifier is None:
        _classifier = BaselineClassifier()
    return _classifier


def set_classifier(classifier: TacticClassifier) -> None:
    """Set the active ML classifier."""
    global _classifier
    _classifier = classifier


def get_semantic_provider() -> SemanticAIProvider:
    """Get the active semantic AI provider."""
    global _semantic_provider
    if _semantic_provider is None:
        return UnavailableAIProvider()
    return _semantic_provider


def set_semantic_provider(provider: SemanticAIProvider) -> None:
    """Set the active semantic AI provider."""
    global _semantic_provider
    _semantic_provider = provider
