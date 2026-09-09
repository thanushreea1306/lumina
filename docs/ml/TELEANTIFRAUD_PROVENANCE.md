# LUMINA ML — TeleAntiFraud-28k Provenance Registry

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Machine-readable provenance tracking for TeleAntiFraud-28k evaluation.

---

## Dataset Identity

| Field | Value |
|-------|-------|
| Dataset Name | TeleAntiFraud-28k |
| Full Title | TeleAntiFraud-28k: An Audio-Text Slow-Thinking Dataset for Telecom Fraud Detection |
| Version | Public release (HuggingFace) |
| Created | 2025 |
| Authors | Zhiming Ma, Peidong Wang, Minhua Huang, Jinpeng Wang, Kai Wu, Xiangzhao Lv, Yachun Pang, Yin Yang, Wenjie Tang, Yuchen Kang |
| Institution | China Mobile Internet Company Ltd., Northeastern University |
| Venue | ACM MM 2025 (Dublin, Ireland) |
| DOI | 10.1145/3746027.3755835 |

---

## Source Evidence Chain

### Source 1: Original Paper
- **URL:** https://arxiv.org/html/2503.24115v4
- **Evidence:** "Focus primarily on Mandarin Chinese speech"
- **Evidence:** "text-to-speech model regeneration"
- **Evidence:** "large language model based self-instruction sampling"
- **Evidence:** "Multi-agent adversarial synthesis"
- **Confidence:** HIGH (primary source)

### Source 2: HuggingFace Dataset
- **URL:** https://huggingface.co/datasets/JimmyMa99/TeleAntiFraud
- **Evidence:** `language: zh` (Chinese)
- **Evidence:** `license: apache-2.0`
- **Evidence:** "TeleAntiFraud is a Chinese audio-text fraud detection dataset"
- **Evidence:** "Copyright 2025 Zhiming Ma"
- **Confidence:** HIGH (primary source)

### Source 3: GitHub Repository
- **URL:** https://github.com/JimmyMa99/TeleAntiFraud
- **Evidence:** Apache-2.0 license
- **Confidence:** HIGH (primary source)

### Source 4: Literature Review
- **URL:** https://www.themoonlight.io/tw/review/teleantifraud-28k-a-audio-text-slow-thinking-dataset-for-telecom-fraud-detection
- **Evidence:** "Focus primarily on Mandarin Chinese speech"
- **Confidence:** MEDIUM (secondary source, consistent with primary)

---

## Licensing Provenance

| Component | License | Owner | Evidence |
|-----------|---------|-------|----------|
| Dataset artifacts | Apache 2.0 | Zhiming Ma | HuggingFace README |
| Code repository | Apache 2.0 | JimmyMa99 | GitHub |
| Paper | ACM License | ACM | Paper header |
| TTS audio | Generated | ChatTTS | Paper methodology |
| LLM text | Generated | DeepSeek/Qwen | Paper methodology |

---

## Content Provenance

| Component | Source Method | Real? | Audio? | Evidence |
|-----------|--------------|-------|--------|----------|
| DS1 text | ASR from real calls | Text: Yes | TTS | Paper: "ASR-transcribed call recordings" |
| DS2 text | LLM self-instruct | **No** | TTS | Paper: "LLM based self-instruction sampling" |
| DS3 text | Multi-agent framework | **No** | TTS | Paper: "Multi-agent adversarial synthesis" |
| ALL audio | ChatTTS synthesis | **No** | TTS | Paper: "ChatTTS" for all audio |
| ALL annotations | DeepSeek-R1 | **No** | — | Paper: "DeepSeek-R1... generates detailed annotations" |

---

## Privacy Provenance

| Aspect | Status | Evidence |
|--------|--------|----------|
| Original recordings | NOT released | Paper: "anonymized original audio" |
| Names | Anonymized | Paper: "anonymizing sensitive information" |
| Phone numbers | Anonymized | Paper: "privacy-protected text samples" |
| IRB/Ethics | Not mentioned | Paper has no ethics section |
| Consent | Not specified | No consent documentation found |

---

## LUMINA Suitability Provenance

| Criterion | Status | Evidence |
|-----------|--------|----------|
| English language | ❌ FATAL | HuggingFace: `language: zh` |
| Real conversations | ❌ FATAL | Paper: TTS + LLM synthetic |
| Two-party speaker labels | ❌ FATAL | No speaker attribution provided |
| Segment-level labels | ❌ FATAL | Conversation-level only |
| Behavioral tactic labels | ❌ FATAL | Scenario/fraud type only |
| Human annotations | ❌ FATAL | LLM-generated (DeepSeek-R1) |
| Production licensing | ✅ MET | Apache 2.0 |
| Privacy | ✅ MET | Anonymized, no original data |

---

## Verdict

**TeleAntiFraud-28k is a legitimate, well-documented dataset with clear licensing. However, it is unsuitable for LUMINA due to:**
1. Wrong language (Chinese vs. English)
2. Synthetic data (TTS + LLM)
3. Wrong label type (conversation-level vs. segment-level)
4. No speaker attribution
5. No behavioral tactic annotations

**The dataset is valuable for Chinese telecom fraud research but cannot enter LUMINA's English behavioral classification pipeline.**
