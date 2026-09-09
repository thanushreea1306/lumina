# LUMINA ML — Pilot Dataset Plan

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Feasibility study infrastructure for determining whether the LUMINA behavioral ML problem is learnable.
**Status:** INFRASTRUCTURE COMPLETE — AWAITING DATA SOURCES

---

## Executive Summary

This plan defines a small, legitimate, high-quality pilot dataset (~500–1,500 real conversation segments) to empirically determine whether LUMINA's 11-tactic segment-level behavioral classification problem is learnable **before** committing to a large annotation budget.

**This is NOT production training.** The pilot is for:
- Feasibility assessment
- Label quality validation
- Taxonomy validation
- Baseline measurement
- Error analysis
- Data sizing estimation

---

## 1. Pilot Dataset Strategy

### Target Size
- **500–1,500 real conversation segments** (justified by annotation design below)
- From **50–150 real two-party conversations**
- Minimum **30 conversations per tactic** for statistical validity

### Why This Size
- Enough to expose obvious overfitting in a baseline model
- Enough to measure per-label precision/recall for common tactics
- Not so large that annotation cost becomes prohibitive for a feasibility study
- Enough to validate taxonomy boundaries (hard cases)

### What the Pilot Must Contain

| Requirement | Rationale |
|-------------|-----------|
| Real two-party conversations | Must reflect genuine behavioral dynamics |
| English language | LUMINA's target language |
| Caller/scammer side | Tactics originate here |
| Recipient/victim side | Resistance, compliance, confusion |
| Benign conversational examples | Baseline negative class |
| Resistance examples | USER_RESISTANCE label |
| Safety/advice examples | ADVICE_OR_WARNING label |
| Multiple scam patterns | Avoid overfitting to single scam type |
| Speaker attribution | Distinguish caller vs. recipient |

### What the Pilot Must NOT Contain
- ❌ Synthetic conversations
- ❌ LLM-generated conversations
- ❌ Scam-baiting as substitute for victim behavior
- ❌ Fabricated labels
- ❌ Fabricated metrics

---

## 2. Legitimate Data Sources — Investigation Results

### Source Evaluation Matrix

| # | Source | Type | Size | License | Two-Party | Speaker Attribution | Behavioral Relevance | Verdict |
|---|--------|------|------|---------|-----------|--------------------|--------------------|---------|
| S1 | FTC/PPoNE Robocall Audio | Real robocalls | 1,432 | Public Domain | ❌ One-sided | ❌ No | Caller-side tactics only | **AUXILIARY** |
| S2 | Kaggle: YouTube Scam Transcripts | Scam baiting | 243 | CC0 | ⚠️ Scam baiting | ❌ No | Scammer tactics yes; victim behavior simulated | **CONDITIONAL** |
| S3 | Kaggle: Call Transcripts | Real conversations | 60 | Unknown | ✅ Yes | ❌ No | Mixed | **CONDITIONAL** |
| S4 | TeleAntiFraud-28k | Audio+Text | 28,511 | Open-source (unverified) | ✅ Yes (TTS) | ⚠️ TTS channels | Partial (60% synthetic) | **NEEDS REVIEW** |
| S5 | LDC Switchboard-1 | Phone conversations | 2,400 | LDC License | ✅ Yes | ✅ Speaker codes | Not scam (general) | **BASELINE ONLY** |
| S6 | LUMINA opt-in recordings | User-consented | 0 (future) | Custom consent | ✅ Yes | ✅ Yes | Direct match | **RECOMMENDED (future)** |
| S7 | Derakhshan et al. | Simulated scam | 215 | Not specified | ⚠️ Simulated | ❌ No | Simulated scenarios | **EXCLUDED** |

### Strongest Candidate Sources

**For Pilot (Immediate):**
1. **S2 (Kaggle YouTube Scam Transcripts, CC0)** — 243 transcripts, two-party (scammer + scam-baiter), CC0 license. Limitation: scam-baiter behavior ≠ real victim behavior. Useful for caller-side tactics.
2. **S3 (Kaggle Call Transcripts)** — 60 calls, real conversations, unknown license. Small but real.
3. **S1 (FTC/PPoNE)** — Caller-side scam language, public domain. Useful for auxiliary/domain adaptation.

**For Production (Future):**
4. **S6 (LUMINA opt-in recordings)** — Only source that provides genuine two-party conversations with proper consent and licensing.

### Licensing Summary

| Source | License | Commercial Use | Training Use | Production Use | Redistribution |
|--------|---------|----------------|--------------|----------------|----------------|
| FTC/PPoNE | Public Domain | ✅ YES | ✅ YES | ✅ YES | ✅ YES |
| Kaggle YouTube | CC0 | ✅ YES | ✅ YES | ✅ YES | ✅ YES |
| Kaggle Call Transcripts | Unknown | ⚠️ Unverified | ⚠️ Unverified | ⚠️ Unverified | ⚠️ Unverified |
| TeleAntiFraud-28k | Open-source | ⚠️ Unverified | ⚠️ Unverified | ⚠️ Unverified | ⚠️ Unverified |
| LDC Switchboard | LDC License | ❌ Research-only | ❌ Research-only | ❌ No | ❌ No |

---

## 3. Pilot Dataset Design

### Schema

Every segment in the pilot dataset must conform to:

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

### Speaker Labels

| Label | Definition |
|-------|------------|
| `CALLER` | The party initiating the call (scammer, telemarketer, etc.) |
| `RECIPIENT` | The party receiving the call (victim, target, etc.) |
| `UNKNOWN` | Speaker identity cannot be determined |

**Rules:**
- Do not infer speaker identity from unsupported assumptions
- If diarization is unavailable, annotate manually where authorized or mark UNKNOWN
- Do not fabricate diarization

### Conversation Phases

| Phase | Description |
|-------|-------------|
| `SETUP` | Initial contact, identity establishment |
| `PRESSURE` | Applying authority, threats, urgency |
| `EXTRACTION` | Requesting credentials, money, access |
| `RESISTANCE` | Recipient pushing back |
| `ESCALATION` | Increasing pressure after resistance |
| `UNKNOWN` | Phase cannot be determined |

---

## 4. Consent-Based Pilot Collection Protocol

### Overview

If real scam calls are unavailable from existing datasets, LUMINA can design a consent-based collection protocol for participants who already possess recordings they are willing to share.

**Critical:** This does NOT mean recording unsuspecting people. Participants must explicitly agree before any data is collected.

### Consent Requirements

| Consent Type | Description | Required |
|-------------|-------------|----------|
| **Participant Consent** | Informed, voluntary agreement to participate | ✅ YES |
| **Recording Consent** | Agreement that the conversation may be recorded/stored | ✅ YES |
| **Transcription Consent** | Agreement that the conversation may be transcribed | ✅ YES |
| **ML Training Consent** | Agreement that data may be used for ML model training | ✅ YES |
| **Production-Use Consent** | Agreement that data may be used in production systems | ✅ YES (if applicable) |
| **Redistribution Consent** | Agreement that data may be redistributed | Optional |

### Privacy Controls

| Control | Description |
|---------|-------------|
| **Anonymization** | Remove or mask all PII before storage |
| **Secure Storage** | Encrypted at rest, access-controlled |
| **Access Control** | Only authorized personnel can access raw data |
| **Retention Period** | Define and enforce data retention limits |
| **Withdrawal Mechanism** | Participants can request data deletion |
| **Deletion Mechanism** | Verify deletion from all backups |
| **Sensitive Information Handling** | Special handling for credentials, financial data |

### Data Collection Flow

```
Participant agrees to consent form
    ↓
Participant provides recording (file upload or API)
    ↓
PII detection and redaction
    ↓
Transcription (if audio)
    ↓
Speaker diarization (if available)
    ↓
Expert annotation with LUMINA taxonomy
    ↓
Quality control and adjudication
    ↓
Dataset assembly with provenance
    ↓
Health checks and validation
```

### Legal Requirements

- **One-party consent states:** Federal law (18 U.S.C. § 2511) permits recording if one party consents
- **All-party consent states:** Some states require all parties to consent
- **International:** Varies by jurisdiction
- **Recommendation:** Only use recordings where the participant has legal right to share them

---

## 5. Annotation Methodology

### Annotation Process

1. **Segmentation:** Split conversations into utterance-level segments
2. **Speaker Attribution:** Label each segment with speaker role
3. **Tactic Annotation:** Multi-label annotation with LUMINA's 11 labels
4. **Phase Annotation:** Label conversation phase
5. **Quality Review:** Expert review of all annotations
6. **Adjudication:** Resolve disagreements

### Multi-Label Rules

- A segment can have **0 labels** (benign, no tactics detected)
- A segment can have **1 label** (single tactic)
- A segment can have **multiple labels** (tactics co-occur)
- Do NOT force a label when evidence is absent
- `UNKNOWN` must remain possible when annotator is uncertain

### Annotation Quality Metrics

| Metric | Target | Minimum |
|--------|--------|---------|
| Annotators per segment | 2+ | 1 (pilot minimum) |
| Inter-annotator agreement (Cohen's κ) | > 0.7 | > 0.5 |
| Per-label agreement | > 0.7 | > 0.5 |
| Disagreement rate | < 20% | < 30% |
| Adjudication rate | < 15% | < 25% |

### Gold Set

Create a small expert-reviewed gold set (~50-100 segments) containing:
- Clear positive examples of each tactic
- Clear negative examples (benign)
- Difficult boundary cases:
  - Authority vs. ordinary identification
  - Urgency vs. normal deadline
  - Threat vs. warning
  - Credential request vs. harmless verification
  - Financial request vs. legitimate payment
  - Isolation vs. ordinary privacy advice
  - User resistance vs. uncertainty
  - Advice/warning vs. scammer instruction

---

## 6. Data Splitting

### Conversation-Level Split

**NEVER split individual segments from the same conversation across train/val/test.**

Algorithm:
1. Group segments by `conversation_id`
2. Deterministically shuffle conversation IDs (seed=42)
3. Assign conversations to splits:
   - 80% train
   - 10% validation
   - 10% test
4. Verify no conversation appears in multiple splits

### Group-Aware Splitting

If multiple recordings come from the same campaign/source/person:
- Group at that level too
- Prevent campaign-level leakage

### Split Documentation

Record:
- Random seed
- Split algorithm
- Conversation counts per split
- Segment counts per split
- Verification that no leakage exists

---

## 7. Baseline Model

### TF-IDF + Logistic Regression

Before any Transformer model, implement a legitimate baseline:

**Requirements:**
- Multi-label classification (OneVsRest or classifier chains)
- Class weighting where justified
- Same train/validation/test splits as future models
- Metrics: macro F1, micro F1, per-label precision/recall/F1
- Multilabel exact-match accuracy
- Confusion/error analysis

**Metrics must come ONLY from actual pilot data.**

If insufficient data exists:
```
BASELINE_STATUS = INSUFFICIENT_DATA
```

Do not fabricate metrics.

---

## 8. DeBERTa Gate

DeBERTa training becomes eligible ONLY if ALL of the following are true:

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Pilot data is legitimate (verified provenance) | ❓ PENDING |
| 2 | Labels are sufficiently represented (>50 per class) | ❓ PENDING |
| 3 | Privacy checks pass (no PII in training data) | ❓ PENDING |
| 4 | Train/val/test split is frozen and verified | ❓ PENDING |
| 5 | No leakage exists between splits | ❓ PENDING |
| 6 | Baseline can be evaluated | ❓ PENDING |
| 7 | Annotation quality is acceptable (κ > 0.5) | ❓ PENDING |
| 8 | Each critical tactic has enough positive examples | ❓ PENDING |
| 9 | Dataset diversity is sufficient | ❓ PENDING |

Otherwise:
```
DEBERTA_STATUS = NO_GO
```

---

## 9. Label Coverage Analysis

### Required Report Format

| Tactic | Total Segments | Positive Segments | Negative Segments | Percentage | Caller Positives | Recipient Positives | Conversations with Label | Annotation Agreement | Status |
|--------|---------------|-------------------|-------------------|------------|-----------------|--------------------|-----------------------|--------------------|--------|

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

**If any tactic has fewer than the minimum, the pilot is INSUFFICIENT_DATA for that tactic.**

---

## 10. Dataset Health Checks

### Validators Required

| Check | Description | Fail Action |
|-------|-------------|-------------|
| Missing required fields | All required fields present | REJECT segment |
| Duplicate segments | No exact text duplicates | REMOVE duplicate |
| Overlapping timestamps | No time overlaps within conversation | FLAG for review |
| Invalid speaker labels | Only CALLER/RECIPIENT/UNKNOWN | REJECT segment |
| Invalid tactic labels | Only valid LUMINA labels | REJECT segment |
| Invalid provenance | Source and license present | REJECT segment |
| Missing license | License field populated | REJECT segment |
| Missing consent | Consent status present | REJECT segment |
| PII detection | No PII in training text | REDACT or REJECT |
| Secrets detection | No secrets in training text | REDACT or REJECT |
| Train/test leakage | No conversation overlap | FAIL pipeline |
| Conversation leakage | No campaign overlap | FAIL pipeline |
| Duplicate text across splits | No text duplication | FAIL pipeline |
| Impossible timestamps | start < end, reasonable values | FLAG for review |
| Empty transcripts | No empty text fields | REJECT segment |
| Malformed annotations | Valid JSON, correct types | REJECT segment |

**Dataset must fail closed.** If a check cannot be verified, the dataset is rejected.

---

## 11. Privacy Sanitization

### Redaction Required

| Pattern | Redaction |
|---------|-----------|
| OTP codes | `[OTP_REDACTED]` |
| PINs | `[PIN_REDACTED]` |
| Passwords | `[PASSWORD_REDACTED]` |
| Card numbers | `[CARD_REDACTED]` |
| Bank account numbers | `[ACCOUNT_REDACTED]` |
| Authentication codes | `[AUTH_CODE_REDACTED]` |
| Identity document numbers | `[ID_DOC_REDACTED]` |
| Secret answers | `[SECRET_REDACTED]` |
| Phone numbers | `[PHONE_REDACTED]` |
| Email addresses | `[EMAIL_REDACTED]` |
| Names (where required) | `[NAME_REDACTED]` |
| Addresses (where required) | `[ADDRESS_REDACTED]` |

### Rules
- Do not over-redact ordinary words
- Keep reversible/raw-data separation if legally necessary
- Training exports must be sanitized
- Operational LUMINA incident data MUST remain separate
- Do NOT use production user incidents without explicit separate training consent

---

## 12. Dataset Versioning

### Version Format: `pilot-v{MAJOR}.{MINOR}`

Example: `pilot-v0.1`

### Required Artifacts

| Artifact | Description |
|----------|-------------|
| `dataset_manifest.json` | Provenance, statistics, versioning |
| `train.jsonl` | Training split |
| `val.jsonl` | Validation split |
| `test.jsonl` | Test split |
| `checksums.json` | SHA-256 checksums for all files |
| `changelog.md` | Version history |
| `acceptance_report.md` | Health check results |
| `annotation_guide.md` | Annotation methodology |
| `split_manifest.json` | Split algorithm and verification |

### Rules
- No private/raw recordings committed to Git
- Only processed, sanitized data in version control
- Checksums verified before any training

---

## 13. FTC Data Role

### DO NOT Mix FTC Data Blindly

FTC data is maintained as a **separate dataset/domain source**:

```
FTC_ROBOCALL_AUXILIARY
```

### Allowed Uses
- STT robustness testing
- Telephony audio robustness
- Scam-language vocabulary expansion
- Caller-side tactic auxiliary analysis
- External evaluation of caller-side detection

### Prohibited Uses
- ❌ Primary training dataset for Task B
- ❌ Victim-side behavioral labels (not present in data)
- ❌ USER_RESISTANCE training (zero examples)
- ❌ ADVICE_OR_WARNING training (zero examples)
- ❌ BENIGN_CONVERSATION training (zero examples)

---

## 14. Model Architecture Decision

### Based on Actual Pilot Results

| Model | When to Use | When NOT to Use |
|-------|-------------|-----------------|
| TF-IDF + LR | Quick baseline, interpretability | Insufficient for complex patterns |
| Sentence embeddings + linear | Good semantics, fast inference | Limited fine-grained classification |
| DistilBERT | Balance of speed and quality | If latency is critical |
| DeBERTa-v3-base | Best NLU, multi-label capable | If data insufficient or latency critical |
| ModernBERT | New architecture, efficient | If less proven in production |
| Deterministic-only | If ML adds no value over rules | If ML improves over rules |

**Select based on actual evidence. Do NOT automatically select DeBERTa.**

---

## 15. Implementation Files

### Documentation
- `docs/ml/PILOT_DATASET_PLAN.md` (this file)
- `docs/ml/PILOT_ANNOTATION_GUIDE.md`
- `docs/ml/PILOT_ACCEPTANCE.md`
- `docs/ml/PILOT_REPORT.md`

### Scripts
- `scripts/ml/validate_pilot_dataset.py`
- `scripts/ml/split_by_conversation.py`
- `scripts/ml/evaluate_baseline.py`

### Tests
- `tests/test_ml_pilot_dataset.py`

---

## 16. Success Criteria

### Pilot is SUCCESSFUL if:
1. Legitimate data sources identified and verified
2. At least 500 real two-party segments annotated
3. All 11 tactics have ≥10 positive examples
4. Baseline model can be trained and evaluated
5. Annotation quality meets minimum thresholds (κ > 0.5)
6. No data leakage detected
7. No PII in training data
8. Clear path to production training identified

### Pilot is INSUFFICIENT if:
1. Fewer than 500 segments available
2. Any critical tactic has <10 positive examples
3. Annotation quality below minimum thresholds
4. Data leakage detected
5. PII found in training data
6. No clear path to production training

---

## 17. Hard Stop Compliance

**This plan stops at infrastructure design. No actions taken:**
- ❌ No datasets downloaded
- ❌ No data collected
- ❌ No DeBERTa trained
- ❌ No synthetic data generated
- ❌ No LLM examples generated
- ❌ No labels fabricated
- ❌ No metrics fabricated
- ❌ No model checkpoints created

**The purpose is to establish a scientifically defensible path from:**

```
LEGITIMATE REAL DATA
    → ANNOTATION
    → PILOT DATASET
    → BASELINE
    → EVIDENCE-BASED MODEL SELECTION
    → FUTURE REAL TRAINING
```
