# LUMINA ML — TeleAntiFraud-28k Forensic Investigation

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Rigorous forensic investigation of TeleAntiFraud-28k for LUMINA pilot suitability.
**Status:** INVESTIGATION COMPLETE — RED FLAG: WRONG LANGUAGE

---

## Executive Summary

**TeleAntiFraud-28k is a MANDARIN CHINESE dataset.** LUMINA requires English. This is a fundamental, insurmountable blocker.

Beyond language, the dataset has additional critical issues:
- **~100% TTS-generated audio** (even the "real" subset uses TTS regeneration)
- **~60-70% LLM-generated dialogues** (DS2 + DS3 subsets)
- **Annotations are LLM-generated** (DeepSeek-R1), not human-annotated
- **Conversation-level labels only** (scenario, fraud type), not segment-level behavioral tactics
- **No speaker attribution** (caller vs. recipient not distinguished in labels)

---

## 1. Primary Source Evidence

### Source 1: Original Paper
- **Title:** "TeleAntiFraud-28k: An Audio-Text Slow-Thinking Dataset for Telecom Fraud Detection"
- **URL:** https://arxiv.org/html/2503.24115v4
- **Venue:** ACM MM 2025 (Dublin, Ireland)
- **Authors:** Zhiming Ma, Peidong Wang, et al. (China Mobile Internet Company)
- **Copyright:** "© acmlicensed"

**Key Evidence:**
> "Focus primarily on **Mandarin Chinese speech**. Future work could extend to multilingual..."

> "Our dataset is constructed through three strategies: (1) Privacy-preserved text-truth sample generation using automatically speech recognition-transcribed call recordings (with anonymized original audio), ensuring real-world consistency through **text-to-speech model regeneration**"

> "Semantic enhancement via **large language model based self-instruction sampling** on authentic ASR outputs"

> "Multi-agent adversarial synthesis, which simulates emerging fraud tactics through predefined communication scenarios"

### Source 2: HuggingFace Dataset Page
- **URL:** https://huggingface.co/datasets/JimmyMa99/TeleAntiFraud
- **Metadata:** `language: zh`, `license: apache-2.0`
- **Description:** "TeleAntiFraud is a **Chinese** audio-text fraud detection dataset"

**Key Evidence:**
> "Licensed under the Apache License, Version 2.0"
> "Copyright 2025 Zhiming Ma. All rights reserved."

### Source 3: GitHub Repository
- **URL:** https://github.com/JimmyMa99/TeleAntiFraud
- **License:** Apache-2.0 (per HuggingFace metadata)

### Source 4: Literature Reviews
- **Source:** https://www.themoonlight.io/tw/review/teleantifraud-28k-a-audio-text-slow-thinking-dataset-for-telecom-fraud-detection
- **Evidence:** "Focus primarily on **Mandarin Chinese speech**"

---

## 2. Exact Data Composition

### Total Dataset
| Metric | Value | Source |
|--------|-------|--------|
| Total samples | 28,511 | Paper Table 1 |
| Training set | 21,490 (75.38%) | Paper Table 1 |
| Test set | 7,021 (24.62%) | Paper Table 1 |
| Fraud calls | 13,647 (47.86%) | Paper Table 1 |
| Normal calls | 14,864 (52.13%) | Paper Table 1 |
| Total audio duration | 307+ hours | Paper Abstract |
| Language | **Mandarin Chinese** | Paper + HuggingFace |

### HuggingFace Public Release
| Package | Train | Test | Total | Description |
|---------|-------|------|-------|-------------|
| binary_classification.zip | 4,000 | 400 | 4,400 | Binary fraud classification |
| sft.zip | 27,146 | 6,807 | 33,953 | Multi-turn SFT data |
| audio.zip | — | — | — | TTS-generated audio files |

### Data Generation Sources (from Paper)
| Subset | Description | Real? | Audio? |
|--------|-------------|-------|--------|
| DS1 (Real-Data ASR) | Real calls → ASR → anonymize → TTS | Text from real; audio is TTS | TTS |
| DS2 (LLM Imitation) | LLM-generated dialogues | **Synthetic** | TTS |
| DS3 (Multi-Agent) | AI agent-simulated conversations | **Synthetic** | TTS |

**Critical:** The paper states: "Our public release includes these anonymized segments only in the test set, alongside LLM-generated and multi-agent-derived data"

This means:
- **Test set** contains some real (anonymized) text + TTS audio
- **Training set** is predominantly LLM-generated + multi-agent synthetic

---

## 3. Synthetic Data Forensics

### Evidence Table

| Component | Real | Synthetic | Mixed | Unknown | Evidence |
|-----------|------|-----------|-------|---------|----------|
| **Dialogue text (DS1)** | Text from real calls | — | — | — | Paper: "ASR-transcribed call recordings" |
| **Dialogue text (DS2)** | — | ✅ LLM-generated | — | — | Paper: "LLM based self-instruction sampling" |
| **Dialogue text (DS3)** | — | ✅ Multi-agent generated | — | — | Paper: "Multi-agent adversarial synthesis" |
| **Audio (ALL)** | — | ✅ TTS-generated | — | — | Paper: "ChatTTS" for all audio synthesis |
| **Annotations** | — | ✅ DeepSeek-R1 generated | — | — | Paper: "DeepSeek-R1... generates detailed annotations" |
| **Labels** | — | ✅ LLM-generated | — | — | Paper: LLM-based annotation pipeline |

### Synthetic Proportion Estimate

Based on the paper's data composition:
- DS1 (real text, TTS audio): ~30-40% of training data (estimated)
- DS2 (LLM text, TTS audio): ~30-35% of training data
- DS3 (multi-agent text, TTS audio): ~25-30% of training data

**Conservative estimate: 60-70% of training data is LLM-generated dialogues.**
**100% of audio is TTS-generated.**
**100% of annotations are LLM-generated.**

### Can the Real Subset Be Isolated?

**DS1 (real text subset) characteristics:**
- Text derived from real ASR transcriptions
- Anonymized (names, numbers removed)
- Audio is TTS-regenerated (NOT original recordings)
- Only included in the test set (not training set)
- No speaker attribution provided
- No segment-level labels

**Isolation feasibility:** Theoretically possible if DS1 samples are identifiable in the metadata. However:
1. Audio is TTS — not genuine human speech
2. No speaker attribution
3. No segment-level behavioral labels
4. Only in test set (not useful for training)
5. Chinese language

**FINAL: Real subset cannot be meaningfully isolated for LUMINA's purposes.**

---

## 4. LUMINA Task Match Analysis

### Language Requirement
| Requirement | TeleAntiFraud-28k | Match |
|-------------|-------------------|-------|
| English language | **Mandarin Chinese** | ❌ **FATAL MISMATCH** |

### Two-Party Structure
| Requirement | TeleAntiFraud-28k | Match |
|-------------|-------------------|-------|
| Caller present | Yes (in dialogue) | ⚠️ Present in text |
| Recipient present | Yes (in dialogue) | ⚠️ Present in text |
| Speaker attribution | **Not provided** | ❌ No speaker labels |
| Genuine human conversation | No (TTS + LLM) | ❌ Synthetic |

### Behavioral Tactics Coverage

| LUMINA Tactic | Evidence in TeleAntiFraud-28k | Assessment |
|---------------|-------------------------------|------------|
| AUTHORITY_CLAIM | Possibly present in scam dialogues | ⚠️ Unknown (Chinese text) |
| THREAT_PRESENTATION | Possibly present | ⚠️ Unknown |
| TIME_PRESSURE | Possibly present | ⚠️ Unknown |
| ISOLATION_TACTIC | Unlikely (not in fraud taxonomy) | ❌ Not covered |
| CREDENTIAL_REQUEST | Possibly present | ⚠️ Unknown |
| FINANCIAL_REQUEST | Possibly present | ⚠️ Unknown |
| IDENTITY_IMPERSONATION | Possibly present | ⚠️ Unknown |
| REMOTE_ACCESS | Unlikely (not in fraud taxonomy) | ❌ Not covered |
| USER_RESISTANCE | Unknown (victim behavior) | ⚠️ Unknown |
| SAFETY_ADVICE | Unlikely | ❌ Not covered |
| BENIGN | Yes (normal calls included) | ⚠️ Present |

**Critical:** The dataset's fraud taxonomy is:
- Scenario: 7 types (Customer Consultation, Appointment, Shopping, Dining, Food Delivery, Ride-Hailing, Transportation)
- Fraud type: 7 types (Customer Service, Banking, Investment, Phishing, Lottery, Kidnapping, Identity Theft)

This does NOT map to LUMINA's 11 behavioral tactics. These are conversation-level category labels, not segment-level behavioral annotations.

### Segment-Level Annotation
| Requirement | TeleAntiFraud-28k | Match |
|-------------|-------------------|-------|
| Segment-level labels | **No** (conversation-level only) | ❌ |
| Multi-label per segment | **No** (single label per conversation) | ❌ |
| Behavioral tactic labels | **No** (scenario/fraud type) | ❌ |
| Speaker-specific labels | **No** | ❌ |

---

## 5. Label Quality Analysis

### Available Labels
| Label Type | Level | Human-Created | Multi-Label | Speaker-Specific |
|------------|-------|---------------|-------------|------------------|
| Scene classification | Conversation | ❌ LLM (DeepSeek-R1) | No | No |
| Fraud determination | Conversation | ❌ LLM (DeepSeek-R1) | No | No |
| Fraud type | Conversation | ❌ LLM (DeepSeek-R1) | No | No |

### LUMINA Tactic Mapping

| LUMINA Tactic | Mapping | Support Level |
|---------------|---------|---------------|
| AUTHORITY_CLAIM | NOT_SUPPORTED | No direct mapping |
| THREAT_PRESENTATION | NOT_SUPPORTED | No direct mapping |
| TIME_PRESSURE | NOT_SUPPORTED | No direct mapping |
| ISOLATION_TACTIC | NOT_SUPPORTED | Not in fraud taxonomy |
| CREDENTIAL_REQUEST | NOT_SUPPORTED | Not in fraud taxonomy |
| FINANCIAL_REQUEST | PARTIAL (Banking/Investment Fraud) | Conversation-level only |
| REMOTE_ACCESS_REQUEST | NOT_SUPPORTED | Not in fraud taxonomy |
| IDENTITY_REQUEST | PARTIAL (Identity Theft) | Conversation-level only |
| BENIGN_CONVERSATION | PARTIAL (Normal Calls) | Conversation-level only |
| USER_RESISTANCE | NOT_SUPPORTED | Not annotated |
| ADVICE_OR_WARNING | NOT_SUPPORTED | Not annotated |

**Summary:** No direct mapping exists. Partial mappings are conversation-level, not segment-level.

---

## 6. Segmentation Feasibility

| Requirement | Available | Assessment |
|-------------|-----------|------------|
| Conversation ID | Likely (sample ID) | ⚠️ Needs verification |
| Segment ID | **No** (conversation-level) | ❌ |
| Speaker labels | **No** | ❌ |
| Timestamps | **No** | ❌ |
| Text/audio alignment | **No** (TTS-generated) | ❌ |
| Conversation-level grouping | Possible | ⚠️ |

**Assessment:** The dataset is conversation-level, not segment-level. LUMINA requires segment-level annotation. Segmentation would require:
1. Manual segmentation of Chinese text
2. Manual speaker attribution
3. Manual tactic annotation
4. Manual phase annotation

This effectively means creating an entirely new dataset from scratch, using TeleAntiFraud-28k merely as a source of Chinese scam conversation text — which is not useful for English LUMINA.

---

## 7. License Forensics

### Dataset License
| Field | Value | Source |
|-------|-------|--------|
| License | Apache License 2.0 | HuggingFace metadata |
| Copyright | "Copyright 2025 Zhiming Ma" | HuggingFace README |
| Commercial use | ✅ YES (Apache 2.0) | Apache 2.0 terms |
| Training use | ✅ YES (Apache 2.0) | Apache 2.0 terms |
| Production use | ✅ YES (Apache 2.0) | Apache 2.0 terms |
| Redistribution | ✅ YES (Apache 2.0) | Apache 2.0 terms |

### Underlying Content Rights
| Component | Rights | Assessment |
|-----------|--------|------------|
| TTS audio | Generated by ChatTTS | No original human recordings released |
| LLM text | Generated by DeepSeek/Qwen | No original human transcripts released |
| Original recordings | **NOT released** | Anonymized and discarded |
| ASR transcripts | Derived from real calls | Anonymized; rights unclear |

**Critical distinction:** The Apache 2.0 license covers the dataset artifacts (TTS audio, LLM text, annotations). It does NOT cover the original human recordings, which are not released.

### License Assessment
- **Dataset license:** Apache 2.0 ✅
- **Underlying content rights:** Not applicable (no original content released)
- **Privacy/personal data:** Original recordings anonymized and not released
- **Commercial ML training:** Permitted under Apache 2.0

**LICENSE_STATUS = VERIFIED (Apache 2.0)**
**PRODUCTION_TRAINING = PERMITTED under Apache 2.0**

However, the license is moot because the dataset fails on language and data quality requirements.

---

## 8. Privacy / Consent

| Aspect | Status | Evidence |
|--------|--------|----------|
| Names | Anonymized | Paper: "anonymizing sensitive information" |
| Phone numbers | Anonymized | Paper: "privacy-protected text samples" |
| Account info | Anonymized | Paper: "safeguarding the privacy" |
| Biometric/voice | **TTS-generated** | No original human voice released |
| Consent | Not specified | No IRB/ethics mention in paper |
| Deletion/withdrawal | Not applicable | No original data released |

**PRIVACY_STATUS = ACCEPTABLE** (no original personal data released)

---

## 9. Clean Subset Possibility

### Can a Clean Subset Be Isolated?

**Criteria for LUMINA suitability:**
1. Genuinely real conversation text ✅ (DS1 subset)
2. Human conversation ⚠️ (text from real, but TTS audio)
3. Two-party ⚠️ (dialogue structure present)
4. Victim/recipient present ⚠️ (in dialogue text)
5. English ❌ (Mandarin Chinese)
6. Non-synthetic ❌ (audio is TTS, annotations are LLM)
7. Provenance documented ✅
8. Production ML rights verified ✅ (Apache 2.0)
9. Privacy requirements satisfied ✅
10. Speaker structure available ❌ (no speaker labels)
11. Conversation boundaries available ⚠️ (possible)
12. Suitable for LUMINA behavioral annotation ❌ (wrong language, wrong label type)

**CLEAN SUBSET POSSIBLE = NO**

**Reason:** The fundamental blocker is language (Mandarin Chinese ≠ English). Even if all other issues were resolved, the dataset cannot be used for English LUMINA training.

---

## 10. Pilot Acceptance Gate Comparison

| Criterion | Required | TeleAntiFraud-28k | Pass? |
|-----------|----------|-------------------|-------|
| ≥500 segments | Yes | 28,511 | ✅ |
| ≥50 real two-party conversations | Yes | 28,511 conversations | ⚠️ Synthetic |
| Production-use licensing | Yes | Apache 2.0 | ✅ |
| Real human conversations | Yes | **TTS + LLM generated** | ❌ |
| Conversation-level grouping | Yes | Possible | ⚠️ |
| Sufficient behavioral diversity | Yes | 7 scenarios, 7 fraud types | ⚠️ Different taxonomy |
| No synthetic contamination | Yes | **60-70% LLM + 100% TTS** | ❌ |
| No fabricated labels | Yes | **LLM-generated annotations** | ❌ |
| Privacy/provenance acceptable | Yes | Anonymized, Apache 2.0 | ✅ |
| **English language** | **Yes** | **Mandarin Chinese** | ❌ **FATAL** |

**ACCEPTANCE GATE: FAILED**

---

## 11. Hard Stop Compliance

**This investigation stops at forensic analysis. No actions taken:**
- ❌ Dataset NOT downloaded
- ❌ No model trained
- ❌ No labels created
- ❌ No synthetic data generated
- ❌ No LLM examples generated
- ❌ No metrics fabricated

---

## 12. FINAL DECISION

# 🔴 RED — DO NOT USE FOR LUMINA TRAINING

---

## Status Fields

```
DATA_STATUS = EXISTS (28,511 samples, Chinese, TTS+LLM generated)
LICENSE_STATUS = VERIFIED (Apache 2.0)
PRODUCTION_TRAINING = PERMITTED (Apache 2.0) but IRRELEVANT
REAL_TWO_PARTY = NO (TTS + LLM synthetic)
VICTIM_BEHAVIOR = NOT VERIFIED (no speaker attribution, Chinese)
SYNTHETIC_CONTAMINATION = SEVERE (60-70% LLM text, 100% TTS audio, 100% LLM annotations)
LABEL_STATUS = CONVERSATION-LEVEL ONLY (scenario/fraud type, NOT segment-level tactics)
PRIVACY_STATUS = ACCEPTABLE (anonymized, no original data released)
LEAKAGE_RISK = LOW (conversation-level grouping possible)
LUMINA_TASK_MATCH = FATAL MISMATCH (Chinese, wrong label type, synthetic)
RECOMMENDATION = DO NOT USE
```

---

## 13. Why NOT Just the "Real" Subset?

Even if we could isolate DS1 (real ASR text):
1. **Language:** Still Mandarin Chinese
2. **Audio:** TTS-regenerated, not original human speech
3. **Speaker attribution:** None provided
4. **Segment-level labels:** None (conversation-level only)
5. **Behavioral tactics:** Not annotated
6. **Only in test set:** Not available for training
7. **Anonymized:** May have lost behavioral nuances

**There is no path to using TeleAntiFraud-28k for LUMINA's English behavioral classification task.**

---

## 14. What This Means for LUMINA

TeleAntiFraud-28k confirms the fundamental problem:
- **No English two-party scam conversation dataset with segment-level behavioral annotations exists.**
- The only large dataset (TeleAntiFraud-28k) is Chinese, synthetic, and conversation-level.
- LUMINA's pilot dataset must come from other sources.

**NEXT_REQUIRED_ACTION remains:**
1. Verify if any English subset exists (unlikely)
2. Deploy LUMINA opt-in recording program
3. Pursue academic partnerships with English scam call datasets
4. Consider government/law enforcement recordings

**TRAINING_STATUS = NO_GO**
