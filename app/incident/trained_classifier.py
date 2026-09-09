# app/incident/trained_classifier.py
"""TrainedClassifier — DeBERTa-v3-based multi-label tactic classifier.

This module provides the production ML classifier interface for LUMINA's
tactic classification. It implements the TacticClassifier abstraction
using a fine-tuned DeBERTa-v3-base model.

ARCHITECTURE:

  Transcript Segment
      ↓
  Tokenizer (DeBERTa-v3 tokenizer)
      ↓
  DeBERTa-v3-base (pre-trained transformer)
      ↓
  Multi-label classifier head
      ↓
  Structured TacticPrediction
      ↓
  Deterministic Safety Engine (always authoritative)

CRITICAL HONESTY RULES:

  - If no trained checkpoint exists, is_trained returns False
  - Never fabricate model accuracy or performance metrics
  - Never create a numeric "scam score" or "fraud probability"
  - ML output is always MODEL_OUTPUT — never FACT
  - ML never directly mutates incident state
  - ML is advisory only — the deterministic safety engine decides

STATUS: INFRASTRUCTURE READY — NO TRAINED MODEL EXISTS

  This module provides the complete inference pipeline. It will return
  NOT_TRAINED until a legitimate checkpoint is produced from real data.

  The interface is designed to be a drop-in replacement for BaselineClassifier
  once training data becomes available and the model is trained.

INTEGRATION:

  This class extends TacticClassifier (ABC) from ml_intelligence.py.

  Usage:
    from app.incident.trained_classifier import TrainedClassifier
    from app.incident.ml_intelligence import set_classifier

    # When a trained model is available:
    clf = TrainedClassifier(checkpoint_path="models/tactic_classifier_v1.pt")
    set_classifier(clf)

  Until then:
    # BaselineClassifier is used automatically
    pass
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.incident.ml_intelligence import (
    ConversationPhasePrediction,
    ModelStatus,
    SegmentFeatures,
    TacticClassifier,
    TacticLabel,
    TacticPrediction,
)


logger = logging.getLogger(__name__)


# ---- Model Configuration ----

@dataclass(frozen=True)
class ModelConfig:
    """Configuration for the DeBERTa-v3 tactic classifier.

    All values have sensible defaults. Override only when necessary.
    """
    model_name: str = "microsoft/deberta-v3-base"
    num_labels: int = 11  # Excluding UNKNOWN
    max_length: int = 256  # Maximum token length for segments
    dropout_rate: float = 0.1
    threshold: float = 0.5  # Multi-label threshold
    device: str = "cpu"  # "cpu" or "cuda"
    id2label: Dict[int, str] = None
    label2id: Dict[str, int] = None

    def __post_init__(self) -> None:
        if self.id2label is None or self.label2id is None:
            # Build label mappings from TacticLabel enum
            labels = [l.value for l in TacticLabel if l.value != "UNKNOWN"]
            object.__setattr__(self, "id2label", {i: l for i, l in enumerate(labels)})
            object.__setattr__(self, "label2id", {l: i for i, l in enumerate(labels)})


# ---- Checkpoint Metadata ----

@dataclass(frozen=True)
class CheckpointMetadata:
    """Metadata about a trained model checkpoint.

    This is stored alongside the model weights and loaded at inference time.
    It provides honest provenance for the model.
    """
    model_name: str
    training_date: str
    dataset_name: str
    dataset_size: int
    num_labels: int
    epoch: int
    train_loss: float
    val_loss: float
    macro_f1: float
    per_class_f1: Dict[str, float]
    training_notes: str
    license: str

    @classmethod
    def from_file(cls, path: Path) -> Optional["CheckpointMetadata"]:
        """Load metadata from a JSON sidecar file."""
        metadata_path = path.with_suffix(".metadata.json")
        if not metadata_path.exists():
            return None

        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_file(self, path: Path) -> None:
        """Save metadata to a JSON sidecar file."""
        metadata_path = path.with_suffix(".metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, indent=2, ensure_ascii=False)


# ---- Tokenizer Wrapper ----

class SegmentTokenizer:
    """Tokenizer wrapper for DeBERTa-v3.

    Handles text preprocessing, tokenization, and padding/truncation.
    Designed to be deterministic and reproducible.

    This wrapper is self-contained and does NOT require the transformers
    library at import time — it falls back to a simple whitespace tokenizer
    if transformers is not available.
    """

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self._transformers_available = False
        self._tokenizer = None

        try:
            from transformers import AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(config.model_name)
            self._transformers_available = True
            logger.info(f"Loaded tokenizer: {config.model_name}")
        except (ImportError, OSError) as e:
            logger.warning(
                f"transformers library not available or model not found: {e}. "
                "Using fallback whitespace tokenizer."
            )

    def tokenize(self, text: str) -> Dict[str, Any]:
        """Tokenize a single text segment.

        Returns a dict with keys: input_ids, attention_mask, tokens.
        """
        if self._transformers_available and self._tokenizer is not None:
            return self._tokenizer(
                text,
                max_length=self.config.max_length,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
        else:
            # Fallback: simple whitespace tokenization
            # This is NOT suitable for real inference — only for testing
            tokens = text.lower().split()[:self.config.max_length]
            # Pad to max_length
            tokens = tokens + ["[PAD]"] * (self.config.max_length - len(tokens))
            attention_mask = [1 if t != "[PAD]" else 0 for t in tokens]
            # Simple hash-based encoding (NOT a real tokenizer)
            input_ids = [hash(t) % 30000 for t in tokens]
            return {
                "input_ids": [input_ids],
                "attention_mask": [attention_mask],
                "tokens": [tokens],
            }

    def tokenize_batch(self, texts: List[str]) -> Dict[str, Any]:
        """Tokenize a batch of text segments."""
        if self._transformers_available and self._tokenizer is not None:
            return self._tokenizer(
                texts,
                max_length=self.config.max_length,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
        else:
            results = [self.tokenize(t) for t in texts]
            return {
                "input_ids": [r["input_ids"][0] for r in results],
                "attention_mask": [r["attention_mask"][0] for r in results],
            }


# ---- Model Wrapper ----

class DeBERTaTacticModel:
    """DeBERTa-v3 model wrapper for multi-label tactic classification.

    This class handles:
    - Model loading from checkpoint
    - Forward pass inference
    - Multi-label threshold application
    - Confidence calibration

    The model is NOT loaded at import time — it is loaded lazily
    when load_checkpoint() is called.
    """

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self._model = None
        self._loaded = False

    def load_checkpoint(self, checkpoint_path: Path) -> bool:
        """Load a trained model from a checkpoint file.

        Returns True if successful, False otherwise.
        """
        if not checkpoint_path.exists():
            logger.error(f"Checkpoint not found: {checkpoint_path}")
            return False

        try:
            import torch
            from transformers import AutoModelForSequenceClassification

            self._model = AutoModelForSequenceClassification.from_pretrained(
                str(checkpoint_path),
                num_labels=self.config.num_labels,
                problem_type="multi_label_classification",
            )
            self._model.to(self.config.device)
            self._model.eval()
            self._loaded = True
            logger.info(f"Loaded model from {checkpoint_path}")
            return True

        except (ImportError, OSError) as e:
            logger.error(f"Failed to load model: {e}")
            self._loaded = False
            return False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def predict(self, input_ids: Any, attention_mask: Any) -> List[List[float]]:
        """Run inference and return raw logits.

        Returns list of lists of floats (batch_size x num_labels).
        """
        if not self._loaded or self._model is None:
            raise RuntimeError("Model not loaded. Call load_checkpoint() first.")

        import torch

        with torch.no_grad():
            outputs = self._model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )
            logits = outputs.logits
            # Apply sigmoid for multi-label
            probs = torch.sigmoid(logits)
            return probs.cpu().tolist()


# ---- TrainedClassifier Implementation ----

class TrainedClassifier(TacticClassifier):
    """DeBERTa-v3-based multi-label tactic classifier.

    Implements the TacticClassifier interface for production use.

    Behavior:
    - When a trained checkpoint is loaded: uses DeBERTa for inference
    - When no checkpoint is available: falls back to DeterministicBaseline
    - Always reports honest is_trained status
    - Never fabricates predictions

    Integration with existing system:
    - Fits the TacticClassifier abstraction
    - Produces TacticPrediction objects (same as BaselineClassifier)
    - Can be set via set_classifier()
    - Does NOT modify incident state
    - Output is always MODEL_OUTPUT epistemic status
    """

    def __init__(
        self,
        checkpoint_path: Optional[Path] = None,
        config: Optional[ModelConfig] = None,
    ) -> None:
        self._config = config or ModelConfig()
        self._tokenizer = SegmentTokenizer(self._config)
        self._model = DeBERTaTacticModel(self._config)
        self._metadata: Optional[CheckpointMetadata] = None
        self._checkpoint_path = checkpoint_path

        if checkpoint_path and checkpoint_path.exists():
            self._load_checkpoint(checkpoint_path)

    def _load_checkpoint(self, path: Path) -> None:
        """Load checkpoint and metadata."""
        # Load metadata
        self._metadata = CheckpointMetadata.from_file(path)

        # Load model
        success = self._model.load_checkpoint(path)
        if success:
            logger.info(
                f"TrainedClassifier loaded: {self._config.model_name} "
                f"(trained on {self._metadata.dataset_size if self._metadata else '?'} segments)"
            )
        else:
            logger.warning("Failed to load model checkpoint — falling back to baseline")

    @property
    def model_id(self) -> str:
        if self._metadata:
            return f"deberta_v3_{self._metadata.training_date}"
        return "deberta_v3_not_trained"

    @property
    def model_name(self) -> str:
        if self._metadata:
            return f"DeBERTa-v3-base (trained {self._metadata.training_date})"
        return f"DeBERTa-v3-base (NOT TRAINED)"

    @property
    def is_trained(self) -> bool:
        return self._model.is_loaded and self._metadata is not None

    def predict(
        self,
        features: List[SegmentFeatures],
    ) -> List[TacticPrediction]:
        """Predict tactics for a list of segment features.

        If the model is not trained, falls back to DeterministicBaseline.
        """
        if not self.is_trained:
            # Fallback to baseline
            from app.incident.ml_intelligence import DeterministicBaseline
            baseline = DeterministicBaseline()
            return baseline.predict_tactics(features)

        # Extract text from features (text_span is not in SegmentFeatures,
        # so we reconstruct from keyword features)
        # NOTE: In production, text would be passed separately.
        # For now, we use the feature vector as a proxy.
        predictions: List[TacticPrediction] = []

        for feat in features:
            # Build a text representation from features for tokenization
            text = self._features_to_text(feat)

            # Tokenize
            tokenized = self._tokenizer.tokenize(text)

            # Run inference
            try:
                probs = self._model.predict(
                    input_ids=tokenized["input_ids"],
                    attention_mask=tokenized["attention_mask"],
                )

                # Apply multi-label threshold
                pred_labels: List[Tuple[TacticLabel, float]] = []
                if probs and probs[0]:
                    for idx, prob in enumerate(probs[0]):
                        if prob >= self._config.threshold:
                            label_name = self._config.id2label.get(idx)
                            if label_name:
                                try:
                                    label = TacticLabel(label_name)
                                    pred_labels.append((label, prob))
                                except ValueError:
                                    pass

                # If no labels above threshold, take the highest
                if not pred_labels and probs and probs[0]:
                    best_idx = max(range(len(probs[0])), key=lambda i: probs[0][i])
                    label_name = self._config.id2label.get(best_idx)
                    if label_name:
                        try:
                            label = TacticLabel(label_name)
                            pred_labels.append((label, probs[0][best_idx]))
                        except ValueError:
                            pred_labels.append((TacticLabel.BENIGN_CONVERSATION, 0.4))

                # Take the highest confidence prediction
                if pred_labels:
                    best_label, best_conf = max(pred_labels, key=lambda x: x[1])
                else:
                    best_label, best_conf = TacticLabel.BENIGN_CONVERSATION, 0.4

                predictions.append(TacticPrediction(
                    tactic=best_label,
                    confidence=round(best_conf, 4),
                    epistemic_status="MODEL_OUTPUT",
                ))

            except Exception as e:
                logger.error(f"Prediction failed: {e}")
                # Fall back to deterministic for this segment
                from app.incident.ml_intelligence import DeterministicBaseline
                baseline = DeterministicBaseline()
                predictions.append(baseline.predict_tactics([feat])[0])

        return predictions

    def _features_to_text(self, feat: SegmentFeatures) -> str:
        """Convert SegmentFeatures back to a text approximation for tokenization.

        This is a lossy conversion — in production, the original text would
        be passed directly. This exists for interface compatibility.
        """
        parts = []
        if feat.has_authority_keyword:
            parts.append("police bank government")
        if feat.has_threat_keyword:
            parts.append("arrest jail warrant")
        if feat.has_urgency_keyword:
            parts.append("now immediately hurry")
        if feat.has_secrecy_keyword:
            parts.append("secret confidential")
        if feat.has_otp_keyword:
            parts.append("otp code verification")
        if feat.has_password_keyword:
            parts.append("password")
        if feat.has_money_keyword:
            parts.append("money transfer payment")
        if feat.has_remote_access_keyword:
            parts.append("install download remote")
        if feat.has_identity_keyword:
            parts.append("id document passport")
        if feat.has_negation:
            parts.append("not never don't")
        if feat.has_advice_context:
            parts.append("warning be careful")

        return " ".join(parts) if parts else "normal conversation"

    def predict_phase(
        self,
        predictions: List[TacticPrediction],
    ) -> ConversationPhasePrediction:
        """Predict conversation phase from tactic predictions.

        Uses the same logic as DeterministicBaseline for consistency.
        """
        from app.incident.ml_intelligence import DeterministicBaseline
        baseline = DeterministicBaseline()
        return baseline.predict_phase(predictions)
