# LUMINA ML — Pilot Dataset Infrastructure Report

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Final report on pilot dataset infrastructure completion.
**Status:** INFRASTRUCTURE COMPLETE — AWAITING DATA SOURCES

---

## 1. Legitimate Pilot Sources Found

| # | Source | Type | Size | License | Two-Party | Verdict |
|---|--------|------|------|---------|-----------|---------|
| S1 | FTC/PPoNE Robocall Audio | Real robocalls | 1,432 | Public Domain | ❌ One-sided | **AUXILIARY** |
| S2 | Kaggle: YouTube Scam Transcripts | Scam baiting | 243 | CC0 | ⚠️ Scam baiting | **CONDITIONAL** |
| S3 | Kaggle: Call Transcripts | Real conversations | 60 | Unknown | ✅ Yes | **CONDITIONAL** |
| S4 | TeleAntiFraud-28k | Audio+Text | 28,511 | Open-source (unverified) | ✅ Yes (TTS) | **NEEDS REVIEW** |
| S5 | LDC Switchboard-1 | Phone conversations | 2,400 | LDC License | ✅ Yes | **BASELINE ONLY** |
| S6 | LUMINA opt-in recordings | User-consented | 0 (future) | Custom consent | ✅ Yes | **RECOMMENDED (future)** |

---

## 2. Strongest Candidate Source

**For Immediate Pilot:**
- **S2 (Kaggle YouTube Scam Transcripts, CC0)** — 243 transcripts, two-party (scammer + scam-baiter), CC0 license. Limitation: scam-baiter behavior ≠ real victim behavior. Useful for caller-side tactics.

**For Production (Future):**
- **S6 (LUMINA opt-in recordings)** — Only source that provides genuine two-party conversations with proper consent and licensing.

---

## 3. Licensing/Consent Status

| Source | License | Commercial Use | Training Use | Production Use |
|--------|---------|----------------|--------------|----------------|
| FTC/PPoNE | Public Domain | ✅ YES | ✅ YES | ✅ YES |
| Kaggle YouTube | CC0 | ✅ YES | ✅ YES | ✅ YES |
| Kaggle Call Transcripts | Unknown | ⚠️ Unverified | ⚠️ Unverified | ⚠️ Unverified |
| TeleAntiFraud-28k | Open-source | ⚠️ Unverified | ⚠️ Unverified | ⚠️ Unverified |
| LDC Switchboard | LDC License | ❌ Research-only | ❌ Research-only | ❌ No |

---

## 4. Actual Data Availability

**Status: NO COMPLETE TWO-PARTY BEHAVIORAL DATASET EXISTS**

The fundamental problem remains:
- No publicly available dataset contains real two-party scam conversations with segment-level behavioral tactic annotations and production-use licensing.
- The closest candidate (TeleAntiFraud-28k) is ~60% synthetic/LLM-generated and uses conversation-level labels, not segment-level.
- The FTC dataset is one-sided (caller only) and lacks victim speech.
- Scam-baiting datasets have simulated victim behavior, not genuine victim responses.

---

## 5. Pilot Dataset Design

### Schema
```json
{
  "segment_id": "string (unique)",
  "conversation_id": "string (groups segments)",
  "start_time": "float (seconds, nullable)",
  "end_time": "float (seconds, nullable)",
  "speaker": "CALLER | RECIPIENT | UNKNOWN",
  "text": "string (transcript text)",
  "tactic_labels": ["string (subset of LUMINA_LABELS)"],
  "conversation_phase": "SETUP | PRESSURE | EXTRACTION | RESISTANCE | ESCALATION | UNKNOWN",
  "provenance": {
    "source": "string",
    "license": "string",
    "consent_status": "VERIFIED | ASSUMED_PUBLIC_DOMAIN | UNKNOWN"
  },
  "annotation_status": "ANNOTATED | PENDING | ADJUDICATED",
  "annotator_ids": ["string"],
  "annotation_timestamp": "ISO 8601"
}
```

### Target Size
- 500–1,500 real conversation segments
- From 50–150 real two-party conversations
- Minimum 30 conversations per tactic for statistical validity

---

## 6. Annotation Methodology

### Process
1. Segmentation: Split conversations into utterance-level segments
2. Speaker Attribution: Label each segment with speaker role
3. Tactic Annotation: Multi-label annotation with LUMINA's 11 labels
4. Phase Annotation: Label conversation phase
5. Quality Review: Expert review of all annotations
6. Adjudication: Resolve disagreements

### Quality Targets
- Cohen's κ > 0.7 (good agreement)
- Percentage agreement > 80%
- Disagreement rate < 20%

---

## 7. Privacy Controls

### Redaction Required
- OTP codes → `[OTP_REDACTED]`
- PINs → `[PIN_REDACTED]`
- Passwords → `[PASSWORD_REDACTED]`
- Card numbers → `[CARD_REDACTED]`
- Phone numbers → `[PHONE_REDACTED]`
- Email addresses → `[EMAIL_REDACTED]`

### Rules
- Do not over-redact ordinary words
- Training exports must be sanitized
- Operational LUMINA incident data MUST remain separate
- Do NOT use production user incidents without explicit separate training consent

---

## 8. Label Coverage (Expected)

### Minimum Thresholds for Pilot Feasibility

| Tactic | Minimum Positive Segments | Minimum Conversations |
|--------|--------------------------|----------------------|
| AUTHORITY_CLAIM | 30 | 15 |
| THREAT_PRESENTATION | 30 | 15 |
| TIME_PRESSURE | 30 | 15 |
| ISOLATION_TACTIC | 15 | 10 |
| CREDENTIAL_REQUEST | 20 | 10 |
| FINANCIAL_REQUEST | 20 | 10 |
| REMOTE_ACCESS_REQUEST | 10 | 5 |
| IDENTITY_REQUEST | 15 | 10 |
| BENIGN_CONVERSATION | 50 | 25 |
| USER_RESISTANCE | 30 | 15 |
| ADVICE_OR_WARNING | 15 | 10 |

---

## 9. Baseline Plan

### TF-IDF + Logistic Regression
- Multi-label classification (OneVsRest)
- Class weighting where justified
- Same train/validation/test splits
- Metrics: macro F1, micro F1, per-label precision/recall/F1

### Decision Threshold
- Macro F1 > 0.3 → Problem appears learnable → Consider DeBERTa
- Macro F1 0.1–0.3 → Problem may be learnable with more data
- Macro F1 < 0.1 → Problem may not be learnable with current data

---

## 10. DeBERTa Gate

DeBERTa training becomes eligible ONLY if ALL of the following are true:

| # | Criterion | Current Status |
|---|-----------|----------------|
| 1 | Pilot data is legitimate | ❌ No data yet |
| 2 | Labels sufficiently represented (>50 per class) | ❌ No data yet |
| 3 | Privacy checks pass | ❌ No data yet |
| 4 | Train/val/test split frozen | ❌ No data yet |
| 5 | No leakage exists | ❌ No data yet |
| 6 | Baseline can be evaluated | ❌ No data yet |
| 7 | Annotation quality acceptable (κ > 0.5) | ❌ No data yet |
| 8 | Each critical tactic has enough examples | ❌ No data yet |
| 9 | Dataset diversity sufficient | ❌ No data yet |

**DEBERTA_STATUS = NO_GO**

---

## 11. Implementation Completed

### Documentation
- ✅ `docs/ml/PILOT_DATASET_PLAN.md` — Comprehensive pilot dataset strategy
- ✅ `docs/ml/PILOT_ANNOTATION_GUIDE.md` — Annotation methodology
- ✅ `docs/ml/PILOT_ACCEPTANCE.md` — Acceptance criteria (35 criteria)

### Scripts
- ✅ `scripts/ml/validate_pilot_dataset.py` — Dataset validation with health checks
- ✅ `scripts/ml/split_by_conversation.py` — Conversation-level splitting
- ✅ `scripts/ml/evaluate_baseline.py` — TF-IDF + LR baseline evaluation

### Tests
- ✅ `tests/test_ml_pilot_dataset.py` — 22 tests, all passing

### Pre-existing Infrastructure (Already Built)
- ✅ `scripts/ml/prepare_dataset.py` — Dataset preparation pipeline
- ✅ `scripts/ml/validate_dataset.py` — Dataset validation
- ✅ `scripts/ml/validate_provenance.py` — Provenance validation
- ✅ `app/incident/ml_intelligence.py` — ML model abstraction and evaluation harness

---

## 12. Tests

```
tests/test_ml_pilot_dataset.py — 22 passed

TestPilotValidation (5 tests)
  ✓ test_validation_imports
  ✓ test_empty_dataset_rejected
  ✓ test_valid_dataset_accepted
  ✓ test_pii_detection
  ✓ test_label_coverage_check

TestConversationSplit (4 tests)
  ✓ test_split_imports
  ✓ test_no_leakage
  ✓ test_deterministic_split
  ✓ test_split_ratios

TestBaselineEvaluation (4 tests)
  ✓ test_baseline_imports
  ✓ test_insufficient_data_returns_status
  ✓ test_baseline_produces_metrics
  ✓ test_per_class_metrics_structure

TestDataContract (4 tests)
  ✓ test_segment_schema
  ✓ test_speaker_values
  ✓ test_tactic_labels_are_lists
  ✓ test_provenance_structure

TestAcceptanceCriteria (3 tests)
  ✓ test_acceptance_document_exists
  ✓ test_annotation_guide_exists
  ✓ test_pilot_plan_exists

TestTacticTaxonomy (2 tests)
  ✓ test_all_11_labels_defined
  ✓ test_unknown_excluded_from_training
```

---

## 13. TRAINING_STATUS

```
╔══════════════════════════════════════════════════════════════╗
║                    TRAINING STATUS                          ║
║                                                              ║
║                    ███  NO_GO  ███                           ║
║                                                              ║
║  Pilot Infrastructure:  ✅ COMPLETE                          ║
║  Pilot Data:            ❌ NOT YET OBTAINED                  ║
║  Baseline:              ❌ NOT YET TRAINED                   ║
║  DeBERTa Gate:          ❌ NO_GO                             ║
║                                                              ║
║  Infrastructure Status:                                     ║
║    ✅ Pilot dataset plan                                     ║
║    ✅ Annotation guide                                       ║
║    ✅ Acceptance criteria                                    ║
║    ✅ Validation scripts                                     ║
║    ✅ Splitting scripts                                      ║
║    ✅ Baseline evaluation script                             ║
║    ✅ Health check tests (22/22 passing)                     ║
║    ✅ Consent-based collection protocol                      ║
║                                                              ║
║  What Exists:                                               ║
║    - Complete infrastructure for pilot dataset               ║
║    - Validation, splitting, and evaluation pipelines         ║
║    - Acceptance criteria with 35 checks                      ║
║    - Annotation guide with 11 tactic definitions             ║
║    - Consent-based collection protocol design                ║
║                                                              ║
║  What Does NOT Exist:                                       ║
║    - Any real two-party scam conversation data               ║
║    - Any annotated segments                                  ║
║    - Any trained model (baseline or DeBERTa)                 ║
║    - Any metrics from real data                              ║
║                                                              ║
║  Deterministic Safety Engine: REMAINS SOLE AUTHORITY         ║
║  ML Training: BLOCKED                                        ║
║  No synthetic data. No LLM examples. No fabricated labels.   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 14. NEXT_REQUIRED_ACTION

**The single blocking action required before any model training:**

### Obtain Legitimate Two-Party Scam Conversation Data

**Option A: License Existing Data**
1. Verify TeleAntiFraud-28k license for production use
2. If license permits, extract two-party conversation subsets
3. Apply LUMINA annotation protocol

**Option B: Consent-Based Collection**
1. Design and deploy LUMINA opt-in recording program
2. Collect real scam call recordings from willing participants
3. Obtain explicit consent for ML training and production use
4. Transcribe and annotate with LUMINA taxonomy

**Option C: Academic Partnership**
1. Partner with researchers who have access to legitimate scam call recordings
2. Negotiate licensing for production use
3. Annotate with LUMINA taxonomy

**Option D: Government/Law Enforcement**
1. Request access to FCC/FTC enforcement action recordings
2. Verify training rights
3. Annotate with LUMINA taxonomy

### Minimum Requirements for Data
- Real two-party conversations (NOT one-sided, NOT simulated)
- English language
- Speaker attribution (CALLER vs RECIPIENT)
- Production-use licensing
- ≥500 segments from ≥50 conversations

### Estimated Timeline
- Option A: 2-4 weeks (if license verified)
- Option B: 3-6 months (consent program setup + collection)
- Option C: 1-3 months (partnership negotiation)
- Option D: 2-6 months (government request process)

---

## 15. Hard Stop Compliance

**This report stops at infrastructure completion. No actions taken:**
- ❌ No datasets downloaded
- ❌ No data collected
- ❌ No DeBERTa trained
- ❌ No synthetic data generated
- ❌ No LLM examples generated
- ❌ No labels fabricated
- ❌ No metrics fabricated
- ❌ No model checkpoints created

**The infrastructure is ready. The data is not.**

**The path forward is clear:**

```
LEGITIMATE REAL DATA (when obtained)
    → ANNOTATION (using pilot annotation guide)
    → PILOT DATASET (validated by acceptance criteria)
    → BASELINE (TF-IDF + LR)
    → EVIDENCE-BASED MODEL SELECTION
    → FUTURE REAL TRAINING (if learnable)
```

**Nothing beyond that.**
