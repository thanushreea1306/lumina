# scripts/ml/validate_real_pilot.py
"""Real Pilot Dataset Validation Script for LUMINA ML.

Validates that a real pilot dataset meets all acceptance criteria
before any model training can proceed.

Checks:
  - Consent validity
  - Audio provenance
  - Two-party structure
  - Privacy/PII
  - Annotation quality
  - Label coverage
  - Data split integrity
  - Dataset integrity

USAGE:
    python -m scripts.ml.validate_real_pilot --dataset-dir ./data/real-pilot-v0.1

CRITICAL: This script validates REAL data only.
          It does NOT create, generate, or fabricate data.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---- Constants ----

LUMINA_LABELS = {
    "AUTHORITY_CLAIM", "THREAT_PRESENTATION", "TIME_PRESSURE",
    "ISOLATION_TACTIC", "CREDENTIAL_REQUEST", "FINANCIAL_REQUEST",
    "REMOTE_ACCESS_REQUEST", "IDENTITY_REQUEST", "BENIGN_CONVERSATION",
    "USER_RESISTANCE", "ADVICE_OR_WARNING",
}

VALID_SPEAKERS = {"CALLER", "RECIPIENT", "UNKNOWN"}
VALID_CONVERSATION_TYPES = {"REAL_TWO_PARTY", "ONE_SIDED", "ROLEPLAY", "SYNTHETIC", "UNKNOWN"}
VALID_RECORDING_SOURCES = {"USER_PROVIDED_RECORDING", "AUTHORIZED_RESEARCH_RECORDING", "CONTROLLED_ROLEPLAY", "NOT_VERIFIED"}

# Minimum thresholds
MIN_CONVERSATIONS = 50
MIN_SEGMENTS = 500
MIN_PER_TACTIC = 10
MIN_BENIGN = 50
MIN_TEST_CONVERSATIONS = 10
MIN_DOUBLE_ANNOTATED_PCT = 0.20
MIN_KAPPA = 0.5
MIN_SPEAKER_ATTRIBUTION = 0.80

# PII Detection Patterns
_PII_PATTERNS = [
    (re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'), "phone"),
    (re.compile(r'\b\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b'), "phone"),
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), "email"),
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), "ssn"),
    (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), "card"),
]


# ---- Data Structures ----

@dataclass
class AcceptanceResult:
    """Result of a single acceptance check."""
    criterion: str
    passed: bool
    message: str
    severity: str = "BLOCKER"  # BLOCKER, WARNING, INFO
    details: Optional[Dict[str, Any]] = None


@dataclass
class AcceptanceReport:
    """Complete real pilot dataset acceptance report."""
    dataset_version: str = "unknown"
    total_criteria: int = 0
    passed_criteria: int = 0
    failed_criteria: int = 0
    warning_criteria: int = 0
    results: List[AcceptanceResult] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        """Dataset is accepted only if no BLOCKER criteria fail."""
        return not any(
            r.passed is False and r.severity == "BLOCKER"
            for r in self.results
        )

    @property
    def has_warnings(self) -> bool:
        return self.warning_criteria > 0

    def add_result(self, result: AcceptanceResult) -> None:
        self.results.append(result)
        self.total_criteria += 1
        if result.passed:
            self.passed_criteria += 1
        else:
            if result.severity == "WARNING":
                self.warning_criteria += 1
            else:
                self.failed_criteria += 1


# ---- Loading ----

def load_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    """Load records from a JSONL file."""
    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning(f"Skipping invalid JSON on line {i + 1}")
    return records


def load_all_splits(dataset_dir: Path) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Load train, val, test splits."""
    train = load_jsonl(dataset_dir / "train.jsonl")
    val = load_jsonl(dataset_dir / "val.jsonl")
    test = load_jsonl(dataset_dir / "test.jsonl")
    return train, val, test


# ---- Consent Checks ----

def check_consent(consents: List[Dict]) -> List[AcceptanceResult]:
    """A1: Consent validity checks."""
    results = []

    required_permissions = [
        "participation", "audio_recording", "speech_to_text",
        "behavioral_ml_annotation", "ml_model_training", "research_evaluation",
    ]

    # A1.1: Consent records exist
    results.append(AcceptanceResult(
        criterion="A1.1_consent_records_exist",
        passed=len(consents) > 0,
        message=f"Consent records: {len(consents)}",
        severity="BLOCKER",
    ))

    # A1.2: All required permissions granted
    missing_permissions = []
    for consent in consents:
        perms = consent.get("permissions", {})
        for perm in required_permissions:
            if not perms.get(perm, False):
                missing_permissions.append(f"{consent.get('consent_id', 'unknown')}:{perm}")

    results.append(AcceptanceResult(
        criterion="A1.2_required_permissions",
        passed=len(missing_permissions) == 0,
        message=f"Missing permissions: {len(missing_permissions)}" if missing_permissions else
                "All required permissions granted",
        severity="BLOCKER",
    ))

    # A1.4: Consent not withdrawn
    withdrawn = sum(1 for c in consents if c.get("deletion_status") == "WITHDRAWN")
    results.append(AcceptanceResult(
        criterion="A1.4_consent_not_withdrawn",
        passed=withdrawn == 0,
        message=f"Withdrawn consents: {withdrawn}" if withdrawn else
                "No withdrawn consents",
        severity="BLOCKER",
    ))

    # A1.5: Age verified
    age_verified = all(c.get("age_confirmed_over_18", False) for c in consents)
    results.append(AcceptanceResult(
        criterion="A1.5_age_verified",
        passed=age_verified,
        message=f"Age verification: {'all verified' if age_verified else 'FAILED'}",
        severity="BLOCKER",
    ))

    return results


# ---- Provenance Checks ----

def check_provenance(conversations: List[Dict]) -> List[AcceptanceResult]:
    """A2: Audio provenance checks."""
    results = []

    # A2.1: Recording source known
    unknown_sources = sum(
        1 for c in conversations
        if c.get("recording_source") not in VALID_RECORDING_SOURCES
    )
    results.append(AcceptanceResult(
        criterion="A2.1_recording_source_known",
        passed=unknown_sources == 0,
        message=f"Unknown recording sources: {unknown_sources}" if unknown_sources else
                "All recording sources valid",
        severity="BLOCKER",
    ))

    # A2.2: Not synthetic
    synthetic = sum(
        1 for c in conversations
        if c.get("recording_source") == "SYNTHETIC" or c.get("conversation_type") == "SYNTHETIC"
    )
    results.append(AcceptanceResult(
        criterion="A2.2_not_synthetic",
        passed=synthetic == 0,
        message=f"Synthetic conversations: {synthetic}" if synthetic else
                "No synthetic conversations",
        severity="BLOCKER",
    ))

    # A2.3: Not roleplay (for real pool)
    roleplay = sum(
        1 for c in conversations
        if c.get("conversation_type") == "ROLEPLAY"
    )
    results.append(AcceptanceResult(
        criterion="A2.3_not_roleplay",
        passed=roleplay == 0,
        message=f"Roleplay conversations: {roleplay}" if roleplay else
                "No roleplay conversations in real pool",
        severity="BLOCKER",
    ))

    # A2.4: Provenance verified
    unverified = sum(
        1 for c in conversations
        if not c.get("provenance", {}).get("provenance_verified", False)
    )
    results.append(AcceptanceResult(
        criterion="A2.4_provenance_verified",
        passed=unverified == 0,
        message=f"Unverified provenance: {unverified}" if unverified else
                "All provenance verified",
        severity="BLOCKER",
    ))

    return results


# ---- Two-Party Checks ----

def check_two_party(conversations: List[Dict], segments: List[Dict]) -> List[AcceptanceResult]:
    """A3: Two-party structure checks."""
    results = []

    # A3.1: Speaker structure
    non_two_party = sum(
        1 for c in conversations
        if c.get("speaker_structure") != "TWO_PARTY"
    )
    results.append(AcceptanceResult(
        criterion="A3.1_speaker_structure",
        passed=non_two_party == 0,
        message=f"Non-two-party conversations: {non_two_party}" if non_two_party else
                "All conversations are two-party",
        severity="BLOCKER",
    ))

    # A3.2: ≥2 participants
    insufficient_participants = sum(
        1 for c in conversations
        if len(c.get("participant_ids", [])) < 2
    )
    results.append(AcceptanceResult(
        criterion="A3.2_insufficient_participants",
        passed=insufficient_participants == 0,
        message=f"Conversations with <2 participants: {insufficient_participants}" if insufficient_participants else
                "All conversations have ≥2 participants",
        severity="BLOCKER",
    ))

    # A3.4: Speaker attribution
    attributed = sum(
        1 for s in segments
        if s.get("speaker") in {"CALLER", "RECIPIENT"}
    )
    attribution_rate = attributed / len(segments) if segments else 0.0
    results.append(AcceptanceResult(
        criterion="A3.4_speaker_attribution",
        passed=attribution_rate >= MIN_SPEAKER_ATTRIBUTION,
        message=f"Speaker attribution: {attribution_rate:.1%} ({attributed}/{len(segments)})",
        severity="BLOCKER",
    ))

    return results


# ---- Scale Checks ----

def check_scale(conversations: List[Dict], segments: List[Dict]) -> List[AcceptanceResult]:
    """C1: Scale checks."""
    results = []

    real_two_party = sum(
        1 for c in conversations
        if c.get("conversation_type") == "REAL_TWO_PARTY"
    )

    results.append(AcceptanceResult(
        criterion="C1.1_minimum_conversations",
        passed=real_two_party >= MIN_CONVERSATIONS,
        message=f"Real two-party conversations: {real_two_party} (minimum: {MIN_CONVERSATIONS})",
        severity="BLOCKER",
    ))
    results.append(AcceptanceResult(
        criterion="C1.2_minimum_segments",
        passed=len(segments) >= MIN_SEGMENTS,
        message=f"Segments: {len(segments)} (minimum: {MIN_SEGMENTS})",
        severity="BLOCKER",
    ))
    results.append(AcceptanceResult(
        criterion="C1.3_recommended_conversations",
        passed=real_two_party >= 100,
        message=f"Real two-party conversations: {real_two_party} (recommended: 100)",
        severity="WARNING",
    ))
    results.append(AcceptanceResult(
        criterion="C1.4_recommended_segments",
        passed=len(segments) >= 1500,
        message=f"Segments: {len(segments)} (recommended: 1500)",
        severity="WARNING",
    ))

    return results


# ---- Label Coverage Checks ----

def check_label_coverage(segments: List[Dict]) -> List[AcceptanceResult]:
    """C2: Label coverage checks."""
    results = []

    label_counts: Counter = Counter()
    multi_label_count = 0
    for seg in segments:
        labels = seg.get("tactic_labels", [])
        if isinstance(labels, list):
            for label_obj in labels:
                label = label_obj.get("label") if isinstance(label_obj, dict) else label_obj
                if label in LUMINA_LABELS:
                    label_counts[label] += 1
            if len(labels) >= 2:
                multi_label_count += 1

    # C2.1: All tactics represented
    missing = LUMINA_LABELS - set(label_counts.keys())
    results.append(AcceptanceResult(
        criterion="C2.1_all_tactics_represented",
        passed=len(missing) == 0,
        message=f"Missing tactics: {missing}" if missing else "All 11 tactics present",
        severity="BLOCKER",
    ))

    # C2.2: Minimum per tactic
    below_min = {
        label: count for label, count in label_counts.items()
        if count < MIN_PER_TACTIC
    }
    results.append(AcceptanceResult(
        criterion="C2.2_minimum_per_tactic",
        passed=len(below_min) == 0,
        message=f"Tactics below minimum: {below_min}" if below_min else
                f"All tactics have ≥{MIN_PER_TACTIC} examples",
        severity="BLOCKER",
    ))

    # C2.3: BENIGN coverage
    benign_count = label_counts.get("BENIGN_CONVERSATION", 0)
    results.append(AcceptanceResult(
        criterion="C2.3_benign_coverage",
        passed=benign_count >= MIN_BENIGN,
        message=f"BENIGN_CONVERSATION: {benign_count} (minimum: {MIN_BENIGN})",
        severity="BLOCKER",
    ))

    # C2.4: Multi-label support
    results.append(AcceptanceResult(
        criterion="C2.4_multi_label_support",
        passed=multi_label_count > 0,
        message=f"Multi-label segments: {multi_label_count}",
        severity="WARNING",
    ))

    # C2.5: No class collapse
    if label_counts:
        max_count = max(label_counts.values())
        total = sum(label_counts.values())
        max_pct = max_count / total if total > 0 else 0.0
        results.append(AcceptanceResult(
            criterion="C2.5_no_class_collapse",
            passed=max_pct < 0.8,
            message=f"Most common label: {max_pct:.1%} of all labels",
            severity="BLOCKER",
        ))

    return results


# ---- Privacy Checks ----

def check_privacy(segments: List[Dict]) -> List[AcceptanceResult]:
    """C5: Privacy checks."""
    results = []

    pii_detections = []
    for seg in segments:
        text = seg.get("text", "")
        for pattern, pii_type in _PII_PATTERNS:
            if pattern.search(text):
                pii_detections.append({
                    "segment_id": seg.get("segment_id"),
                    "pii_type": pii_type,
                })
                break

    results.append(AcceptanceResult(
        criterion="C5.1_no_pii",
        passed=len(pii_detections) == 0,
        message=f"PII detections: {len(pii_detections)}" if pii_detections else
                "No PII detected",
        severity="BLOCKER",
    ))

    # Check for secrets
    secret_patterns = [
        re.compile(r'password\s*[:=]\s*\S+', re.IGNORECASE),
        re.compile(r'api[_-]?key\s*[:=]\s*\S+', re.IGNORECASE),
    ]
    secret_detections = 0
    for seg in segments:
        text = seg.get("text", "")
        for pattern in secret_patterns:
            if pattern.search(text):
                secret_detections += 1
                break

    results.append(AcceptanceResult(
        criterion="C5.2_no_secrets",
        passed=secret_detections == 0,
        message=f"Secret detections: {secret_detections}" if secret_detections else
                "No secrets detected",
        severity="BLOCKER",
    ))

    return results


# ---- Integrity Checks ----

def check_integrity(segments: List[Dict]) -> List[AcceptanceResult]:
    """C6: Dataset integrity checks."""
    results = []

    # C6.1: No duplicate segments
    text_hashes = Counter()
    for seg in segments:
        text = seg.get("text", "").lower().strip()
        text_hashes[text] += 1
    duplicates = sum(count - 1 for count in text_hashes.values() if count > 1)

    results.append(AcceptanceResult(
        criterion="C6.1_no_duplicates",
        passed=duplicates == 0,
        message=f"Duplicate segments: {duplicates}" if duplicates else
                "No duplicate segments",
        severity="BLOCKER",
    ))

    # C6.2: No empty transcripts
    empty = sum(1 for seg in segments if not seg.get("text", "").strip())
    results.append(AcceptanceResult(
        criterion="C6.2_no_empty_transcripts",
        passed=empty == 0,
        message=f"Empty transcripts: {empty}" if empty else
                "No empty transcripts",
        severity="BLOCKER",
    ))

    # C6.3: No invalid labels
    invalid_labels = set()
    for seg in segments:
        labels = seg.get("tactic_labels", [])
        if isinstance(labels, list):
            for label_obj in labels:
                label = label_obj.get("label") if isinstance(label_obj, dict) else label_obj
                if label not in LUMINA_LABELS and label != "UNKNOWN":
                    invalid_labels.add(label)

    results.append(AcceptanceResult(
        criterion="C6.3_no_invalid_labels",
        passed=len(invalid_labels) == 0,
        message=f"Invalid labels: {invalid_labels}" if invalid_labels else
                "All labels valid",
        severity="BLOCKER",
    ))

    # C6.4: No invalid speakers
    invalid_speakers = set()
    for seg in segments:
        speaker = seg.get("speaker", "UNKNOWN")
        if speaker not in VALID_SPEAKERS:
            invalid_speakers.add(speaker)

    results.append(AcceptanceResult(
        criterion="C6.4_no_invalid_speakers",
        passed=len(invalid_speakers) == 0,
        message=f"Invalid speakers: {invalid_speakers}" if invalid_speakers else
                "All speakers valid",
        severity="BLOCKER",
    ))

    return results


# ---- Split Checks ----

def check_split(train: List[Dict], val: List[Dict], test: List[Dict]) -> List[AcceptanceResult]:
    """C4: Data split checks."""
    results = []

    train_convs = set(s.get("conversation_id", "") for s in train)
    val_convs = set(s.get("conversation_id", "") for s in val)
    test_convs = set(s.get("conversation_id", "") for s in test)

    # C4.1: Conversation-level split
    overlaps = (train_convs & val_convs) | (train_convs & test_convs) | (val_convs & test_convs)
    results.append(AcceptanceResult(
        criterion="C4.1_conversation_level_split",
        passed=len(overlaps) == 0,
        message=f"Conversation overlap: {len(overlaps)}" if overlaps else
                "No conversation overlap between splits",
        severity="BLOCKER",
    ))

    # C4.3: No text leakage
    train_texts = set(s.get("text", "").lower().strip() for s in train)
    val_texts = set(s.get("text", "").lower().strip() for s in val)
    test_texts = set(s.get("text", "").lower().strip() for s in test)
    text_overlaps = (train_texts & val_texts) | (train_texts & test_texts) | (val_texts & test_texts)
    results.append(AcceptanceResult(
        criterion="C4.3_no_text_leakage",
        passed=len(text_overlaps) == 0,
        message=f"Text leakage: {len(text_overlaps)}" if text_overlaps else
                "No text leakage between splits",
        severity="BLOCKER",
    ))

    # C4.5: Minimum test size
    results.append(AcceptanceResult(
        criterion="C4.5_minimum_test_size",
        passed=len(test_convs) >= MIN_TEST_CONVERSATIONS,
        message=f"Test conversations: {len(test_convs)} (minimum: {MIN_TEST_CONVERSATIONS})",
        severity="BLOCKER",
    ))

    return results


# ---- Main ----

def run_validation(dataset_dir: Path) -> AcceptanceReport:
    """Run all real pilot dataset acceptance checks."""
    report = AcceptanceReport()

    # Load manifest
    manifest_path = dataset_dir / "dataset_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        report.dataset_version = manifest.get("dataset_version", "unknown")

    # Load data
    try:
        consents = load_jsonl(dataset_dir / "consents.jsonl") if (dataset_dir / "consents.jsonl").exists() else []
        conversations = load_jsonl(dataset_dir / "conversations.jsonl") if (dataset_dir / "conversations.jsonl").exists() else []
        segments = load_jsonl(dataset_dir / "segments.jsonl") if (dataset_dir / "segments.jsonl").exists() else []
        train, val, test = load_all_splits(dataset_dir)
    except FileNotFoundError as e:
        report.add_result(AcceptanceResult(
            criterion="data_files_exist",
            passed=False,
            message=f"Missing file: {e}",
            severity="BLOCKER",
        ))
        return report

    all_segments = train + val + test

    logger.info(f"Validating real pilot dataset: {dataset_dir}")
    logger.info(f"  Consents: {len(consents)}")
    logger.info(f"  Conversations: {len(conversations)}")
    logger.info(f"  Segments: {len(all_segments)}")

    # Run all checks
    all_checks = []
    all_checks.extend(check_consent(consents))
    all_checks.extend(check_provenance(conversations))
    all_checks.extend(check_two_party(conversations, all_segments))
    all_checks.extend(check_scale(conversations, all_segments))
    all_checks.extend(check_label_coverage(all_segments))
    all_checks.extend(check_split(train, val, test))
    all_checks.extend(check_privacy(all_segments))
    all_checks.extend(check_integrity(all_segments))

    for result in all_checks:
        report.add_result(result)
        status = "✓" if result.passed else ("⚠" if result.severity == "WARNING" else "✗")
        logger.info(f"  {status} [{result.severity}] {result.criterion}: {result.message}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate LUMINA real pilot dataset acceptance criteria"
    )
    parser.add_argument(
        "--dataset-dir", type=Path, required=True,
        help="Path to real pilot dataset directory",
    )
    args = parser.parse_args()

    if not args.dataset_dir.exists():
        logger.error(f"Dataset directory not found: {args.dataset_dir}")
        sys.exit(1)

    report = run_validation(args.dataset_dir)

    logger.info(f"\n{'=' * 60}")
    logger.info("Real Pilot Dataset Acceptance Report")
    logger.info(f"{'=' * 60}")
    logger.info(f"Dataset version: {report.dataset_version}")
    logger.info(f"Total criteria: {report.total_criteria}")
    logger.info(f"Passed: {report.passed_criteria}")
    logger.info(f"Failed: {report.failed_criteria}")
    logger.info(f"Warnings: {report.warning_criteria}")
    logger.info(f"Result: {'ACCEPTED' if report.accepted else 'REJECTED'}")

    if not report.accepted:
        logger.error("\nFailed BLOCKER criteria:")
        for result in report.results:
            if not result.passed and result.severity == "BLOCKER":
                logger.error(f"  - {result.criterion}: {result.message}")
        sys.exit(1)

    if report.has_warnings:
        logger.warning("\nWarnings:")
        for result in report.results:
            if not result.passed and result.severity == "WARNING":
                logger.warning(f"  - {result.criterion}: {result.message}")

    logger.info("\nReal pilot dataset ACCEPTED for baseline training.")


if __name__ == "__main__":
    main()
