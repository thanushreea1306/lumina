# LUMINA ML — Training Readiness Assessment

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Pre-training checklist — GO / NO-GO decision for DeBERTa-v3 training.  
**Status:** **NO-GO** — Training data does not exist.

---

## GO / NO-GO Decision

# ❌ NO-GO FOR TRAINING

**Reason:** No legitimate, sufficiently large, properly annotated training dataset exists.

**What would need to change:** A custom annotated dataset of ≥10,000 segment-level, multi-label social-engineering tactic annotations with production-use licensing must be created before training can proceed.

---

## Readiness Checklist

| # | Criterion | Required | Actual | Status |
|---|-----------|----------|--------|--------|
| 1 | Dataset exists | Yes | **No** | ❌ BLOCKER |
| 2 | Dataset is downloadable | Yes | N/A | ❌ BLOCKED |
| 3 | License permits training | Yes | N/A | ❌ BLOCKED |
| 4 | License permits production use | Yes | N/A | ❌ BLOCKED |
| 5 | Labels match LUMINA taxonomy | Yes | N/A | ❌ BLOCKED |
| 6 | Segment-level annotations | Yes | N/A | ❌ BLOCKED |
| 7 | Multi-label support | Yes | N/A | ❌ BLOCKED |
| 8 | Minimum 10,000 labeled segments | Yes | 0 | ❌ BLOCKER |
| 9 | Class balance > 10% minority | Yes | N/A | ❌ BLOCKED |
| 10 | Train/val/test split possible | Yes | N/A | ❌ BLOCKED |
| 11 | No data leakage | Yes | N/A | ❌ BLOCKED |
| 12 | PII filtering applied | Yes | N/A | ❌ BLOCKED |
| 13 | Deterministic preprocessing | Yes | ✅ Built | ✅ |
| 14 | Provenance tracking | Yes | ✅ Built | ✅ |
| 15 | Model architecture defined | Yes | ✅ Built | ✅ |
| 16 | Training pipeline ready | Yes | ⚠️ Partial | ⚠️ |
| 17 | Compute requirements known | Yes | ✅ Defined | ✅ |
| 18 | Deployment constraints defined | Yes | ✅ Defined | ✅ |

**Score: 4/18 criteria met (22%)**

---

## Detailed Assessment

### 1. Dataset Size

**Required:** ≥10,000 labeled segments (50,000+ preferred for deep learning)  
**Available:** 0 labeled segments  
**Gap:** Complete — no dataset exists

For context:
- Derakhshan et al.: 215 calls (simulated, binary labels)
- Kaggle Composite: 46,982 transcripts (CC BY-NC — cannot use)
- Combined all public data: ~518 conversations (binary labels)

None of these provide segment-level multi-label annotations.

### 2. Label Coverage

**Required:** 11 TacticLabel classes with segment-level multi-label annotations  
**Available:** 0 labels  
**Gap:** Complete — no dataset provides these labels

LUMINA's TacticLabel taxonomy:
```
AUTHORITY_CLAIM, THREAT_PRESENTATION, TIME_PRESSURE, ISOLATION_TACTIC,
CREDENTIAL_REQUEST, FINANCIAL_REQUEST, REMOTE_ACCESS_REQUEST,
IDENTITY_REQUEST, BENIGN_CONVERSATION, USER_RESISTANCE, ADVICE_OR_WARNING
```

No public dataset labels individual utterances with these categories.

### 3. Class Balance

**Required:** No class with <10% of the majority class frequency  
**Available:** N/A  
**Expected imbalance (based on real-world scam call analysis):**
- Most common: AUTHORITY_CLAIM, TIME_PRESSURE, FINANCIAL_REQUEST, BENIGN_CONVERSATION
- Rare: ISOLATION_TACTIC, REMOTE_ACCESS_REQUEST, IDENTITY_REQUEST, ADVICE_OR_WARNING

Class weighting and oversampling strategies would be needed even with data.

### 4. Split Integrity

**Required:** Conversation-level splitting with no leakage  
**Available:** Pipeline built and tested (`scripts/ml/prepare_dataset.py`)  
**Status:** ✅ Ready — will work correctly when data is available

The pipeline:
- Groups segments by conversation_id
- Shuffles conversations deterministically
- Assigns entire conversations to train/val/test
- Verifies no conversation appears in multiple splits

### 5. Licensing Status

**Required:** License permits both training and production use  
**Available:** No dataset with suitable license identified  
**Status:** ❌ BLOCKER

The only large dataset (Composite Scam, 46,982 transcripts) is CC BY-NC, which prohibits commercial use. LUMINA is a production system.

### 6. Preprocessing Status

**Required:** Deterministic text cleaning, PII filtering, label mapping  
**Available:** ✅ Built and functional  
**Status:** ✅ Ready

The preprocessing pipeline (`scripts/ml/prepare_dataset.py`) provides:
- Text normalization (unicode, whitespace, control characters)
- PII filtering (phone numbers, emails, SSN, credit cards, Aadhaar)
- Secret detection and redaction
- Label mapping from common patterns to LUMINA taxonomy
- Duplicate detection and removal

### 7. Model Architecture

**Required:** DeBERTa-v3-base with multi-label classification head  
**Available:** ✅ Interface defined and implemented  
**Status:** ✅ Ready (architecture only — no trained weights)

The `TrainedClassifier` class in `app/incident/trained_classifier.py`:
- Extends `TacticClassifier` (ABC)
- Uses DeBERTa-v3-base tokenizer
- Multi-label classification with sigmoid output
- Configurable threshold
- Falls back to DeterministicBaseline when not trained
- Honest `is_trained` reporting

### 8. Compute Requirements

**Required:** Known and documented  
**Available:** ✅ Defined

For DeBERTa-v3-base fine-tuning:
- **Minimum GPU:** NVIDIA T4 (16GB VRAM) or equivalent
- **Recommended GPU:** NVIDIA A100 (40GB) or V100 (16GB)
- **CPU-only:** Possible but very slow (not recommended)
- **Training time estimate:**
  - 10K segments: ~2-4 hours on T4
  - 50K segments: ~8-16 hours on T4
  - 100K segments: ~16-32 hours on T4
- **Batch size:** 16-32 (depending on GPU memory)
- **Learning rate:** 2e-5 to 5e-5
- **Epochs:** 3-5
- **Mixed precision:** FP16 recommended for GPU training

### 9. Deployment Constraints

**Required:** Known and documented  
**Available:** ✅ Defined

- **Inference latency target:** <100ms per segment
- **Model size:** ~440MB (DeBERTa-v3-base)
- **Memory requirement:** ~1GB RAM for inference
- **ONNX export:** Supported for production deployment
- **Mobile deployment:** Quantized model may be needed for Android
- **Fallback:** DeterministicBaseline always available

### 10. Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| No training data | Cannot train | Report blocker (done) |
| Scam baiting ≠ real victims | Biased training if used | Do not use scam-baiting data |
| Speaker attribution unavailable | Cannot use speaker feature | Use text-only features |
| Region-specific tactics | Model may not generalize | Future: region-specific training |
| Adversarial evasion | Model may be bypassed | Deterministic engine as safety net |

---

## What Would Need to Happen for GO

### Phase A: Dataset Creation (4-6 months)

1. **Design annotation protocol**
   - Define guidelines for each TacticLabel
   - Create annotation interface
   - Pilot with 100 segments

2. **Collect source data**
   - Real phone call transcripts (with consent)
   - Licensing for production use
   - Minimum 500 conversations

3. **Annotate**
   - 3+ expert annotators per segment
   - Multi-label per segment
   - Inter-annotator agreement > 0.7 Cohen's kappa

4. **Validate**
   - Review disagreements
   - Finalize labels
   - Quality assurance

### Phase B: Training (1-2 months)

1. **Prepare dataset** using `scripts/ml/prepare_dataset.py`
2. **Train DeBERTa-v3** with cross-validation
3. **Evaluate** on held-out test set
4. **Compare** against DeterministicBaseline
5. **Validate** that ML improves (not degrades) safety

### Phase C: Integration (1 month)

1. **Deploy** alongside deterministic engine
2. **A/B test** ML vs. no-ML
3. **Monitor** for regression
4. **Rollback** if safety degrades

**Total estimated time to GO: 6-9 months**

---

## Conclusion

**Training cannot proceed.**

The infrastructure is ready:
- ✅ Model architecture defined
- ✅ Training pipeline built
- ✅ Preprocessing pipeline built
- ✅ Provenance tracking built
- ✅ Evaluation harness ready
- ✅ Integration with safety engine designed

But the fundamental blocker remains:
- ❌ No training data exists
- ❌ No dataset with segment-level multi-label annotations
- ❌ No dataset with production-use license
- ❌ No way to create this data without significant investment

**The deterministic safety engine remains the sole authority for LUMINA's safety function.**
