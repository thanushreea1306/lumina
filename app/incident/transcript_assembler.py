# app/incident/transcript_assembler.py
"""Incremental Transcript Assembler.

Solves the chunk-boundary quality problem from CP-15:

  Problem:
    Whisper transcribes each audio chunk independently.
    This can cause:
    - Words split across chunk boundaries
    - Duplicated words at overlaps
    - Missing words at boundaries
    - Incorrect global timestamps
    - Loss of conversational context

  Solution:
    This assembler accumulates transcript segments from multiple chunks,
    maintains stable global timestamps, suppresses duplicate segments,
    and produces a coherent incremental transcript.

DESIGN PRINCIPLES:
  - Deterministic: same input always produces same output
  - Append-only: new segments are added, old segments never modified
  - Idempotent: reprocessing the same chunk does not create duplicates
  - Honest: does not invent words or fabricate context
  - Source-preserving: every segment retains its provenance

NOT TRUE NEURAL STREAMING:
  This is incremental batch assembly, not streaming inference.
  Each chunk is transcribed independently by Whisper.
  The assembler handles the post-processing of combining results.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from app.incident.transcript_provider import TranscriptSegment


# ---- Duplicate Detection ----

# Minimum similarity ratio for two segments to be considered duplicates.
# Uses simple word-overlap Jaccard similarity.
_DUPLICATE_THRESHOLD = 0.85


def _normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, strip, collapse whitespace."""
    return re.sub(r'\s+', ' ', text.strip().lower())


def _word_set(text: str) -> Set[str]:
    """Extract a set of words from text."""
    return set(_normalize_text(text).split())


def _jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    """Compute Jaccard similarity between two word sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


def is_duplicate(seg_a: TranscriptSegment, seg_b: TranscriptSegment) -> bool:
    """Determine if two segments are duplicates.

    Uses word-overlap similarity. Two segments are duplicates if:
    1. They have very similar text (Jaccard > threshold)
    2. Their timestamps overlap or are very close

    This is conservative: it only suppresses near-exact duplicates,
    not repeated phrases that are legitimately part of the conversation.
    """
    words_a = _word_set(seg_a.text)
    words_b = _word_set(seg_b.text)

    similarity = _jaccard_similarity(words_a, words_b)
    if similarity < _DUPLICATE_THRESHOLD:
        return False

    # Check timestamp overlap if both have timestamps
    if seg_a.start_time is not None and seg_b.start_time is not None:
        # If timestamps are more than 2 seconds apart, they're probably
        # different utterances of similar text (not duplicates)
        time_diff = abs(seg_a.start_time - seg_b.start_time)
        if time_diff > 2.0:
            return False

    return True


# ---- Assembled Transcript ----


@dataclass
class AssembledTranscript:
    """An incrementally-built transcript from multiple chunks.

    Maintains a stable, ordered list of segments with global timestamps
    and deduplication.
    """
    transcript_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    incident_id: str = ""
    segments: List[TranscriptSegment] = field(default_factory=list)
    full_text: str = ""
    chunk_count: int = 0
    total_duplicate_segments_suppressed: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    def add_chunk_segments(
        self,
        new_segments: List[TranscriptSegment],
        chunk_sequence: int,
        chunk_duration_offset: float = 0.0,
    ) -> List[TranscriptSegment]:
        """Add segments from a new chunk, with deduplication.

        Args:
            new_segments: Segments produced by transcribing this chunk.
            chunk_sequence: The sequence number of the chunk.
            chunk_duration_offset: Accumulated duration of previous chunks
                (for global timestamp offset).

        Returns:
            The segments that were actually added (after deduplication).
        """
        added: List[TranscriptSegment] = []

        for seg in new_segments:
            # Adjust timestamps to global offset
            adjusted = _adjust_timestamps(seg, chunk_duration_offset)

            # Check for duplicates against existing segments
            is_dup = False
            for existing in self.segments:
                if is_duplicate(adjusted, existing):
                    self.total_duplicate_segments_suppressed += 1
                    is_dup = True
                    break

            if not is_dup:
                self.segments.append(adjusted)
                added.append(adjusted)

        # Update metadata
        self.chunk_count += 1
        self.full_text = " ".join(s.text for s in self.segments)
        self.updated_at = datetime.now(timezone.utc).isoformat()

        return added

    def get_full_text(self) -> str:
        """Return the assembled full text."""
        return self.full_text

    def get_segments_in_order(self) -> List[TranscriptSegment]:
        """Return segments sorted by timestamp (if available) then sequence."""
        return sorted(
            self.segments,
            key=lambda s: (
                s.start_time if s.start_time is not None else float('inf'),
                s.segment_id,
            ),
        )

    def to_dict(self) -> Dict:
        return {
            "transcript_id": self.transcript_id,
            "incident_id": self.incident_id,
            "segment_count": self.segment_count,
            "chunk_count": self.chunk_count,
            "total_duplicates_suppressed": self.total_duplicate_segments_suppressed,
            "full_text": self.full_text,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _adjust_timestamps(
    segment: TranscriptSegment,
    time_offset: float,
) -> TranscriptSegment:
    """Create a new segment with timestamps adjusted by the chunk offset.

    Preserves all other fields. If the segment has no timestamps,
    returns it unchanged.
    """
    if segment.start_time is None and segment.end_time is None:
        return segment

    new_start = (segment.start_time + time_offset) if segment.start_time is not None else None
    new_end = (segment.end_time + time_offset) if segment.end_time is not None else None

    return TranscriptSegment(
        segment_id=segment.segment_id,
        text=segment.text,
        start_time=round(new_start, 3) if new_start is not None else None,
        end_time=round(new_end, 3) if new_end is not None else None,
        speaker=segment.speaker,
        speaker_attribution_method=segment.speaker_attribution_method,
        speaker_epistemic_status=segment.speaker_epistemic_status,
        source_provider=segment.source_provider,
        created_at=segment.created_at,
        metadata=segment.metadata,
    )
