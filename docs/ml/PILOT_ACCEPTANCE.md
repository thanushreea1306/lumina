# LUMINA ML — Pilot Dataset Acceptance Criteria

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Acceptance criteria for the pilot dataset before any baseline training.
**Status:** DEFINED — Ready for evaluation

---

## Overview

The pilot dataset must pass ALL acceptance criteria before any model training (including baseline) can proceed. If any criterion fails, the dataset is rejected and the pilot is INSUFFICIENT.

---

## Acceptance Criteria

### A1: Data Legitimacy

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A1.1 | Provenance documented | Every segment has a source | Provenance manifest |
| A1.2 | License verified | Every source has a verified license | License field in manifest |
| A1.3 | Commercial use permitted | All sources allow commercial use | License check |
| A1.4 | Training use permitted | All sources allow ML training | License check |
| A1.5 | No synthetic data | Zero LLM-generated or synthetic segments | Source verification |
| A1.6 | No fabricated labels | All labels from human annotators | Annotator records |

### A2: Two-Party Conversations

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A2.1 | Both speakers present | CALLER and RECIPIENT in dataset | Speaker label analysis |
| A2.2 | Speaker attribution | ≥80% of segments have speaker labels | Speaker label coverage |
| A2.3 | Genuine conversations | Not simulated or scam-baiting | Source verification |

### A3: Scale

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A3.1 | Minimum segments | ≥500 segments | Count |
| A3.2 | Minimum conversations | ≥50 conversations | Count |
| A3.3 | Recommended segments | ≥1,000 segments | Count |
| A3.4 | Recommended conversations | ≥100 conversations | Count |

### A4: Label Coverage

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A4.1 | All 11 tactics represented | Each tactic has ≥1 label | Label distribution |
| A4.2 | Minimum per tactic | Each tactic has ≥10 positive segments | Per-label count |
| A4.3 | BENIGN representation | ≥50 BENIGN_CONVERSATION segments | Label count |
| A4.4 | Multi-label support | Some segments have ≥2 labels | Multi-label analysis |
| A4.5 | No class collapse | No single label >80% of all labels | Imbalance check |

### A5: Annotation Quality

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A5.1 | Double-annotated subset | ≥20% of segments double-annotated | Annotation records |
| A5.2 | Inter-annotator agreement | Cohen's κ > 0.5 | Agreement calculation |
| A5.3 | Disagreement rate | <30% | Disagreement calculation |
| A5.4 | Adjudication complete | All disagreements resolved | Adjudication records |
| A5.5 | Gold set validated | Gold set passes quality checks | Gold set evaluation |

### A6: Data Split

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A6.1 | Conversation-level split | No conversation in multiple splits | Split verification |
| A6.2 | Split ratios | ~80/10/10 train/val/test | Split counts |
| A6.3 | No text leakage | No duplicate text across splits | Text dedup check |
| A6.4 | Deterministic split | Seed documented, reproducible | Split manifest |
| A6.5 | Minimum test size | ≥10 conversations in test | Test count |

### A7: Privacy

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A7.1 | No PII in training data | Zero PII detections | PII scan |
| A7.2 | No secrets in training data | Zero secret detections | Secret scan |
| A7.3 | Phone numbers redacted | All phone numbers replaced | Redaction check |
| A7.4 | Email addresses redacted | All emails replaced | Redaction check |
| A7.5 | Credentials redacted | All OTPs, PINs, passwords replaced | Redaction check |

### A8: Dataset Integrity

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A8.1 | No duplicate segments | Zero exact text duplicates | Dedup check |
| A8.2 | No empty transcripts | Zero empty text fields | Null check |
| A8.3 | No invalid labels | All labels in LUMINA taxonomy | Label validation |
| A8.4 | No invalid speakers | All speakers in {CALLER, RECIPIENT, UNKNOWN} | Speaker validation |
| A8.5 | No overlapping timestamps | No time overlaps within conversation | Timestamp check |
| A8.6 | Valid JSON/JSONL format | All files parse correctly | Format validation |
| A8.7 | Checksums match | All checksums verified | Checksum verification |

### A9: Minimum Baseline Trainability

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A9.1 | Baseline can train | TF-IDF + LR runs without error | Training run |
| A9.2 | Baseline can predict | Predictions produced for all test segments | Prediction check |
| A9.3 | Metrics calculable | Precision/recall/F1 computed | Metric calculation |
| A9.4 | Not all-same predictions | Baseline does not predict single class for all | Prediction diversity |

---

## Acceptance Report Template

```markdown
# Pilot Dataset Acceptance Report

**Dataset Version:** pilot-v0.1
**Evaluation Date:** YYYY-MM-DD
**Evaluator:** [Name]

## Summary
- Total Criteria: 35
- Passed: [N]
- Failed: [N]
- Result: ACCEPTED / REJECTED

## Failed Criteria
[List any failed criteria with details]

## Statistics
- Total Segments: [N]
- Total Conversations: [N]
- Label Distribution: [dict]
- Class Imbalance Ratio: [float]
- Inter-Annotator κ: [float]
- PII Detections: [N]
- Duplicate Segments: [N]

## Recommendation
[Go / No-Go for baseline training]
```

---

## Fail-Closed Rules

The dataset is REJECTED if:
1. Any criterion in A1 (Legitimacy) fails
2. Any criterion in A7 (Privacy) fails
3. Any criterion in A8 (Integrity) fails
4. Fewer than 500 segments available
5. Any tactic has fewer than 10 positive examples
6. Inter-annotator κ < 0.3 (unreliable annotations)

The dataset is CONDITIONAL if:
1. Scale criteria (A3) are below recommended but above minimum
2. Annotation quality (A5) is below target but above minimum
3. Some rare tactics have fewer than recommended examples

---

## DeBERTa Gate (Separate from Pilot Acceptance)

Passing pilot acceptance does NOT automatically enable DeBERTa training.

Additional DeBERTa requirements:
1. ≥1,000 segments (recommended scale)
2. ≥50 positive examples per common tactic
3. ≥20 positive examples per rare tactic
4. Inter-annotator κ > 0.7 (good agreement)
5. Baseline macro F1 > 0.3 (problem is learnable)
6. No severe class imbalance (min ratio > 0.05)

If baseline macro F1 ≤ 0.3, the problem may not be learnable with current data, and DeBERTa training is NO-GO regardless of other criteria.
