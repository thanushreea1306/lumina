# LUMINA ML — Real Pilot Acceptance Gate

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Acceptance criteria for real pilot dataset before any model training.
**Status:** DEFINED — Ready for evaluation

---

## Overview

The real pilot dataset must pass ALL acceptance criteria before any model training can proceed. If any criterion fails, the dataset is rejected.

**Fail-closed:** If a check cannot be verified, the dataset is rejected.

---

## 1. Conversation-Level Acceptance

### A1: Consent Validity

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A1.1 | Consent record exists | Every participant has a consent record | consent_id lookup |
| A1.2 | All required permissions granted | participation, audio_recording, speech_to_text, behavioral_ml_annotation, ml_model_training, research_evaluation | Permission check |
| A1.3 | Consent obtained before recording | consent_timestamp < recording_timestamp | Timestamp comparison |
| A1.4 | Consent not withdrawn | deletion_status != WITHDRAWN | Status check |
| A1.5 | Age verified | age_confirmed_over_18 == true | Age check |
| A1.6 | Consent document hash valid | consent_document_hash matches current version | Hash verification |

### A2: Audio Provenance

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A2.1 | Recording source known | recording_source is valid enum | Field check |
| A2.2 | Not synthetic | recording_source != SYNTHETIC | Exclusion check |
| A2.3 | Not roleplay (for real pool) | recording_source != CONTROLLED_ROLEPLAY | Exclusion check |
| A2.4 | Provenance verified | provenance_verified == true | Verification check |
| A2.5 | Recording timestamp valid | recording_timestamp is valid ISO 8601 | Timestamp check |

### A3: Two-Party Structure

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A3.1 | Speaker structure | speaker_structure == TWO_PARTY | Field check |
| A3.2 | ≥2 participants | len(participant_ids) ≥ 2 | Count check |
| A3.3 | ≥2 consents | len(consent_ids) ≥ 2 | Count check |
| A3.4 | Caller + recipient present | Both roles in transcript | Speaker analysis |

### A4: Language

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A4.1 | English | language == "en" | Field check |

### A5: Privacy

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A5.1 | PII check passed | No unresolved PII issues | PII scan |
| A5.2 | Secrets redacted | No secrets in training data | Secret scan |
| A5.3 | Sanitization complete | sanitization_status == "SANITIZED" | Status check |

### A6: Conversation Quality

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| A6.1 | Usable transcript | Transcript exists and non-empty | Transcript check |
| A6.2 | Conversation boundary | Start and end identifiable | Timestamp check |
| A6.3 | Duration reasonable | 10s ≤ duration ≤ 600s | Duration check |
| A6.4 | Speaker attribution | ≥80% segments have speaker labels | Attribution check |

---

## 2. Segment-Level Acceptance

### B1: Parent Conversation

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| B1.1 | Conversation passes | Parent conversation in candidate pool | Lookup check |

### B2: Annotation

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| B2.1 | Human annotation exists | annotation record present | Record check |
| B2.2 | Evidence span exists | evidence_span non-empty per label | Field check |
| B2.3 | Annotation version known | annotation_version present | Field check |
| B2.4 | Valid labels | All labels in LUMINA_LABELS | Label validation |

### B3: Privacy

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| B3.1 | PII check passed | No PII in segment text | PII scan |
| B3.2 | Sanitization complete | sanitization_status == "SANITIZED" | Status check |

### B4: Split

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| B4.1 | Split assigned | train/val/test assigned | Split check |
| B4.2 | Not withdrawn | deletion_status == ACTIVE | Status check |

---

## 3. Dataset-Level Acceptance

### C1: Scale

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| C1.1 | Minimum conversations | ≥50 real two-party conversations | Count |
| C1.2 | Minimum segments | ≥500 annotated segments | Count |
| C1.3 | Recommended conversations | ≥100 | Count |
| C1.4 | Recommended segments | ≥1,500 | Count |

### C2: Label Coverage

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| C2.1 | All 11 tactics represented | Each tactic has ≥1 label | Label distribution |
| C2.2 | Minimum per tactic | Each tactic has ≥10 positive segments | Per-label count |
| C2.3 | BENIGN coverage | ≥50 BENIGN_CONVERSATION segments | Label count |
| C2.4 | Multi-label support | Some segments have ≥2 labels | Multi-label analysis |
| C2.5 | No class collapse | No single label >80% of all labels | Imbalance check |

### C3: Annotation Quality

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| C3.1 | Double-annotated subset | ≥20% of segments double-annotated | Annotation records |
| C3.2 | Inter-annotator agreement | Cohen's κ > 0.5 | Agreement calculation |
| C3.3 | Disagreement rate | <30% | Disagreement calculation |
| C3.4 | Adjudication complete | All disagreements resolved | Adjudication records |

### C4: Data Split

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| C4.1 | Conversation-level split | No conversation in multiple splits | Split verification |
| C4.2 | Split ratios | ~80/10/10 train/val/test | Split counts |
| C4.3 | No text leakage | No duplicate text across splits | Text dedup check |
| C4.4 | Deterministic split | Seed documented, reproducible | Split manifest |
| C4.5 | Minimum test size | ≥10 conversations in test | Test count |

### C5: Privacy

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| C5.1 | No PII in training data | Zero PII detections | PII scan |
| C5.2 | No secrets in training data | Zero secret detections | Secret scan |

### C6: Dataset Integrity

| # | Criterion | Requirement | Verification |
|---|-----------|-------------|--------------|
| C6.1 | No duplicate segments | Zero exact text duplicates | Dedup check |
| C6.2 | No empty transcripts | Zero empty text fields | Null check |
| C6.3 | No invalid labels | All labels in LUMINA taxonomy | Label validation |
| C6.4 | No invalid speakers | All speakers in {CALLER, RECIPIENT, UNKNOWN} | Speaker validation |
| C6.5 | Valid JSON/JSONL format | All files parse correctly | Format validation |

---

## 4. Acceptance Report Template

```markdown
# Real Pilot Dataset Acceptance Report

**Dataset Version:** pilot-v0.1
**Evaluation Date:** YYYY-MM-DD
**Evaluator:** [Name]

## Summary
- Total Criteria: 40
- Passed: [N]
- Failed: [N]
- Result: ACCEPTED / REJECTED

## Failed Criteria
[List any failed criteria with details]

## Statistics
- Total Conversations: [N]
- Real Two-Party: [N]
- Total Segments: [N]
- Annotated Segments: [N]
- Label Distribution: [dict]
- Class Imbalance Ratio: [float]
- Inter-Annotator κ: [float]
- PII Detections: [N]

## Recommendation
[Go / No-Go for baseline training]
```

---

## 5. Fail-Closed Rules

The dataset is REJECTED if:
1. Any criterion in A1 (Consent) fails
2. Any criterion in A2 (Provenance) fails
3. Any criterion in A3 (Two-Party) fails
4. Any criterion in A5 (Privacy) fails
5. Fewer than 500 segments available
6. Any tactic has fewer than 10 positive examples
7. Inter-annotator κ < 0.3 (unreliable annotations)

The dataset is CONDITIONAL if:
1. Scale criteria (C1) are below recommended but above minimum
2. Annotation quality (C3) is below target but above minimum
3. Some rare tactics have fewer than recommended examples

---

## 6. Training Gate

Passing acceptance does NOT automatically enable model training.

Additional training requirements:
1. ≥500 segments (minimum scale)
2. ≥50 positive examples per common tactic
3. ≥20 positive examples per rare tactic
4. Inter-annotator κ > 0.7 (good agreement)
5. Baseline macro F1 > 0.3 (problem is learnable)
6. No severe class imbalance (min ratio > 0.05)

If baseline macro F1 ≤ 0.3, the problem may not be learnable with current data.
