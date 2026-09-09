# LUMINA ML — TeleAntiFraud-28k Suitability Gate

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Formal suitability gate decision for TeleAntiFraud-28k.
**Decision:** 🔴 RED — DO NOT USE

---

## Decision

# 🔴 RED — DO NOT USE FOR LUMINA TRAINING

---

## Status Matrix

| Field | Status | Evidence |
|-------|--------|----------|
| **DATA_STATUS** | EXISTS | 28,511 samples on HuggingFace |
| **LICENSE_STATUS** | VERIFIED | Apache 2.0 (Copyright 2025 Zhiming Ma) |
| **PRODUCTION_TRAINING** | PERMITTED | Apache 2.0 permits commercial use |
| **REAL_TWO_PARTY** | NO | TTS + LLM synthetic |
| **VICTIM_BEHAVIOR** | NOT VERIFIED | No speaker attribution, Chinese |
| **SYNTHETIC_CONTAMINATION** | SEVERE | 60-70% LLM text, 100% TTS audio |
| **LABEL_STATUS** | CONVERSATION-LEVEL ONLY | Scenario/fraud type, NOT segment-level |
| **PRIVACY_STATUS** | ACCEPTABLE | Anonymized, no original data released |
| **LEAKAGE_RISK** | LOW | Conversation-level grouping possible |
| **LUMINA_TASK_MATCH** | FATAL MISMATCH | Chinese, wrong label type, synthetic |
| **RECOMMENDATION** | DO NOT USE | Multiple fatal blockers |

---

## Fatal Blockers

### Blocker 1: Wrong Language
- **Requirement:** English
- **Actual:** Mandarin Chinese
- **Evidence:** HuggingFace metadata `language: zh`, paper "Focus primarily on Mandarin Chinese speech"
- **Severity:** FATAL — Insurmountable

### Blocker 2: Synthetic Data
- **Requirement:** Real human conversations
- **Actual:** 60-70% LLM-generated dialogues, 100% TTS-generated audio
- **Evidence:** Paper describes DS2 (LLM imitation) and DS3 (multi-agent) as primary data sources; all audio via ChatTTS
- **Severity:** FATAL — Violates LUMINA's absolute rules

### Blocker 3: Wrong Label Type
- **Requirement:** Segment-level multi-label behavioral tactics
- **Actual:** Conversation-level scenario/fraud type classification
- **Evidence:** Paper describes 3 tasks: scene classification, fraud determination, fraud type identification — all conversation-level
- **Severity:** FATAL — Cannot be mapped to LUMINA taxonomy

---

## Non-Fatal Issues (but still problematic)

| Issue | Status | Impact |
|-------|--------|--------|
| No speaker attribution | Present | Cannot distinguish caller vs. recipient |
| LLM-generated annotations | DeepSeek-R1 | Not human-annotated |
| Chinese fraud taxonomy | 7 scenarios, 7 fraud types | Does not map to LUMINA's 11 tactics |
| Real subset only in test set | DS1 in test only | Cannot use for training |
| No segment-level timestamps | Absent | Cannot segment conversations |

---

## What Would Need to Change

For TeleAntiFraud-28k to become suitable:

1. ❌ **Language:** Would need English version (doesn't exist)
2. ❌ **Real audio:** Would need original human recordings (not released)
3. ❌ **Speaker attribution:** Would need caller/recipient labels (not provided)
4. ❌ **Segment-level labels:** Would need utterance-level tactic annotations (not provided)
5. ❌ **Behavioral taxonomy:** Would need LUMINA's 11 labels (different taxonomy)
6. ❌ **Human annotations:** Would need expert human labels (LLM-generated)

**None of these changes are feasible without creating an entirely new dataset.**

---

## Comparison with LUMINA Requirements

| LUMINA Requirement | TeleAntiFraud-28k | Gap |
|--------------------|-------------------|-----|
| English language | Chinese | ❌ Complete gap |
| Real human conversations | TTS + LLM | ❌ Complete gap |
| Two-party with speaker labels | No speaker labels | ❌ Complete gap |
| Segment-level multi-label | Conversation-level | ❌ Complete gap |
| 11 behavioral tactics | 7 fraud types | ❌ Different taxonomy |
| Human annotations | LLM-generated | ❌ Complete gap |
| Production licensing | Apache 2.0 | ✅ Met |
| Privacy/anonymization | Anonymized | ✅ Met |

**Score: 2/8 requirements met (25%)**
**Both met requirements are non-substantive (licensing and privacy).**
**All substantive requirements fail.**

---

## TRAINING_STATUS

```
╔══════════════════════════════════════════════════════════════╗
║                    TRAINING STATUS                          ║
║                    ███  NO_GO  ███                           ║
║                                                              ║
║  TeleAntiFraud-28k:  🔴 RED — DO NOT USE                    ║
║                                                              ║
║  Fatal Blockers:                                             ║
║    ❌ Wrong language (Chinese, not English)                   ║
║    ❌ Synthetic data (TTS + LLM generated)                   ║
║    ❌ Wrong label type (conversation-level, not segment)     ║
║                                                              ║
║  Deterministic Safety Engine: REMAINS SOLE AUTHORITY         ║
║  No synthetic data. No LLM examples. No fabricated labels.   ║
╚══════════════════════════════════════════════════════════════╝
```

---

## NEXT_REQUIRED_ACTION

**TeleAntiFraud-28k does not change the blocking action:**

**Obtain legitimate English two-party scam conversation data** via:
1. Deploy LUMINA opt-in recording program
2. Academic partnerships with English scam call researchers
3. Government/law enforcement recording requests
4. Licensing legitimate English conversation datasets

**The search for suitable data continues.**
