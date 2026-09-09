# scripts/ml/split_real_pilot.py
"""Real Pilot Dataset Conversation-Level Splitting for LUMINA ML.

Splits a real pilot dataset into train/validation/test splits at the
CONVERSATION level (not segment level) to prevent data leakage.

No conversation may appear in multiple splits.

USAGE:
    python -m scripts.ml.split_real_pilot \
        --input-dir ./data/real-pilot-raw \
        --output-dir ./data/real-pilot-v0.1 \
        --seed 42

CRITICAL: This script operates on REAL data only.
          It does NOT create, generate, or fabricate data.
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---- Constants ----

DEFAULT_SEED = 42
DEFAULT_TRAIN_RATIO = 0.8
DEFAULT_VAL_RATIO = 0.1
DEFAULT_TEST_RATIO = 0.1


# ---- Data Structures ----

@dataclass
class SplitManifest:
    """Manifest recording the split algorithm and verification."""
    seed: int
    train_ratio: float
    val_ratio: float
    test_ratio: float
    total_conversations: int = 0
    total_segments: int = 0
    train_conversations: int = 0
    val_conversations: int = 0
    test_conversations: int = 0
    train_segments: int = 0
    val_segments: int = 0
    test_segments: int = 0
    verification_passed: bool = False
    label_distribution: Dict[str, int] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "train_ratio": self.train_ratio,
            "val_ratio": self.val_ratio,
            "test_ratio": self.test_ratio,
            "total_conversations": self.total_conversations,
            "total_segments": self.total_segments,
            "train_conversations": self.train_conversations,
            "val_conversations": self.val_conversations,
            "test_conversations": self.test_conversations,
            "train_segments": self.train_segments,
            "val_segments": self.val_segments,
            "test_segments": self.test_segments,
            "verification_passed": self.verification_passed,
            "label_distribution": self.label_distribution,
            "created_at": self.created_at,
        }


# ---- Loading ----

def load_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    """Load records from a JSONL file."""
    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


# ---- Splitting ----

def split_by_conversation(
    segments: List[Dict[str, Any]],
    seed: int = DEFAULT_SEED,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    val_ratio: float = DEFAULT_VAL_RATIO,
    test_ratio: float = DEFAULT_TEST_RATIO,
) -> Dict[str, List[Dict[str, Any]]]:
    """Split segments by conversation ID to prevent data leakage."""
    # Group by conversation
    conversations: Dict[str, List[Dict[str, Any]]] = {}
    for seg in segments:
        conv_id = seg.get("conversation_id", f"unknown_{id(seg)}")
        if conv_id not in conversations:
            conversations[conv_id] = []
        conversations[conv_id].append(seg)

    conv_ids = list(conversations.keys())
    logger.info(f"Found {len(conv_ids)} unique conversations")

    # Deterministic shuffle
    rng = random.Random(seed)
    rng.shuffle(conv_ids)

    # Calculate split boundaries
    n = len(conv_ids)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train_conv_ids = conv_ids[:train_end]
    val_conv_ids = conv_ids[train_end:val_end]
    test_conv_ids = conv_ids[val_end:]

    # Assemble splits
    train_segments = []
    for conv_id in train_conv_ids:
        conv_segs = sorted(conversations[conv_id], key=lambda s: s.get("segment_index", 0))
        train_segments.extend(conv_segs)

    val_segments = []
    for conv_id in val_conv_ids:
        conv_segs = sorted(conversations[conv_id], key=lambda s: s.get("segment_index", 0))
        val_segments.extend(conv_segs)

    test_segments = []
    for conv_id in test_conv_ids:
        conv_segs = sorted(conversations[conv_id], key=lambda s: s.get("segment_index", 0))
        test_segments.extend(conv_segs)

    # Verify no leakage
    train_set = set(train_conv_ids)
    val_set = set(val_conv_ids)
    test_set = set(test_conv_ids)

    assert train_set.isdisjoint(val_set), "Train/Val conversation leak!"
    assert train_set.isdisjoint(test_set), "Train/Test conversation leak!"
    assert val_set.isdisjoint(test_set), "Val/Test conversation leak!"

    logger.info(
        f"Split: {len(train_conv_ids)} train convs ({len(train_segments)} segs), "
        f"{len(val_conv_ids)} val convs ({len(val_segments)} segs), "
        f"{len(test_conv_ids)} test convs ({len(test_segments)} segs)"
    )

    return {
        "train": train_segments,
        "val": val_segments,
        "test": test_segments,
    }


# ---- Verification ----

def verify_split(
    train: List[Dict], val: List[Dict], test: List[Dict]
) -> bool:
    """Verify that no conversation appears in multiple splits."""
    train_convs = set(s.get("conversation_id") for s in train)
    val_convs = set(s.get("conversation_id") for s in val)
    test_convs = set(s.get("conversation_id") for s in test)

    overlaps = (train_convs & val_convs) | (train_convs & test_convs) | (val_convs & test_convs)
    if overlaps:
        logger.error(f"LEAKAGE: {len(overlaps)} conversations in multiple splits")
        return False

    # Check text leakage
    train_texts = set(s.get("text", "").lower().strip() for s in train)
    val_texts = set(s.get("text", "").lower().strip() for s in val)
    test_texts = set(s.get("text", "").lower().strip() for s in test)
    text_overlaps = (train_texts & val_texts) | (train_texts & test_texts) | (val_texts & test_texts)
    if text_overlaps:
        logger.error(f"TEXT LEAKAGE: {len(text_overlaps)} duplicate texts")
        return False

    logger.info("Split verification PASSED")
    return True


# ---- Saving ----

def save_split(segments: List[Dict], output_dir: Path, split_name: str) -> None:
    """Save a split to a JSONL file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{split_name}.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(json.dumps(seg, ensure_ascii=False) + "\n")
    logger.info(f"Saved {len(segments)} segments to {output_path}")


# ---- Main ----

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split LUMINA real pilot dataset by conversation"
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--train-ratio", type=float, default=DEFAULT_TRAIN_RATIO)
    parser.add_argument("--val-ratio", type=float, default=DEFAULT_VAL_RATIO)
    parser.add_argument("--test-ratio", type=float, default=DEFAULT_TEST_RATIO)

    args = parser.parse_args()

    # Load segments
    input_file = args.input_dir / "segments.jsonl"
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        sys.exit(1)

    segments = load_jsonl(input_file)
    if not segments:
        logger.error("No segments loaded")
        sys.exit(1)

    logger.info(f"Loaded {len(segments)} segments")

    # Split
    splits = split_by_conversation(
        segments, seed=args.seed,
        train_ratio=args.train_ratio, val_ratio=args.val_ratio, test_ratio=args.test_ratio,
    )

    # Verify
    verified = verify_split(splits["train"], splits["val"], splits["test"])

    # Save
    for split_name, split_segments in splits.items():
        save_split(split_segments, args.output_dir, split_name)

    # Build manifest
    conv_ids_all = set(s.get("conversation_id") for s in segments)
    label_dist: Counter = Counter()
    for seg in segments:
        for label_obj in seg.get("tactic_labels", []):
            label = label_obj.get("label") if isinstance(label_obj, dict) else label_obj
            label_dist[label] += 1

    manifest = SplitManifest(
        seed=args.seed, train_ratio=args.train_ratio,
        val_ratio=args.val_ratio, test_ratio=args.test_ratio,
        total_conversations=len(conv_ids_all), total_segments=len(segments),
        train_conversations=len(set(s.get("conversation_id") for s in splits["train"])),
        val_conversations=len(set(s.get("conversation_id") for s in splits["val"])),
        test_conversations=len(set(s.get("conversation_id") for s in splits["test"])),
        train_segments=len(splits["train"]), val_segments=len(splits["val"]),
        test_segments=len(splits["test"]),
        verification_passed=verified, label_distribution=dict(label_dist),
    )

    manifest_path = args.output_dir / "split_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)

    logger.info(f"\nSplit complete. Verified: {verified}")


if __name__ == "__main__":
    main()
