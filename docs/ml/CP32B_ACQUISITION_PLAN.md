# LUMINA ML — CP-32B Acquisition Plan

**Document Version:** 1.0  
**Created:** 2026-09-08  
**Purpose:** Define the acquisition pipeline for when a legitimate dataset is identified  
**Status:** Plan only — no acquisition authorized

---

## Current Status

**Decision:** NO_GO  
**Reason:** No currently available candidate satisfies the minimum requirements

This document defines what WOULD be done if a legitimate candidate passes the hard gates.

---

## Acquisition Pipeline Design

### Step 1: Legal/Privacy Gate

Before any data acquisition:

1. **License Verification**
   - Confirm dataset license allows commercial ML training
   - Confirm audio/transcript/annotation licenses are compatible
   - Confirm no redistribution restrictions that conflict with deployment
   - Document all license terms in `LICENSE_MANIFEST.md`

2. **Privacy/Consent Verification**
   - Confirm proper consent was obtained from all participants
   - Confirm PII handling meets LUMINA's privacy standards
   - Confirm no re-identification risks
   - Confirm voice identity restrictions are respected
   - Document privacy terms in `PRIVACY_MANIFEST.md`

3. **DUA Requirements**
   - If a DUA is required, complete it before acquisition
   - Document DUA terms and restrictions
   - Confirm contractor access is permitted

### Step 2: Source Manifest

Create an immutable source manifest:

```yaml
dataset_name: "<name>"
version: "<version>"
source_url: "<url>"
checksum_sha256: "<hash>"
acquisition_date: "<date>"
license_file: "<path>"
privacy_file: "<path>"
```

### Step 3: Download/Acquisition

1. Download from authoritative source only
2. Verify checksum against source manifest
3. Store in `data/raw/<dataset_name>/`
4. Never commit raw data to Git

### Step 4: Privacy Filtering

1. **PII Detection/Removal**
   - Phone numbers (E.164 format)
   - Email addresses
   - Physical addresses
   - Financial account numbers
   - Social security numbers / Aadhaar / PAN
   - Names (where not essential for analysis)

2. **Speaker Handling**
   - Anonymize speaker identities
   - Remove voice-identifying metadata
   - Respect voice cloning restrictions

3. **Credential Removal**
   - OTPs / verification codes
   - Passwords
   - Card numbers
   - Bank account numbers

### Step 5: Transcript Validation

1. **Format Validation**
   - Verify transcript format matches expected schema
   - Check for encoding issues
   - Validate timestamp ordering

2. **Content Validation**
   - Verify speaker attribution is present
   - Check for segment boundaries
   - Validate language (English for LUMINA)

3. **Quality Checks**
   - Remove empty/corrupted segments
   - Flag low-confidence ASR transcripts
   - Validate segment length limits

### Step 6: Annotation Conversion

1. **Map to LUMINA Taxonomy**
   - Convert existing labels to 11-tactic taxonomy
   - Document mapping decisions
   - Flag ambiguous mappings

2. **Segment-Level Labels**
   - Ensure labels are at segment level, not conversation level
   - Document label granularity
   - Record annotation methodology

3. **Label Provenance**
   - Document who created labels
   - Document annotation training
   - Record inter-annotator agreement (if available)

### Step 7: Train/Validation/Test Split

1. **Split Strategy**
   - 70% train / 15% validation / 15% test
   - Stratified by tactic label
   - No data leakage between splits

2. **Leakage Prevention**
   - Ensure no speaker appears in multiple splits
   - Ensure no conversation spans multiple splits
   - Document split boundaries

3. **Class Balance Analysis**
   - Analyze tactic label distribution
   - Document class imbalance
   - Plan for balanced sampling if needed

### Step 8: Deduplication

1. **Exact Deduplication**
   - Remove exact duplicate segments
   - Document deduplication criteria

2. **Near-Deduplication**
   - Identify near-duplicate segments
   - Document near-duplication threshold

### Step 9: Evaluation Protocol

1. **Metrics**
   - Per-class precision, recall, F1
   - Macro F1
   - Confusion matrix
   - No fabricated metrics

2. **Evaluation Sets**
   - Use held-out test set for final evaluation
   - Use validation set for model selection
   - Document evaluation protocol

3. **Baseline Comparison**
   - Compare against deterministic baseline
   - Document improvement (if any)

---

## Data Storage

```
data/
├── raw/                    # Raw downloaded data (not committed)
│   └── <dataset_name>/
├── processed/              # Processed data (not committed)
│   └── <dataset_name>/
├── splits/                 # Train/val/test splits (not committed)
│   └── <dataset_name>/
└── manifests/              # Source/license/provenance manifests (committed)
    ├── SOURCE_MANIFEST.md
    ├── LICENSE_MANIFEST.md
    └── PRIVACY_MANIFEST.md
```

---

## What Is NOT Allowed

1. **No synthetic data** — Only real human conversations
2. **No fabricated labels** — Only verified annotations
3. **No fabricated metrics** — Only real evaluation results
4. **No training without approval** — Only after GO decision
5. **No commit of raw data** — Raw data stays out of Git
6. **No PII in logs** — Never log phone numbers, credentials, etc.

---

## Blockers for This Phase

Since the decision is NO_GO, this plan is not yet activated.

**Required before activation:**
1. A dataset must pass all critical gates
2. Legal/privacy verification must be complete
3. DUA must be signed (if required)
4. Explicit authorization to proceed must be received

---

## Status

**Plan created:** 2026-09-08  
**Plan status:** DORMANT (NO_GO decision)  
**Next review:** When a new candidate is identified
