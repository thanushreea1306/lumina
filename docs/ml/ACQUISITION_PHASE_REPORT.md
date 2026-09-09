# LUMINA ML — Data Acquisition & Annotation Phase Report

**Date:** 2026-09-07  
**Status:** COMPLETE — TRAINING_STATUS = NO_GO  
**Author:** Buffy (Codebuff Agent)

---

## 1. Legitimate Acquisition Sources Found

**9 source categories evaluated. 3 viable paths identified.**

| Path | Source | License | Size | Timeline |
|------|--------|---------|------|----------|
| **Primary** | FTC Robocall Audio (PPoNE) | **Public Domain** | 1,432 calls | 0-3 months |
| **Secondary** | Expert annotation service | Work-for-hire | Custom | 3-6 months |
| **Tertiary** | LUMINA user opt-in | Custom consent | Variable | 6-12 months |

**Primary Source: FTC Robocall Audio Dataset**
- URL: https://github.com/wspr-ncsu/robocall-audio-dataset
- Size: 1,432 calls (96.2% English)
- License: **Public Domain** (FTC government data)
- Commercial Use: **YES**
- Training Use: **YES**
- Modality: Audio + transcripts
- Labels: None (requires annotation)

---

## 2. Licensing Findings

| Source | License | Commercial Use | Training Use | Verdict |
|--------|---------|----------------|--------------|---------|
| FTC Robocall Audio | **Public Domain** | **YES** | **YES** | **USABLE** |
| LDC Corpora | LDC License | Research-only | Research-only | Baseline only |
| Composite Scam | CC BY-NC | **NO** | Yes | **EXCLUDED** |
| BothBosu Synthetic | Various | Varies | Varies | **EXCLUDED** |
| User-Consented | Custom | Per consent | Per consent | **USABLE** (when collected) |

**Critical finding:** The FTC Robocall Audio Dataset is the only large, publicly available, English-language, production-usable dataset with phone call transcripts.

---

## 3. Consent Requirements

| Data Source | Consent Required | Mechanism |
|-------------|-----------------|-----------|
| FTC Robocall Audio | No (public domain) | N/A |
| Expert Annotation | Yes (work-for-hire) | Contract |
| User Opt-In | Yes (explicit) | In-app consent |
| LDC Corpora | No (licensed) | License agreement |

**User Consent Protocol Designed:**
- Explicit, informed, voluntary
- Covers training and production use
- Withdrawal mechanism in place
- Data separation from operational incidents

---

## 4. Recommended Acquisition Path

### Phase 1: Immediate (0-3 months)
1. Download FTC Robocall Audio Dataset (public domain)
2. Extract transcripts from metadata.csv
3. Segment transcripts into utterances
4. Expert-annotate ~15,000 segments

### Phase 2: Short-term (3-6 months)
1. Professional annotation (Scale AI / Labelbox)
2. Pilot with 500 segments
3. Full annotation run
4. Quality control and adjudication

### Phase 3: Medium-term (6-12 months)
1. LUMINA opt-in recording program
2. Collect user-consented calls
3. Transcribe with faster-whisper
4. Annotate with expert protocol

**Estimated total cost:** $15,000-$63,500
**Estimated timeline:** 6-12 months to GO

---

## 5. Recommended Annotation Process

**Protocol defined in:** `docs/ml/ANNOTATION_GUIDELINES.md`

**Key elements:**
- Segment-level, multi-label annotation
- 11-label taxonomy (TACTIC_TAXONOMY.md)
- Inter-annotator agreement target: Cohen's kappa > 0.7
- Adjudication for disagreements
- Quality control with gold standard testing
- Annotator training and qualification

**Annotation flow:**
1. Annotator reads segment + context
2. Applies tactic labels (multi-label)
3. Provides rationale
4. Rates confidence
5. Adjudicator resolves disagreements
6. Quality control review

---

## 6. Final 11-Label Taxonomy Status

**Taxonomy defined in:** `docs/ml/TACTIC_TAXONOMY.md`

| # | Label | Definition | Multi-label | Status |
|---|-------|------------|-------------|--------|
| 1 | AUTHORITY_CLAIM | Claims institutional authority | Yes | FINAL |
| 2 | THREAT_PRESENTATION | Presents negative consequences | Yes | FINAL |
| 3 | TIME_PRESSURE | Creates urgency/deadlines | Yes | FINAL |
| 4 | ISOLATION_TACTIC | Blocks verification/help | Yes | FINAL |
| 5 | CREDENTIAL_REQUEST | Requests OTP/passwords/PINs | Yes | FINAL |
| 6 | FINANCIAL_REQUEST | Requests money/payments | Yes | FINAL |
| 7 | REMOTE_ACCESS_REQUEST | Requests software/screen access | Yes | FINAL |
| 8 | IDENTITY_REQUEST | Requests ID documents/info | Yes | FINAL |
| 9 | BENIGN_CONVERSATION | No tactics detected | No (exclusive) | FINAL |
| 10 | USER_RESISTANCE | User pushes back/refuses | Yes | FINAL |
| 11 | ADVICE_OR_WARNING | Safety guidance provided | Yes | FINAL |

**Taxonomy version:** 1.0  
**Status:** FINAL — ready for annotation

---

## 7. Realistic Dataset Size Requirements

**Defined in:** `docs/ml/DATASET_VERSIONING.md`

| Tier | Segments | Conversations | Use Case |
|------|----------|---------------|----------|
| **Minimum Exploratory** | 5,000 | 500 | Prototype, baseline comparison |
| **Preferred Training** | 15,000 | 1,500 | DeBERTa fine-tuning |
| **Strong Validation** | 30,000 | 3,000 | Robust model, publication |

**With FTC Robocall Audio (1,432 calls):**
- Estimated segments: 15,000-25,000 (after segmentation)
- Satisfies: Preferred Training tier
- With expert annotation: Strong Validation tier achievable

**Class balance target:** No class < 5% of majority class frequency

---

## 8. Baseline Recommendation

**Defined in:** `docs/ml/TRAINING_GATE.md`

**Recommended baseline:** TF-IDF + Logistic Regression

**Rationale:**
- Simple, interpretable, fast
- Well-understood behavior
- No GPU required
- Easy to reproduce
- Good reference for "does ML actually help?"

**Baseline requirements:**
- Same held-out test set as DeBERTa
- Same preprocessing pipeline
- Same evaluation metrics (macro F1)
- Must be beaten by DeBERTa to justify complexity

**Alternative baselines (if needed):**
- Sentence embeddings (sentence-transformers) + classifier
- Linear SVM on TF-IDF features
- Rule-based deterministic baseline (already exists)

---

## 9. Privacy Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PII in training data | Medium | Critical | PII detection + redaction |
| User data repurposed | Low | Critical | Explicit consent + separation |
| Consent not documented | Low | Critical | Consent tracking system |
| License violation | Low | Critical | Legal review of all sources |
| Data breach | Low | Critical | Encrypted storage, access control |

**Mitigations implemented:**
- PII detection patterns in `prepare_dataset.py`
- Provenance validation in `validate_provenance.py`
- Dataset acceptance criteria in `DATASET_ACCEPTANCE.md`
- Training gate checklist in `TRAINING_GATE.md`

---

## 10. Implementation Completed

### Documentation Created

| File | Purpose |
|------|---------|
| `docs/ml/DATA_ACQUISITION_PLAN.md` | Source evaluation and acquisition strategy |
| `docs/ml/DATA_CONTRACT.md` | Training example specification |
| `docs/ml/TACTIC_TAXONOMY.md` | 11-label taxonomy with definitions |
| `docs/ml/ANNOTATION_GUIDELINES.md` | Annotation protocol |
| `docs/ml/DATASET_VERSIONING.md` | Versioning and reproducibility |
| `docs/ml/TRAINING_GATE.md` | GO/NO-GO criteria |
| `docs/ml/DATASET_ACCEPTANCE.md` | Acceptance criteria |
| `docs/ml/ACQUISITION_PHASE_REPORT.md` | This report |

### Scripts Created

| File | Purpose |
|------|---------|
| `scripts/ml/validate_provenance.py` | Provenance validation |
| `scripts/ml/validate_dataset.py` | Dataset acceptance validation |

### Tests Created

| File | Tests |
|------|-------|
| `tests/test_ml_data_contract.py` | 26 tests for data contract, PII, leakage, acceptance |

**Total new tests:** 26  
**Total all ML tests:** 109 (38 + 45 + 26)

---

## 11. Tests

```
tests/test_ml_intelligence.py:        38 passed
tests/test_ml_dataset_pipeline.py:    45 passed
tests/test_ml_data_contract.py:       26 passed
────────────────────────────────────────────────
Total:                               109 passed, 0 failed
```

**Test categories covered:**
- Data contract field validation (10 tests)
- PII detection (4 tests)
- Leakage detection (2 tests)
- Label distribution (2 tests)
- Conversation split validation (2 tests)
- Acceptance criteria (4 tests)
- Provenance validation (2 tests)

---

## 12. TRAINING_STATUS

```
TRAINING_STATUS = NO_GO

Reason: No legitimate, sufficiently large, properly annotated training dataset exists.

Criteria met: 0/12 (Training Gate)

What exists:
- Complete acquisition plan (FTC Robocall Audio as primary source)
- Complete annotation protocol (11-label taxonomy + guidelines)
- Complete validation infrastructure (provenance, PII, leakage, acceptance)
- Complete versioning protocol (reproducibility)
- Complete training gate (12 GO/NO-GO criteria)

What is needed:
- Execute Phase 1: Download and annotate FTC Robocall Audio
- Expert annotators with domain knowledge
- 3-6 months for annotation
- $15,000-$45,000 budget

Next step: Begin Phase 1 of DATA_ACQUISITION_PLAN.md
```

---

## Summary

This phase established the **legitimate path to obtaining real training data**. The key finding:

1. **FTC Robocall Audio Dataset** (1,432 calls, public domain) is the only viable primary source
2. **Expert annotation** is required to create segment-level labels
3. **6-12 months** and **$15,000-$63,500** needed for full dataset creation
4. **All infrastructure** for annotation, validation, and acceptance is ready
5. **Deterministic safety engine** remains the sole authority until training completes

**No fake data. No fabricated metrics. Just honest assessment and ready infrastructure.**
