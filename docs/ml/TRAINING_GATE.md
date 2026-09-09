# LUMINA ML — Training Gate

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** GO/NO-GO criteria that must be met before any model training.  
**Status:** FINAL

---

## Overview

Training is ALLOWED only when ALL 12 criteria below are satisfied. If ANY criterion is not met, training is PROHIBITED.

**Current Status:** NO-GO

---

## Training Gate Criteria

### 1. Legitimate Data Source Exists

**Requirement:** At least one data source with verified provenance and clear licensing.

**Verification:**
- [ ] Data source identified
- [ ] Source is legitimate (not synthetic, not LLM-generated)
- [ ] Source contains real phone conversations or transcripts
- [ ] Source is in English
- [ ] Source has sufficient volume (>1000 conversations)

**Evidence:** DATA_ACQUISITION_PLAN.md, DATA_PROVENANCE.md

**Status:** ❌ NOT MET

---

### 2. License/Consent Verified

**Requirement:** Explicit permission for commercial/production use.

**Verification:**
- [ ] License text reviewed by legal team
- [ ] Commercial use explicitly permitted
- [ ] Training use explicitly permitted
- [ ] Redistribution permitted (if needed)
- [ ] No conflicting restrictions

**Evidence:** LICENSE_RECORDS in dataset manifest

**Status:** ❌ NOT MET

---

### 3. Provenance Documented

**Requirement:** Complete provenance chain from source to training example.

**Verification:**
- [ ] Source URL/location documented
- [ ] Download date recorded
- [ ] Verification status confirmed
- [ ] Annotation date recorded
- [ ] Annotation version recorded

**Evidence:** Provenance records in dataset manifest

**Status:** ❌ NOT MET

---

### 4. Sufficient Segment-Level Labels Exist

**Requirement:** Minimum labeled segments for meaningful training.

**Verification:**
- [ ] Total segments ≥ 5,000 (minimum) or ≥ 15,000 (preferred)
- [ ] Each label class has ≥ 200 examples (minimum)
- [ ] Multi-label annotations are present
- [ ] Annotation quality verified

**Evidence:** Dataset manifest statistics

**Status:** ❌ NOT MET

---

### 5. Taxonomy Mapping is Complete

**Requirement:** All dataset labels map to LUMINA's 11-label taxonomy.

**Verification:**
- [ ] Label mapping defined (LABEL_MAPPING.md)
- [ ] All source labels have mapping targets
- [ ] Mapping reviewed and validated
- [ ] No unmapped labels remain

**Evidence:** LABEL_MAPPING.md, label distribution report

**Status:** ❌ NOT MET

---

### 6. Privacy Sanitization Passes

**Requirement:** All PII and secrets detected and redacted.

**Verification:**
- [ ] PII detection applied
- [ ] Phone numbers redacted
- [ ] Email addresses redacted
- [ ] SSN/ID numbers redacted
- [ ] Passwords/OTP redacted
- [ ] Spot-check confirms no PII remains

**Evidence:** PII filter logs, spot-check report

**Status:** ❌ NOT MET

---

### 7. Train/Validation/Test Split is Frozen

**Requirement:** Deterministic split with no leakage.

**Verification:**
- [ ] Split procedure documented
- [ ] Split seed recorded
- [ ] No conversation appears in multiple splits
- [ ] Split ratios are reasonable (80/10/10)
- [ ] Split manifest generated

**Evidence:** Split manifest, leakage check report

**Status:** ❌ NOT MET

---

### 8. No Leakage Detected

**Requirement:** No data leakage between splits.

**Verification:**
- [ ] Text deduplication across splits
- [ ] Conversation ID overlap check
- [ ] No near-duplicate text across splits
- [ ] Source overlap check

**Evidence:** Leakage detection report

**Status:** ❌ NOT MET

---

### 9. Annotation Quality is Acceptable

**Requirement:** Inter-annotator agreement meets threshold.

**Verification:**
- [ ] Cohen's kappa ≥ 0.7
- [ ] Gold standard accuracy ≥ 80%
- [ ] Adjudication completed for disagreements
- [ ] Rationales are substantive

**Evidence:** Agreement metrics, quality report

**Status:** ❌ NOT MET

---

### 10. Class Coverage is Acceptable

**Requirement:** All label classes have sufficient representation.

**Verification:**
- [ ] No class has < 5% of majority class frequency
- [ ] Class imbalance documented
- [ ] Mitigation strategy defined (if needed)
- [ ] Rare classes have ≥ 200 examples

**Evidence:** Label distribution report, class balance analysis

**Status:** ❌ NOT MET

---

### 11. Baseline Comparison is Defined

**Requirement:** A legitimate baseline model is defined.

**Verification:**
- [ ] Baseline model selected (e.g., TF-IDF + LR)
- [ ] Baseline training procedure documented
- [ ] Baseline evaluation metrics defined
- [ ] Same held-out test set used

**Evidence:** Baseline definition document

**Status:** ❌ NOT MET

---

### 12. Evaluation Protocol is Defined

**Requirement:** Clear evaluation metrics and procedure.

**Verification:**
- [ ] Primary metric defined (macro F1)
- [ ] Secondary metrics defined
- [ ] Evaluation procedure documented
- [ ] Acceptance threshold defined
- [ ] Failure criteria defined

**Evidence:** Evaluation protocol document

**Status:** ❌ NOT MET

---

## Gate Decision

### Current Status

```
TRAINING_STATUS = NO_GO

Criteria met: 0/12
```

### Decision Process

1. Review all 12 criteria
2. Verify evidence for each criterion
3. If ALL criteria met → TRAINING_STATUS = GO
4. If ANY criterion not met → TRAINING_STATUS = NO_GO
5. Document decision with evidence
6. Get approval from project lead

### Approval Requirements

Training requires:
- All 12 criteria met
- Documentation reviewed
- Legal review completed
- Project lead approval
- Ethics review (if applicable)

---

## Re-evaluation

This gate is re-evaluated:
- When new data is acquired
- When annotation is completed
- When licensing is verified
- When quality checks pass
- Before any training run

---

## Emergency Stop

Training can be halted at any time if:
- Data provenance is questioned
- License compliance is uncertain
- Privacy breach is detected
- Annotation quality degrades
- Safety concerns arise

**Emergency stop procedure:**
1. Stop training immediately
2. Preserve all artifacts
3. Investigate the issue
4. Document findings
5. Resume only when issue resolved
