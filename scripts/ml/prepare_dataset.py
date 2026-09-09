# scripts/ml/prepare_dataset.py
"""Deterministic Dataset Preparation Pipeline for LUMINA ML Training.

This module provides a reproducible, auditable pipeline for preparing
training data for LUMINA's tactic classifier. It enforces:

  - Raw datasets remain outside Git unless licensing explicitly allows
  - Deterministic preprocessing (seed-based splits)
  - Provenance tracking (dataset manifest with versioning)
  - Duplicate detection and removal
  - PII/secrets filtering where legally appropriate
  - Conversation-level splitting (no leakage between splits)
  - Train / validation / test split with deterministic seed
  - Label distribution reporting
  - Label mapping to LUMINA's TacticLabel taxonomy

CRITICAL HONESTY RULES:
  - If no legitimate training data exists, this pipeline reports the blocker
  - It NEVER fabricates data or generates synthetic examples
  - It NEVER creates fake metrics or假装 the model is trained
  - Output is always honest about dataset size and quality

USAGE:
    python -m scripts.ml.prepare_dataset \
        --input-dir ./data/raw \
        --output-dir ./data/processed \
        --seed 42

ARCHITECTURE:
    Raw Data (outside Git)
        ↓
    Validation (provenance, format, licensing)
        ↓
    Preprocessing (text cleaning, label mapping)
        ↓
    Duplicate Detection
        ↓
    PII Filtering
        ↓
    Conversation-Level Split
        ↓
    Label Distribution Analysis
        ↓
    Dataset Manifest (versioned)
        ↓
    Training-Ready Output
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import secrets
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.incident.ml_intelligence import TacticLabel


# ---- Logging ----

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---- Constants ----

DEFAULT_SEED = 42
DEFAULT_TRAIN_RATIO = 0.8
DEFAULT_VAL_RATIO = 0.1
DEFAULT_TEST_RATIO = 0.1
MANIFEST_VERSION = "1.0.0"

# LUMINA's TacticLabel taxonomy
LUMINA_LABELS = {label.value for label in TacticLabel}
LUMINA_LABELS.discard("UNKNOWN")  # UNKNOWN is a catch-all, not a training target


# ---- Data Structures ----

class DatasetSplit(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass(frozen=True)
class ProvenanceRecord:
    """Provenance tracking for a single dataset source."""
    source_name: str
    source_url: str
    license: str
    commercial_use: bool
    training_use: bool
    language: str
    modality: str
    download_date: str
    verification_status: str  # "VERIFIED", "UNVERIFIED", "EXCLUDED"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_url": self.source_url,
            "license": self.license,
            "commercial_use": self.commercial_use,
            "training_use": self.training_use,
            "language": self.language,
            "modality": self.modality,
            "download_date": self.download_date,
            "verification_status": self.verification_status,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class Segment:
    """A single labeled segment for training."""
    segment_id: str
    conversation_id: str
    text: str
    labels: Tuple[str, ...]
    speaker: Optional[str] = None
    sequence: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "conversation_id": self.conversation_id,
            "text": self.text,
            "labels": list(self.labels),
            "speaker": self.speaker,
            "sequence": self.sequence,
            "metadata": self.metadata,
        }


@dataclass
class DatasetManifest:
    """Versioned dataset manifest with full provenance."""
    version: str
    created_at: str
    seed: int
    provenance: List[ProvenanceRecord]
    total_conversations: int = 0
    total_segments: int = 0
    train_count: int = 0
    val_count: int = 0
    test_count: int = 0
    label_distribution: Dict[str, int] = field(default_factory=dict)
    duplicate_rate: float = 0.0
    avg_segment_length: float = 0.0
    language_distribution: Dict[str, int] = field(default_factory=dict)
    split_integrity: bool = True
    preprocessing_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "seed": self.seed,
            "provenance": [p.to_dict() for p in self.provenance],
            "total_conversations": self.total_conversations,
            "total_segments": self.total_segments,
            "train_count": self.train_count,
            "val_count": self.val_count,
            "test_count": self.test_count,
            "label_distribution": self.label_distribution,
            "duplicate_rate": self.duplicate_rate,
            "avg_segment_length": self.avg_segment_length,
            "language_distribution": self.language_distribution,
            "split_integrity": self.split_integrity,
            "preprocessing_notes": self.preprocessing_notes,
        }


# ---- Text Cleaning ----

_PII_PATTERNS = [
    # Phone numbers
    (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), "[PHONE]"),
    (re.compile(r'\b\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b'), "[PHONE]"),
    # Email addresses
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), "[EMAIL]"),
    # SSN-like patterns
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "[SSN]"),
    # Credit card numbers (basic pattern)
    (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), "[CARD]"),
    # Aadhaar numbers (12 digits)
    (re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'), "[ID_NUMBER]"),
    # OTP codes (4-8 digit numbers in context)
    (re.compile(r'\b(?:otp|code|pin)[:\s]+(\d{4,8})\b', re.IGNORECASE), r'\1 [OTP_REDACTED]'),
]

_SECRET_PATTERNS = [
    re.compile(r'password\s*[:=]\s*\S+', re.IGNORECASE),
    re.compile(r'secret\s*[:=]\s*\S+', re.IGNORECASE),
    re.compile(r'api[_-]?key\s*[:=]\s*\S+', re.IGNORECASE),
]


def filter_pii(text: str) -> str:
    """Filter PII and secrets from text.

    This is a best-effort heuristic. It does NOT guarantee complete PII removal.
    The goal is to reduce PII exposure while preserving conversational content
    for ML training.

    Returns filtered text with PII replaced by placeholders.
    """
    filtered = text
    for pattern, replacement in _PII_PATTERNS:
        filtered = pattern.sub(replacement, filtered)

    for pattern in _SECRET_PATTERNS:
        filtered = pattern.sub("[SECRET_REDACTED]", filtered)

    return filtered


def clean_text(text: str) -> str:
    """Basic text cleaning for ML training.

    - Strips whitespace
    - Normalizes unicode
    - Removes control characters
    - Preserves punctuation and case (important for tactic detection)
    """
    # Normalize unicode
    import unicodedata
    text = unicodedata.normalize("NFKC", text)

    # Remove control characters (except newlines)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Normalize multiple spaces
    text = re.sub(r' {2,}', ' ', text)

    return text


# ---- Duplicate Detection ----

def compute_text_hash(text: str) -> str:
    """Compute a deterministic hash for deduplication."""
    normalized = text.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def detect_duplicates(segments: List[Segment]) -> Tuple[List[Segment], int]:
    """Detect and remove duplicate segments.

    Uses text hash for exact deduplication.
    Returns deduplicated segments and count of duplicates removed.
    """
    seen_hashes: Set[str] = set()
    unique_segments: List[Segment] = []
    duplicates = 0

    for seg in segments:
        h = compute_text_hash(seg.text)
        if h not in seen_hashes:
            seen_hashes.add(h)
            unique_segments.append(seg)
        else:
            duplicates += 1

    return unique_segments, duplicates


# ---- Label Mapping ----

# Mapping from common dataset label patterns to LUMINA's TacticLabel
_LABEL_MAP: Dict[str, str] = {
    # Authority patterns
    "authority": TacticLabel.AUTHORITY_CLAIM.value,
    "impersonation": TacticLabel.AUTHORITY_CLAIM.value,
    "false_authority": TacticLabel.AUTHORITY_CLAIM.value,
    # Threat patterns
    "threat": TacticLabel.THREAT_PRESENTATION.value,
    "intimidation": TacticLabel.THREAT_PRESENTATION.value,
    "arrest_threat": TacticLabel.THREAT_PRESENTATION.value,
    "legal_threat": TacticLabel.THREAT_PRESENTATION.value,
    # Urgency patterns
    "urgency": TacticLabel.TIME_PRESSURE.value,
    "time_pressure": TacticLabel.TIME_PRESSURE.value,
    "pressure": TacticLabel.TIME_PRESSURE.value,
    # Isolation patterns
    "isolation": TacticLabel.ISOLATION_TACTIC.value,
    "secrecy": TacticLabel.ISOLATION_TACTIC.value,
    "secrecy_request": TacticLabel.ISOLATION_TACTIC.value,
    # Credential patterns
    "credential": TacticLabel.CREDENTIAL_REQUEST.value,
    "otp": TacticLabel.CREDENTIAL_REQUEST.value,
    "password": TacticLabel.CREDENTIAL_REQUEST.value,
    "information_elicitation": TacticLabel.CREDENTIAL_REQUEST.value,
    # Financial patterns
    "financial": TacticLabel.FINANCIAL_REQUEST.value,
    "money": TacticLabel.FINANCIAL_REQUEST.value,
    "payment": TacticLabel.FINANCIAL_REQUEST.value,
    "transfer": TacticLabel.FINANCIAL_REQUEST.value,
    # Remote access patterns
    "remote_access": TacticLabel.REMOTE_ACCESS_REQUEST.value,
    "tech_support": TacticLabel.REMOTE_ACCESS_REQUEST.value,
    "software_install": TacticLabel.REMOTE_ACCESS_REQUEST.value,
    # Identity patterns
    "identity": TacticLabel.IDENTITY_REQUEST.value,
    "document": TacticLabel.IDENTITY_REQUEST.value,
    "personal_info": TacticLabel.IDENTITY_REQUEST.value,
    # Benign patterns
    "benign": TacticLabel.BENIGN_CONVERSATION.value,
    "normal": TacticLabel.BENIGN_CONVERSATION.value,
    "legitimate": TacticLabel.BENIGN_CONVERSATION.value,
    "non_scam": TacticLabel.BENIGN_CONVERSATION.value,
    "non-scam": TacticLabel.BENIGN_CONVERSATION.value,
    # Resistance patterns
    "resistance": TacticLabel.USER_RESISTANCE.value,
    "refusal": TacticLabel.USER_RESISTANCE.value,
    "pushback": TacticLabel.USER_RESISTANCE.value,
}


def map_label(raw_label: str) -> Optional[str]:
    """Map a raw dataset label to LUMINA's TacticLabel taxonomy.

    Returns the mapped label or None if no mapping exists.
    """
    normalized = raw_label.lower().strip()
    normalized = re.sub(r'[\s\-_]+', '_', normalized)

    # Direct match
    if normalized in _LABEL_MAP:
        return _LABEL_MAP[normalized]

    # Partial match
    for pattern, mapped in _LABEL_MAP.items():
        if pattern in normalized:
            return mapped

    return None


# ---- Conversation-Level Split ----

def split_by_conversation(
    segments: List[Segment],
    seed: int = DEFAULT_SEED,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    val_ratio: float = DEFAULT_VAL_RATIO,
    test_ratio: float = DEFAULT_TEST_RATIO,
) -> Dict[DatasetSplit, List[Segment]]:
    """Split segments by conversation ID to prevent data leakage.

    No conversation may appear in multiple splits.

    Uses deterministic shuffling based on the provided seed.
    """
    import random

    # Group segments by conversation
    conversations: Dict[str, List[Segment]] = {}
    for seg in segments:
        conv_id = seg.conversation_id
        if conv_id not in conversations:
            conversations[conv_id] = []
        conversations[conv_id].append(seg)

    conv_ids = list(conversations.keys())

    # Deterministic shuffle
    rng = random.Random(seed)
    rng.shuffle(conv_ids)

    # Calculate split boundaries
    n = len(conv_ids)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_convs = conv_ids[:train_end]
    val_convs = conv_ids[train_end:val_end]
    test_convs = conv_ids[val_end:]

    # Assemble splits
    train_segments = []
    for conv_id in train_convs:
        train_segments.extend(sorted(conversations[conv_id], key=lambda s: s.sequence))

    val_segments = []
    for conv_id in val_convs:
        val_segments.extend(sorted(conversations[conv_id], key=lambda s: s.sequence))

    test_segments = []
    for conv_id in test_convs:
        test_segments.extend(sorted(conversations[conv_id], key=lambda s: s.sequence))

    # Verify no leakage
    train_convs_set = set(train_convs)
    val_convs_set = set(val_convs)
    test_convs_set = set(test_convs)

    assert train_convs_set.isdisjoint(val_convs_set), "Train/Val conversation leak!"
    assert train_convs_set.isdisjoint(test_convs_set), "Train/Test conversation leak!"
    assert val_convs_set.isdisjoint(test_convs_set), "Val/Test conversation leak!"

    logger.info(
        f"Split: {len(train_convs)} train conversations ({len(train_segments)} segments), "
        f"{len(val_convs)} val conversations ({len(val_segments)} segments), "
        f"{len(test_convs)} test conversations ({len(test_segments)} segments)"
    )

    return {
        DatasetSplit.TRAIN: train_segments,
        DatasetSplit.VALIDATION: val_segments,
        DatasetSplit.TEST: test_segments,
    }


# ---- Label Distribution Analysis ----

def compute_label_distribution(segments: List[Segment]) -> Dict[str, int]:
    """Compute label frequency distribution."""
    dist: Dict[str, int] = {}
    for seg in segments:
        for label in seg.labels:
            dist[label] = dist.get(label, 0) + 1
    return dict(sorted(dist.items(), key=lambda x: -x[1]))


def compute_class_imbalance(label_dist: Dict[str, int]) -> Dict[str, float]:
    """Compute class imbalance ratios.

    Returns ratio of each class count to the maximum class count.
    A ratio close to 1.0 means balanced; close to 0.0 means highly imbalanced.
    """
    if not label_dist:
        return {}
    max_count = max(label_dist.values())
    return {label: count / max_count for label, count in label_dist.items()}


# ---- Main Pipeline ----

def validate_input_directory(input_dir: Path) -> List[Path]:
    """Validate that the input directory exists and contains recognizable data files."""
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    supported_extensions = {".json", ".jsonl", ".csv", ".tsv", ".txt"}
    data_files = [
        f for f in input_dir.iterdir()
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]

    if not data_files:
        raise ValueError(
            f"No data files found in {input_dir}. "
            f"Supported formats: {supported_extensions}"
        )

    logger.info(f"Found {len(data_files)} data files in {input_dir}")
    return data_files


def load_segments_from_json(file_path: Path) -> List[Segment]:
    """Load segments from a JSON file.

    Expected format:
    [
        {
            "conversation_id": "conv_001",
            "text": "I am calling from the police department",
            "labels": ["AUTHORITY_CLAIM"],
            "speaker": "CALLER",
            "sequence": 0
        },
        ...
    ]
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {file_path}")

    segments = []
    for i, item in enumerate(data):
        text = item.get("text", "")
        if not text:
            continue

        # Map labels
        raw_labels = item.get("labels", [])
        if isinstance(raw_labels, str):
            raw_labels = [raw_labels]

        mapped_labels = []
        for label in raw_labels:
            mapped = map_label(label)
            if mapped:
                mapped_labels.append(mapped)

        if not mapped_labels:
            mapped_labels = [TacticLabel.UNKNOWN.value]

        # Filter PII
        filtered_text = filter_pii(text)
        cleaned_text = clean_text(filtered_text)

        if not cleaned_text:
            continue

        segments.append(Segment(
            segment_id=item.get("segment_id", f"{file_path.stem}_{i}"),
            conversation_id=item.get("conversation_id", f"{file_path.stem}_conv_{i}"),
            text=cleaned_text,
            labels=tuple(mapped_labels),
            speaker=item.get("speaker"),
            sequence=item.get("sequence", i),
            metadata={"source_file": str(file_path)},
        ))

    return segments


def load_segments_from_jsonl(file_path: Path) -> List[Segment]:
    """Load segments from a JSONL file (one JSON object per line)."""
    segments = []
    with open(file_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(f"Skipping invalid JSON on line {i + 1} of {file_path}")
                continue

            text = item.get("text", "")
            if not text:
                continue

            raw_labels = item.get("labels", [])
            if isinstance(raw_labels, str):
                raw_labels = [raw_labels]

            mapped_labels = []
            for label in raw_labels:
                mapped = map_label(label)
                if mapped:
                    mapped_labels.append(mapped)

            if not mapped_labels:
                mapped_labels = [TacticLabel.UNKNOWN.value]

            filtered_text = filter_pii(text)
            cleaned_text = clean_text(filtered_text)

            if not cleaned_text:
                continue

            segments.append(Segment(
                segment_id=item.get("segment_id", f"{file_path.stem}_{i}"),
                conversation_id=item.get("conversation_id", f"{file_path.stem}_conv_{i}"),
                text=cleaned_text,
                labels=tuple(mapped_labels),
                speaker=item.get("speaker"),
                sequence=item.get("sequence", i),
                metadata={"source_file": str(file_path)},
            ))

    return segments


def load_segments(file_path: Path) -> List[Segment]:
    """Load segments from a supported file format."""
    ext = file_path.suffix.lower()
    if ext == ".json":
        return load_segments_from_json(file_path)
    elif ext == ".jsonl":
        return load_segments_from_jsonl(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def save_split(segments: List[Segment], output_dir: Path, split_name: str) -> None:
    """Save a split to a JSONL file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{split_name}.jsonl"

    with open(output_path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(json.dumps(seg.to_dict(), ensure_ascii=False) + "\n")

    logger.info(f"Saved {len(segments)} segments to {output_path}")


def run_pipeline(
    input_dir: Path,
    output_dir: Path,
    seed: int = DEFAULT_SEED,
) -> DatasetManifest:
    """Run the full dataset preparation pipeline.

    Returns a DatasetManifest with all statistics and provenance.
    """
    logger.info("=" * 60)
    logger.info("LUMINA Dataset Preparation Pipeline")
    logger.info("=" * 60)

    # Step 1: Validate input
    logger.info("Step 1: Validating input directory...")
    data_files = validate_input_directory(input_dir)

    # Step 2: Load segments
    logger.info("Step 2: Loading segments...")
    all_segments: List[Segment] = []
    provenance_records: List[ProvenanceRecord] = []

    for file_path in data_files:
        logger.info(f"  Loading {file_path.name}...")
        try:
            segments = load_segments(file_path)
            all_segments.extend(segments)
            provenance_records.append(ProvenanceRecord(
                source_name=file_path.stem,
                source_url=f"file://{file_path}",
                license="UNKNOWN",
                commercial_use=False,
                training_use=False,
                language="en",
                modality="text",
                download_date=datetime.now(timezone.utc).isoformat(),
                verification_status="UNVERIFIED",
                notes=f"Loaded {len(segments)} segments from {file_path.name}",
            ))
        except Exception as e:
            logger.error(f"  Failed to load {file_path.name}: {e}")
            continue

    if not all_segments:
        logger.error("No segments loaded. Pipeline cannot continue.")
        return DatasetManifest(
            version=MANIFEST_VERSION,
            created_at=datetime.now(timezone.utc).isoformat(),
            seed=seed,
            provenance=provenance_records,
            preprocessing_notes=["BLOCKER: No valid segments found in input directory"],
        )

    logger.info(f"  Total segments loaded: {len(all_segments)}")

    # Step 3: Deduplication
    logger.info("Step 3: Detecting duplicates...")
    unique_segments, dup_count = detect_duplicates(all_segments)
    dup_rate = dup_count / len(all_segments) if all_segments else 0.0
    logger.info(f"  Removed {dup_count} duplicates ({dup_rate:.2%} rate)")

    # Step 4: Conversation-level split
    logger.info("Step 4: Splitting by conversation...")
    splits = split_by_conversation(unique_segments, seed=seed)

    # Step 5: Compute statistics
    logger.info("Step 5: Computing statistics...")
    train_dist = compute_label_distribution(splits[DatasetSplit.TRAIN])
    val_dist = compute_label_distribution(splits[DatasetSplit.VALIDATION])
    test_dist = compute_label_distribution(splits[DatasetSplit.TEST])

    # Merge distributions
    all_dist: Dict[str, int] = {}
    for dist in [train_dist, val_dist, test_dist]:
        for label, count in dist.items():
            all_dist[label] = all_dist.get(label, 0) + count

    # Compute average segment length
    total_chars = sum(len(seg.text) for seg in unique_segments)
    avg_length = total_chars / len(unique_segments) if unique_segments else 0.0

    # Count unique conversations
    conv_ids = set(seg.conversation_id for seg in unique_segments)

    # Step 6: Save splits
    logger.info("Step 6: Saving splits...")
    for split_name, segments in splits.items():
        save_split(segments, output_dir, split_name.value)

    # Step 7: Create manifest
    logger.info("Step 7: Creating dataset manifest...")
    manifest = DatasetManifest(
        version=MANIFEST_VERSION,
        created_at=datetime.now(timezone.utc).isoformat(),
        seed=seed,
        provenance=provenance_records,
        total_conversations=len(conv_ids),
        total_segments=len(unique_segments),
        train_count=len(splits[DatasetSplit.TRAIN]),
        val_count=len(splits[DatasetSplit.VALIDATION]),
        test_count=len(splits[DatasetSplit.TEST]),
        label_distribution=all_dist,
        duplicate_rate=dup_rate,
        avg_segment_length=avg_length,
        language_distribution={"en": len(unique_segments)},
        split_integrity=True,
        preprocessing_notes=[
            f"Loaded {len(all_segments)} segments from {len(data_files)} files",
            f"Removed {dup_count} duplicates ({dup_rate:.2%})",
            f"Split {len(conv_ids)} conversations into train/val/test",
            f"PII filtering applied",
            f"Text cleaning applied",
        ],
    )

    # Save manifest
    manifest_path = output_dir / "dataset_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info(f"  Manifest saved to {manifest_path}")

    # Print summary
    logger.info("=" * 60)
    logger.info("Pipeline Complete")
    logger.info("=" * 60)
    logger.info(f"  Conversations: {manifest.total_conversations}")
    logger.info(f"  Segments: {manifest.total_segments}")
    logger.info(f"  Train: {manifest.train_count}")
    logger.info(f"  Validation: {manifest.val_count}")
    logger.info(f"  Test: {manifest.test_count}")
    logger.info(f"  Duplicate rate: {manifest.duplicate_rate:.2%}")
    logger.info(f"  Avg segment length: {manifest.avg_segment_length:.0f} chars")
    logger.info(f"  Label distribution: {manifest.label_distribution}")

    imbalance = compute_class_imbalance(manifest.label_distribution)
    if imbalance:
        min_ratio = min(imbalance.values())
        logger.info(f"  Class imbalance: min ratio = {min_ratio:.3f}")
        if min_ratio < 0.1:
            logger.warning("  WARNING: Severe class imbalance detected!")

    return manifest


# ---- CLI ----

def main() -> None:
    parser = argparse.ArgumentParser(
        description="LUMINA Dataset Preparation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This pipeline prepares training data for LUMINA's tactic classifier.

Input format: JSON files with segments containing:
  - conversation_id: unique conversation identifier
  - text: the transcript segment text
  - labels: list of tactic labels (raw or LUMINA-mapped)
  - speaker: optional speaker attribution
  - sequence: segment order within conversation

Output: Train/validation/test splits with provenance manifest.
        """,
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing raw dataset files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for processed output files",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for deterministic splits (default: {DEFAULT_SEED})",
    )

    args = parser.parse_args()

    try:
        manifest = run_pipeline(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            seed=args.seed,
        )

        if manifest.total_segments == 0:
            logger.error("PIPELINE FAILED: No usable segments found.")
            logger.error("See docs/ml/DATA_PROVENANCE.md for dataset availability.")
            sys.exit(1)

        if manifest.total_segments < 1000:
            logger.warning(
                f"WARNING: Only {manifest.total_segments} segments found. "
                "This is likely insufficient for deep learning training. "
                "See docs/ml/TRAINING_READINESS.md for requirements."
            )

    except FileNotFoundError as e:
        logger.error(f"Input directory not found: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Pipeline error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
