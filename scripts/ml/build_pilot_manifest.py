# scripts/ml/build_pilot_manifest.py
"""Real Pilot Dataset Manifest Builder for LUMINA ML.

Builds a versioned dataset manifest for the real pilot dataset.
The manifest tracks provenance, statistics, and acceptance status.

USAGE:
    python -m scripts.ml.build_pilot_manifest \
        --dataset-dir ./data/real-pilot-v0.1 \
        --output-dir ./data/real-pilot-v0.1

CRITICAL: This script reads existing data and builds a manifest.
          It does NOT create, generate, or fabricate data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---- Constants ----

LUMINA_LABELS = {
    "AUTHORITY_CLAIM", "THREAT_PRESENTATION", "TIME_PRESSURE",
    "ISOLATION_TACTIC", "CREDENTIAL_REQUEST", "FINANCIAL_REQUEST",
    "REMOTE_ACCESS_REQUEST", "IDENTITY_REQUEST", "BENIGN_CONVERSATION",
    "USER_RESISTANCE", "ADVICE_OR_WARNING",
}


# ---- Loading ----

def load_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    """Load records from a JSONL file."""
    records = []
    if not file_path.exists():
        return records
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


# ---- Checksums ----

def compute_file_checksum(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"


# ---- Statistics ----

def compute_statistics(
    consents: List[Dict],
    conversations: List[Dict],
    segments: List[Dict],
) -> Dict[str, Any]:
    """Compute dataset statistics."""
    stats = {}

    # Conversation statistics
    stats["total_conversations"] = len(conversations)
    stats["real_two_party"] = sum(
        1 for c in conversations
        if c.get("conversation_type") == "REAL_TWO_PARTY"
    )
    stats["one_sided"] = sum(
        1 for c in conversations
        if c.get("conversation_type") == "ONE_SIDED"
    )
    stats["roleplay"] = sum(
        1 for c in conversations
        if c.get("conversation_type") == "ROLEPLAY"
    )
    stats["synthetic"] = sum(
        1 for c in conversations
        if c.get("conversation_type") == "SYNTHETIC"
    )
    stats["unknown_provenance"] = sum(
        1 for c in conversations
        if c.get("conversation_type") == "UNKNOWN"
    )

    # Language
    stats["english"] = sum(
        1 for c in conversations
        if c.get("language") == "en"
    )
    stats["non_english"] = len(conversations) - stats["english"]

    # Speaker attribution
    stats["with_speaker_attribution"] = sum(
        1 for c in conversations
        if c.get("speaker_structure") == "TWO_PARTY"
    )
    stats["with_usable_transcripts"] = sum(
        1 for c in conversations
        if c.get("transcript", {}).get("text")
    )

    # Segment statistics
    stats["total_segments"] = len(segments)
    stats["annotated_segments"] = sum(
        1 for s in segments
        if s.get("tactic_labels")
    )
    stats["unannotated_segments"] = stats["total_segments"] - stats["annotated_segments"]

    # Label distribution
    label_counts: Counter = Counter()
    for seg in segments:
        labels = seg.get("tactic_labels", [])
        if isinstance(labels, list):
            for label_obj in labels:
                label = label_obj.get("label") if isinstance(label_obj, dict) else label_obj
                if label in LUMINA_LABELS:
                    label_counts[label] += 1
    stats["label_distribution"] = dict(label_counts)

    # Speaker distribution
    speaker_counts: Counter = Counter()
    for seg in segments:
        speaker = seg.get("speaker", "UNKNOWN")
        speaker_counts[speaker] += 1
    stats["speaker_distribution"] = dict(speaker_counts)

    # Consent statistics
    stats["total_consents"] = len(consents)
    stats["withdrawn_consents"] = sum(
        1 for c in consents
        if c.get("deletion_status") == "WITHDRAWN"
    )

    # Excluded
    stats["excluded_conversations"] = sum(
        1 for c in conversations
        if c.get("deletion_status") in ("WITHDRAWN", "DELETED")
    )

    return stats


# ---- Main ----

def build_manifest(dataset_dir: Path) -> Dict[str, Any]:
    """Build dataset manifest."""
    # Load data
    consents = load_jsonl(dataset_dir / "consents.jsonl")
    conversations = load_jsonl(dataset_dir / "conversations.jsonl")
    segments = load_jsonl(dataset_dir / "segments.jsonl")

    logger.info(f"Loaded: {len(consents)} consents, {len(conversations)} conversations, {len(segments)} segments")

    # Compute statistics
    stats = compute_statistics(consents, conversations, segments)

    # Compute checksums
    checksums = {}
    for filename in ["consents.jsonl", "conversations.jsonl", "segments.jsonl",
                     "train.jsonl", "val.jsonl", "test.jsonl"]:
        file_path = dataset_dir / filename
        if file_path.exists():
            checksums[filename] = compute_file_checksum(file_path)

    # Build manifest
    manifest = {
        "manifest_id": "generated",
        "dataset_version": "pilot-v0.1",
        "schema_version": "1.0",
        "taxonomy_version": "1.0",
        "consent_version": "1.0",
        "sanitization_version": "1.0",
        "annotation_version": "1.0",
        "split_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "build_pilot_manifest",
        "total_conversations": stats["total_conversations"],
        "total_segments": stats["total_segments"],
        "real_two_party_conversations": stats["real_two_party"],
        "annotated_segments": stats["annotated_segments"],
        "label_distribution": stats["label_distribution"],
        "speaker_distribution": stats["speaker_distribution"],
        "split_distribution": {
            "train": len(load_jsonl(dataset_dir / "train.jsonl")),
            "validation": len(load_jsonl(dataset_dir / "val.jsonl")),
            "test": len(load_jsonl(dataset_dir / "test.jsonl")),
        },
        "statistics": stats,
        "provenance_registry": [],
        "acceptance_status": "PENDING",
        "training_status": "NO_GO",
        "checksums": checksums,
    }

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build LUMINA real pilot dataset manifest"
    )
    parser.add_argument(
        "--dataset-dir", type=Path, required=True,
        help="Path to real pilot dataset directory",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Output directory (default: dataset-dir)",
    )

    args = parser.parse_args()

    if not args.dataset_dir.exists():
        logger.error(f"Dataset directory not found: {args.dataset_dir}")
        sys.exit(1)

    output_dir = args.output_dir or args.dataset_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build manifest
    manifest = build_manifest(args.dataset_dir)

    # Save manifest
    manifest_path = output_dir / "dataset_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    logger.info(f"Manifest saved to {manifest_path}")

    # Print summary
    logger.info(f"\n{'=' * 60}")
    logger.info("Dataset Manifest Built")
    logger.info(f"{'=' * 60}")
    logger.info(f"Version: {manifest['dataset_version']}")
    logger.info(f"Conversations: {manifest['total_conversations']}")
    logger.info(f"Real two-party: {manifest['real_two_party_conversations']}")
    logger.info(f"Segments: {manifest['total_segments']}")
    logger.info(f"Annotated: {manifest['annotated_segments']}")
    logger.info(f"Label distribution: {manifest['label_distribution']}")
    logger.info(f"Training status: {manifest['training_status']}")


if __name__ == "__main__":
    main()
