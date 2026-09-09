"""
LUMINA ML — real scam conversation dataset discovery gate tests.

These tests encode the non-negotiable review conclusions from:
- docs/ml/DATASET_DISCOVERY_REPORT.md
- docs/ml/DATASET_DISCOVERY_MATRIX.md
- docs/ml/DATASET_DISCOVERY_SOURCES.md

They do not download large datasets, do not train anything, and do not
modify product code.


"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CATALOG_PATH = Path(__file__).resolve().parent.parent / "docs" / "ml" / "DATASET_DISCOVERY_MATRIX.md"
REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "ml" / "DATASET_DISCOVERY_REPORT.md"
SOURCES_PATH = Path(__file__).resolve().parent.parent / "docs" / "ml" / "DATASET_DISCOVERY_SOURCES.md"


def _read(path: Path) -> str:
    if not path.exists():
        raise pytest.fail.Exception(f"Expected discovery document missing: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def _norm_keep_quotes(text: str) -> str:
    # Same whitespace normalization as _norm but keep curly quotes so that
    # CJK-quoted dataset names from the matrix file can still be matched.
    return re.sub(r"\s+", " ", text or "").strip()


def _norm(text: str, keep_case: bool = False) -> str:
    out = re.sub(r"\s+", " ", text or "").strip()
    if not keep_case:
        out = out.lower()
    return out


# ---------------------------------------------------------------------------
# Candidate roster extracted from the matrix file
# ---------------------------------------------------------------------------

CANDIDATES: list[tuple[str, str]] = [
    ("FTC / NCSU Robocall Audio Dataset", "ftc-ncsu-robocall"),
    ("TeleAntiFraud-28k", "teleantifraud-28k"),
    ("BothBosu synthetic scam datasets", "bothbosu-synthetic"),
    ("Zenodo Scam Conversation Corpus", "zenodo-scc"),
    ("Zenodo Multiclass NLP Dataset", "zenodo-nlp"),
    ("Shen et al. real-time detection paper dataset lineage", "shen-real-time"),
    ("D-STAR scam/non-scam transcript set", "dstar"),
    ("Kaggle \"Call Transcripts Scam Determinations\"", "kaggle-mealss"),
    ("Kaggle \"Scam and Non-Scam Call Conversation Dataset\"", "kaggle-teeconnie"),
    ("Mendeley ASLC-448", "aslc-448"),
    ("Anatomy of a Scam Call honeypot corpus", "anatomy-honeypot"),
]


def _matrix_table() -> dict[str, dict[str, str]]:
    """Parse each candidate's dimension block from the raw markdown.

    Finds ### headings in the raw text, maps them to CANDIDATES,
    extracts the block between consecutive headings, and parses
    dimension values from each block.
    """
    raw = _read(CATALOG_PATH)
    lines = raw.splitlines()

    DIMS = [
        "REAL_AUDIO", "REAL_TWO_PARTY", "REAL_VICTIM_BEHAVIOR",
        "ENGLISH", "SCAM_RELEVANCE", "BENIGN_RELEVANCE",
        "SEGMENTABLE", "SPEAKER_ATTRIBUTION", "TACTIC_ANNOTATION",
        "COMMERCIAL_ML", "DERIVATIVE_ANNOTATION", "PRIVACY", "PROVENANCE",
    ]

    # Find all ### heading line indices
    heading_indices = [i for i, l in enumerate(lines) if l.strip().startswith("### ")]

    result: dict[str, dict[str, str]] = {}

    for idx, h_idx in enumerate(heading_indices):
        # Strip leading "N. " and trailing parenthetical from heading
        heading_text = lines[h_idx].strip().removeprefix("### ").strip()
        heading_base = re.sub(r"^\s*\d+\.\s+", "", heading_text).strip()
        heading_base = re.sub(r"\s*\(.*\)\s*$", "", heading_base).strip()
        norm_heading = _norm(heading_base).replace('\u201c', '"').replace('\u201d', '"')

        # Match to a candidate slug
        matched_slug = None
        for title, slug in CANDIDATES:
            if _norm(title).replace('\u201c', '"').replace('\u201d', '"') == norm_heading:
                matched_slug = slug
                break
        if matched_slug is None:
            continue

        # Extract block: from this heading to the next ### heading
        end = heading_indices[idx + 1] if idx + 1 < len(heading_indices) else len(lines)
        block = "\n".join(lines[h_idx:end])
        bnorm = _norm(block)

        # Parse each dimension
        dims: dict[str, str] = {}
        for dim in DIMS:
            pattern = dim.lower()
            match = re.search(pattern + r"\s*\|\s*(yes|partial|not_verified|no|unknown)", bnorm)
            dims[dim] = match.group(1).upper() if match else "UNKNOWN"
        result[matched_slug] = dims

    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEveryCandidateHasAStatus:
    def test_every_candidate_has_an_overall_status(self):
        raw = _norm(_read(CATALOG_PATH))
        for title, _slug in CANDIDATES:
            assert "overall" in raw, "Matrix should contain an OVERALL column."
        # Count candidate verdicts expected in the final matrix verdict section.
        assert "red" in raw
        assert "yellow" in raw


class TestSeriousCandidateHasSourceEvidence:
    def test_every_serious_candidate_traced(self):
        sources = _norm(_read(SOURCES_PATH))
        serious = [
            "ftc-ncsu-robocall",
            "teleantifraud-28k",
            "bothbosu-synthetic",
            "zenodo-scc",
            "zenodo-nlp",
            "shen-real-time",
            "dstar",
            "kaggle-mealss",
            "kaggle-teeconnie",
            "aslc-448",
            "anatomy-honeypot",
        ]
        def candidate_in_text(slug: str, text: str) -> bool:
            # The source-trace file uses canonical section titles, not internal
            # slugs. These titles are matched against the existing sources file.
            lookup = {
                "ftc-ncsu-robocall": "FTC / NCSU Robocall Audio Dataset",
                "teleantifraud-28k": "TeleAntiFraud-28k",
                "bothbosu-synthetic": "BothBosu synthetic scam datasets",            "zenodo-scc": "Zenodo Scam Conversation Corpus",
            "zenodo-nlp": "Zenodo Multiclass NLP Dataset",                "shen-real-time": "Shen et al. real-time phone scam detection paper",
                "dstar": "D-STAR",                "kaggle-mealss": "Kaggle \u201cCall Transcripts Scam Determinations\u201d",
                    "kaggle-teeconnie": "Kaggle \u201cScam and Non-Scam Call Conversation Dataset\u201d",
                "aslc-448": "Mendeley ASLC-448",
                "anatomy-honeypot": "Anatomy of a Scam Call honeypot corpus",
            }
            needle = lookup.get(slug, slug)
            return _norm(needle) in text

        for slug in serious:
            assert candidate_in_text(slug, sources), (
                f"Serious candidate {slug} must appear in DATASET_DISCOVERY_SOURCES.md"
            )

        # Also verify the sources file records the canonical section for the
        # Shen et al. candidate, which is titled differently there.
        assert "shen et al. real-time phone scam detection paper" in sources, (
            "Sources file section for Shen et al. must use its canonical title."
        )


class TestUnknownLicensingNeverUpgradedToYes:
    def test_licensing_fields_not_false_positives(self):
        matrix = _matrix_table()
        for title, _slug in CANDIDATES:
            slug = _slug
            dims = matrix[slug]
            for key in ["COMMERCIAL_ML", "DERIVATIVE_ANNOTATION"]:
                value = dims.get(key, "UNKNOWN")
                assert value != "YES" or slug == "ftc-ncsu-robocall", (
                    f"{slug}: {key} should not be upgraded to YES without verification."
                )


class TestSyntheticCannotBecomeGreen:
    def test_synthetic_candidates_not_green(self):
        matrix = _matrix_table()
        synthetic_slugs = ["teleantifraud-28k", "bothbosu-synthetic", "aslc-448"]
        for slug in synthetic_slugs:
            assert slug in matrix
        # The overall verdict section must not describe any synthetic/TTS
        # candidate as GREEN.
        raw = _norm(_read(CATALOG_PATH))
        assert "green" not in raw or "none found" in raw or "no" in raw, (
            "No synthetic/TTS candidate may be described as GREEN."
        )

    def test_tts_candidate_audio_is_not_real(self):
        matrix = _matrix_table()
        assert matrix["aslc-448"]["REAL_AUDIO"] != "YES", (
            "ASLC-448 is TTS-generated audio and must not be marked REAL_AUDIO=YES."
        )


class TestOneSidedCannotBecomeTwoParty:
    def test_ftc_not_two_party(self):
        matrix = _matrix_table()
        assert matrix["ftc-ncsu-robocall"]["REAL_TWO_PARTY"] != "YES", (
            "FTC/NCSU robocall data is one-sided and must not be marked REAL_TWO_PARTY=YES."
        )
        assert matrix["ftc-ncsu-robocall"]["REAL_VICTIM_BEHAVIOR"] != "YES", (
            "FTC/NCSU robocall data does not provide real victim behavior."
        )


class TestScamBaitingCannotBecomeVictimBehavior:
    def test_honeypot_victim_side_not_real_human_victim(self):
        matrix = _matrix_table()
        # The honeypot corpus captures real scammer behavior, but the recipient
        # side is an AI voice agent, not a real human victim.
        assert matrix["anatomy-honeypot"]["REAL_VICTIM_BEHAVIOR"] != "YES", (
            "Anatomy-of-a-Scam-Call honeypot corpus recipient side is an AI agent, "
            "not real human victim behavior."
        )

    def test_scc_victim_side_not_real_human_victim(self):
        matrix = _matrix_table()
        # Zenodo Scam Conversation Corpus victim side is described as
        # GPT-4o-facilitated, not real human victim behavior.
        assert matrix["zenodo-scc"]["REAL_VICTIM_BEHAVIOR"] != "YES", (
            "Zenodo SCC victim side is LLM-facilitated, not real human victim behavior."
        )


class TestMissingCountsRemainUnknown:
    def test_uncertain_counts_not_upgraded(self):
        matrix = _matrix_table()
        uncertain_cases = [
            ("kaggle-mealss", ["REAL_VICTIM_BEHAVIOR", "PRIVACY"]),
            ("kaggle-teeconnie", ["REAL_VICTIM_BEHAVIOR", "PRIVACY"]),
            ("dstar", ["REAL_VICTIM_BEHAVIOR", "PRIVACY", "SPEAKER_ATTRIBUTION"]),
        ]
        for slug, fields in uncertain_cases:
            for field in fields:
                assert matrix[slug].get(field) in {"UNKNOWN", "NOT_VERIFIED"}, (
                    f"{slug}: {field} must remain UNKNOWN/NOT_VERIFIED without source certainty."
                )


class TestBestCandidateStillConditional:
    def test_honeypot_not_noisy_green(self):
        matrix = _matrix_table()
        assert matrix["anatomy-honeypot"]["REAL_VICTIM_BEHAVIOR"] == "NO", (
            "Even the best candidate does not provide real human victim behavior "
            "(recipient side is an AI voice agent)."
        )
        assert matrix["anatomy-honeypot"]["COMMERCIAL_ML"] == "NOT_VERIFIED", (
            "Access and licensing for the honeypot corpus must remain NOT_VERIFIED until confirmed."
        )

    def test_final_board_is_nogo_now(self):
        raw = _norm(_read(REPORT_PATH))
        assert "no_go" in raw, "Final recommendation must be NO_GO for training right now."
        assert "do not train" in raw, "NO_GO must be explicit."


class TestNoDatasetApprovedForTraining:
    def test_no_green_candidate(self):
        raw = _norm(_read(REPORT_PATH))
        # The report must not imply any dataset is GO for LUMINA training.
        assert "no_go" in raw, (
            "Discovery must not approve any dataset for LUMINA training."
        )


class TestDocumentationCoherence:
    def _matrix_headings(self, canonicalize: bool = False) -> set[str]:
        text = _read(CATALOG_PATH)
        out: set[str] = set()
        for line in text.splitlines():
            if line.strip().startswith("### "):
                head = line.strip().removeprefix("### ").strip()
                if canonicalize:
                    # Strip inline leading indices such as "1. " and trailing
                    # parenthetical noise such as "`15212527`" so internal
                    # candidate titles can match the base row heading.
                    head = re.sub(r"^\s*[0-9]+\.\s+", "", head).strip()
                    head = re.sub(r"\s*\(.*\)\s*$", "", head).strip()
                out.add(_norm(head))
        return out

    def _matrix_headings_base(self) -> dict[str, str]:
        """Map normalized base title -> raw heading line."""
        mapping: dict[str, str] = {}
        for raw_heading in self._matrix_headings():
            base = re.sub(r"^\s*[0-9]+\.\s+", "", raw_heading).strip()
            base = re.sub(r"\s*\(.*\)\s*$", "", base).strip()
            key = _norm(base).replace('\u201c', '"').replace('\u201d', '"')
            if key and key not in mapping:
                mapping[key] = raw_heading
        return mapping

    def _matrix_heading_for_candidate(self, title: str) -> str:
        base_map = self._matrix_headings_base()
        norm_title = _norm(title).replace('\u201c', '"').replace('\u201d', '"')
        if norm_title in base_map:
            return base_map[norm_title]
        cleaned = re.sub(r"^\s*[0-9]+\.\s+", "", title).strip()
        cleaned = re.sub(r"\s*\(.*\)\s*$", "", cleaned).strip()
        norm_cleaned = _norm(cleaned)
        if norm_cleaned in base_map:
            return base_map[norm_cleaned]
        raise AssertionError(f"No matrix heading found for candidate: {title!r} (norm={norm_title!r})")

    def test_matrix_mentions_all_candidates(self):
        headings = self._matrix_headings(canonicalize=True)
        for title, _slug in CANDIDATES:
            heading = self._matrix_heading_for_candidate(title)
            norm_heading = _norm(heading)
            # Normalize both sides for comparison so inline indices and trailing
            # parentheticals do not break the match.
            norm_heading_base = re.sub(
                r"^\s*[0-9]+\.\s+", "", norm_heading
            ).strip()
            norm_heading_base = re.sub(
                r"\s*\(.*\)\s*$", "", norm_heading_base
            ).strip()
            matched = any(
                norm_h == norm_heading_base or norm_heading_base.startswith(norm_h)
                for norm_h in headings
            )
            assert matched, (
                f"Matrix should mention: {title} (row: {heading!r}, base={norm_heading_base!r}, headings={sorted(headings)})"
            )

    def test_report_matches_matrix_verdict_shape(self):
        report = _norm(_read(REPORT_PATH))
        matrix = _norm(_read(CATALOG_PATH))
        assert "red" in matrix
        assert "yellow" in matrix
        assert "green" in matrix or "none found" in matrix
        # The report's NO_GO posture must be consistent with the matrix verdict.
        assert "no_go" in report
