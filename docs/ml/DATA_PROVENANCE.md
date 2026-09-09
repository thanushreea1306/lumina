# LUMINA ML — Dataset Provenance Registry

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Machine-readable provenance tracking for all evaluated dataset candidates.  
**Status:** AUDIT COMPLETE — NO SUITABLE TRAINING DATA IDENTIFIED

---

## Evaluation Summary

| Datasets Evaluated | 11 |
|---|---|
| Datasets Verified as Downloadable | 5 |
| Datasets with Clear License | 4 |
| Datasets Permitting Commercial Use | 2 |
| Datasets Permitting Model Training | 2 |
| Datasets with Segment-Level Tactic Labels | 0 |
| **Datasets Suitable for LUMINA** | **0** |

---

## Dataset Provenance Table

| # | Dataset | Source | License | Commercial Use | Training Use | Redistribution | Language | Modality | Size | Labels | Real/Synthetic/Simulated | Privacy Concerns | LUMINA Suitability | Decision |
|---|---------|--------|---------|----------------|--------------|----------------|----------|----------|------|--------|--------------------------|------------------|-------------------|----------|
| 1 | BYU-PCCL Scam Call Identification | [GitHub](https://github.com/BYU-PCCL/scam-call-identification) | MIT (code only) | Unclear for data | Unclear for data | Unclear for data | English | Transcripts | 243+ transcripts | Scam/Non-scam (binary) | Mixed (YouTube scam baiting = simulated victim) | Low (public YouTube content) | **UNSUITABLE** | No standalone dataset; requires LLM API keys; in development; no segment-level labels |
| 2 | Kaggle: Call Transcripts Scam Determinations | [Kaggle](https://www.kaggle.com/datasets/mealss/call-transcripts-scam-determinations) | Not specified | Not specified | Not specified | Not specified | English | Transcripts | 60 calls | Scam/Non-scam (binary) | Real (annotated transcripts) | Low | **UNSUITABLE** | Too small (60 calls); binary labels only; no license specified |
| 3 | Kaggle: YouTube Scam Phone Call Transcripts | [Kaggle](https://www.kaggle.com/datasets/rivalcults/youtube-scam-phone-call-transcripts) | Not specified | Not specified | Not specified | Not specified | English | Transcripts | 243 transcripts | Scam type (multi-class) | Scam baiting (simulated victim) | Low (public YouTube content) | **UNSUITABLE** | Scam baiting = not real victim interactions; no segment-level labels; no license |
| 4 | Derakhshan et al. (2021) | [GitHub](https://github.com/aliderakhsh/Detecting-Telephone-based-Social-Engineering-Attacks-using-Scam-Signatures-Dataset) | Not specified | Not specified | Not specified | Not specified | English | Excel transcripts | 215 calls (75 scam + 140 non-scam) | 5 scam types | **Simulated** (volunteer-generated) | Low | **UNSUITABLE** | Too small; simulated scenarios; 15 samples per type; no segment-level labels |
| 5 | Wood et al. (NDSS 2024) | [Paper](https://arxiv.org/html/2307.01965v1) | Not yet released | Not yet released | Not yet released | Not yet released | English | Transcripts | 341 transcripts (90 hours) | 4-7 scam types (manually labeled) | Scam baiting (simulated victim) | Low (public YouTube content) | **UNSUITABLE** | Dataset promised but not publicly released; scam baiting = simulated victim; HMM stage labels not segment-level |
| 6 | Kaggle: Composite Scam Transcript Dataset | [Kaggle](https://www.kaggle.com/datasets/ibrahimbagwan12/composite-scam-transcript-dataset) | **CC BY-NC 4.0** | **NO (Non-Commercial)** | Yes | Yes (with attribution) | English | Transcripts | 46,982 transcripts | Financial fraud categories | Composite (mixed sources) | Medium (financial content) | **UNSUITABLE** | CC BY-NC prohibits commercial/production use; LUMINA is a production system |
| 7 | Kaggle: Augmented Scam Call Transcript | [Kaggle](https://www.kaggle.com/datasets/yingzisilver/augmented-scam-call-transcript) | **CC0 (Public Domain)** | Yes | Yes | Yes | English | Transcripts | Unknown (augmented) | Scam/Non-scam | **Augmented** (possibly synthetic) | Low | **UNSUITABLE** | "Augmented" suggests synthetic modification; no segment-level tactic labels; verify before use |
| 8 | BothBosu Synthetic Datasets | [HuggingFace](https://huggingface.co/collections/BothBosu/synthetic-data-for-scam-detection) | Various | Varies | Varies | Varies | English | Transcripts | Various | Various | **LLM-GENERATED** | Low | **EXCLUDED** | Synthetic/LLM-generated data — violates LUMINA's absolute rules |
| 9 | Zenodo: Multiclass NLP Dataset | [Zenodo](https://zenodo.org/records/15235123) | Open | Yes | Yes | Yes | English | Email/SMS | 624 messages | 6 classes (Phishing, Malware, Scareware, Baiting, Pretexting, NOT-Malicious) | Human-created | Low | **UNSUITABLE** | Too small (624); email/SMS not phone calls; no segment-level labels; different modality |
| 10 | ScamGen | [Mendeley](https://data.mendeley.com/datasets/dkypjhkmgb) | Research only | **NO** | Limited | No | **Chinese** | Transcripts | Various | Various | **Synthetic** | Low | **EXCLUDED** | Wrong language; synthetic; research-only license |
| 11 | Kimdesok Korean Voice Phishing | [GitHub](https://github.com/kimdesok/Text-classification-of-voice-phishing-transcipts) | Not specified | Not specified | Not specified | Not specified | **Korean** | Transcripts | 2,927 entries | Binary (fraud/non-fraud) | Real (transcribed calls) | Medium | **EXCLUDED** | Wrong language; binary labels only |

---

## Detailed Notes per Dataset

### 1. BYU-PCCL Scam Call Identification

**Provenance Status:** Code repository exists; data pipeline in development.

- **Repository:** `BYU-PCCL/scam-call-identification` (MIT license for code)
- **Data Sources:** YouTube scam baiting videos, Candor dataset, Switchboard dataset, Thai Call Center dataset
- **Critical Issues:**
  - No standalone dataset release (no downloadable CSV/JSON)
  - Requires OpenAI GPT and Google Gemini API keys for feature extraction
  - Project explicitly marked "(In development)"
  - LLM-derived features mean the labels are LLM-generated
  - No segment-level behavioral/tactic labels
- **Verdict:** UNSUITABLE — no usable dataset; LLM-dependent pipeline; in development

### 2. Kaggle: Call Transcripts Scam Determinations

**Provenance Status:** Downloadable but insufficient.

- **Size:** 60 calls
- **Labels:** Binary (scam/non-scam)
- **Critical Issues:**
  - 60 calls is far below minimum for deep learning (need thousands minimum)
  - Binary labels do not map to LUMINA's 11-class taxonomy
  - No license specified on Kaggle page
- **Verdict:** UNSUITABLE — too small; binary labels

### 3. Kaggle: YouTube Scam Phone Call Transcripts

**Provenance Status:** Downloadable but problematic.

- **Size:** 243 transcripts
- **Labels:** Scam type (multi-class)
- **Critical Issues:**
  - Scam baiting videos = scammers interacting with professional scam-baiters, NOT real victims
  - Victim behavior in scam-baiting calls is deliberately deceptive (baiting)
  - Does not represent real victim responses
  - No license specified
  - No segment-level labels
- **Verdict:** UNSUITABLE — simulated victim behavior; no segment labels

### 4. Derakhshan et al. (2021)

**Provenance Status:** GitHub repository exists.

- **Size:** 215 calls (75 scam + 140 non-scam)
- **Labels:** 5 scam types
- **Critical Issues:**
  - Scam calls were generated by 15 graduate students (simulated scenarios)
  - 15 samples per scam type — statistically insufficient
  - Non-scam calls from CallHome dataset (different domain)
  - No license specified
  - No segment-level labels
- **Verdict:** UNSUITABLE — simulated; too small; no segment labels

### 5. Wood et al. (NDSS 2024)

**Provenance Status:** Paper published; dataset promised but not released.

- **Size:** 341 transcripts (90 hours)
- **Labels:** 4-7 scam types (manually labeled); HMM-derived stage labels
- **Critical Issues:**
  - Dataset was promised "on acceptance" but not yet publicly available as of September 2026
  - Scam baiting = simulated victim behavior
  - HMM stage labels are conversation-level, not segment-level
  - No license specified for data
- **Verdict:** UNSUITABLE — not available; simulated victim; no segment labels

### 6. Kaggle: Composite Scam Transcript Dataset

**Provenance Status:** Downloadable; clear license.

- **Size:** 46,982 transcripts
- **Labels:** Financial fraud categories
- **License:** CC BY-NC 4.0 (Non-Commercial)
- **Critical Issues:**
  - **CC BY-NC explicitly prohibits commercial use**
  - LUMINA is intended as a production system
  - Using this dataset would violate the license
  - Composite nature means mixed provenance
- **Verdict:** **EXCLUDED** — Non-Commercial license incompatible with production use

### 7. Kaggle: Augmented Scam Call Transcript

**Provenance Status:** Downloadable; CC0 license.

- **Size:** Unknown (augmented)
- **Labels:** Scam/Non-scam
- **License:** CC0 (Public Domain)
- **Critical Issues:**
  - "Augmented" implies synthetic modification of original data
  - Binary labels only
  - No segment-level behavioral labels
  - Need to verify actual content before use
- **Verdict:** UNSUITABLE — augmented/synthetic; binary labels; verify before any use

### 8. BothBosu Synthetic Datasets

**Provenance Status:** Multiple HuggingFace datasets.

- **Critical Issues:**
  - ALL datasets are LLM-generated/synthetic
  - Explicitly violates LUMINA's absolute rules:
    - "No synthetic datasets"
    - "No LLM-generated training examples"
- **Verdict:** **EXCLUDED** — synthetic data prohibited

### 9. Zenodo: Multiclass NLP Dataset

**Provenance Status:** Downloadable; open license.

- **Size:** 624 messages
- **Labels:** 6 classes (Phishing, Malware, Scareware, Baiting, Pretexting, NOT-Malicious)
- **Critical Issues:**
  - 624 messages is far too small for deep learning
  - Email/SMS modality — NOT phone call transcripts
  - Different domain from LUMINA's use case
  - No segment-level labels
- **Verdict:** UNSUITABLE — wrong modality; too small

### 10. ScamGen

**Provenance Status:** Mendeley Data.

- **Critical Issues:**
  - Chinese language — LUMINA requires English
  - Synthetic data
  - Research-only license
- **Verdict:** **EXCLUDED** — wrong language; synthetic

### 11. Kimdesok Korean Voice Phishing

**Provenance Status:** GitHub repository.

- **Size:** 2,927 entries
- **Labels:** Binary (fraud/non-fraud)
- **Critical Issues:**
  - Korean language — LUMINA requires English
  - Binary labels
- **Verdict:** **EXCLUDED** — wrong language

---

## Critical Finding: No Segment-Level Tactic Labels Exist

**LUMINA's TacticLabel taxonomy requires segment-level, multi-label behavioral classification:**

```
AUTHORITY_CLAIM, THREAT_PRESENTATION, TIME_PRESSURE, ISOLATION_TACTIC,
CREDENTIAL_REQUEST, FINANCIAL_REQUEST, REMOTE_ACCESS_REQUEST,
IDENTITY_REQUEST, BENIGN_CONVERSATION, USER_RESISTANCE, ADVICE_OR_WARNING
```

**No public dataset provides:**
1. Segment-level (utterance-level) labels for social-engineering tactics
2. Multi-label annotation (a segment can contain multiple tactics)
3. Labels matching LUMINA's behavioral taxonomy
4. Sufficient scale for deep learning (thousands of labeled segments)
5. Clear commercial-use license

The closest dataset (Wood et al., 341 transcripts) provides conversation-level scam type labels and HMM-derived stage labels, but:
- Not yet publicly released
- Scam baiting = simulated victim behavior
- Stage labels are conversation-level, not segment-level
- No multi-label annotation

---

## Implications

1. **No existing dataset can train a segment-level multi-label tactic classifier**
2. **Creating such a dataset would require:**
   - Expert annotation of phone call transcripts
   - Segment-level (utterance-level) labeling
   - Multi-label annotation per segment
   - Thousands of labeled segments minimum
   - Clear licensing for production use
3. **The deterministic safety engine remains the only reliable foundation**
4. **ML training cannot proceed without first creating a custom annotated dataset**

---

## Next Steps (Blocked)

| Step | Status | Blocker |
|------|--------|---------|
| Segment-level annotation | BLOCKED | No existing annotated dataset |
| Expert annotator recruitment | NOT STARTED | Requires funding/planning |
| Annotation protocol design | NOT STARTED | Requires domain expertise |
| Custom dataset creation | NOT STARTED | Requires annotation infrastructure |
| DeBERTa training | BLOCKED | No training data |

---

## References

1. Derakhshan, A., et al. (2021). "Detecting Telephone-based Social Engineering Attacks using Scam Signatures." ACSAC.
2. Wood, I.D., et al. (2024). "An analysis of scam baiting calls: Identifying and extracting scam stages and scripts." NDSS.
3. Shen, Z., et al. (2024). "Combating Phone Scams with LLM-based Detection: Where Do We Stand?" arXiv:2409.11643.
4. BYU-PCCL. (2025). "Scam Call Identification System." GitHub.
5. Engineering Ingegneria Informatica Spa. (2025). "Multiclass NLP Dataset for Phishing and Social Engineering Threat Detection." Zenodo.
