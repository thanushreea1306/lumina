# LUMINA ML — Label Mapping Analysis

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Map LUMINA's TacticLabel taxonomy to available datasets and assess label coverage.  
**Status:** INSUFFICIENT — No dataset provides segment-level multi-label tactic annotations.

---

## LUMINA's TacticLabel Taxonomy

These labels are defined in `app/incident/ml_intelligence.py` and represent the target classification output:

```python
class TacticLabel(str, Enum):
    AUTHORITY_CLAIM = "AUTHORITY_CLAIM"
    THREAT_PRESENTATION = "THREAT_PRESENTATION"
    TIME_PRESSURE = "TIME_PRESSURE"
    ISOLATION_TACTIC = "ISOLATION_TACTIC"
    CREDENTIAL_REQUEST = "CREDENTIAL_REQUEST"
    FINANCIAL_REQUEST = "FINANCIAL_REQUEST"
    REMOTE_ACCESS_REQUEST = "REMOTE_ACCESS_REQUEST"
    IDENTITY_REQUEST = "IDENTITY_REQUEST"
    BENIGN_CONVERSATION = "BENIGN_CONVERSATION"
    USER_RESISTANCE = "USER_RESISTANCE"
    ADVICE_OR_WARNING = "ADVICE_OR_WARNING"
    UNKNOWN = "UNKNOWN"
```

**Key Requirements:**
- **Segment-level:** Labels apply to individual utterances/segments, not entire conversations
- **Multi-label:** A single segment may contain multiple tactics (e.g., authority claim + threat)
- **Behavioral:** Labels describe observed behavior, not intent or outcome

---

## Label-by-Label Analysis

### 1. AUTHORITY_CLAIM

| Property | Value |
|----------|-------|
| **Definition** | Caller claims authority (police, bank, government, court, agency) |
| **Available Evidence** | Keyword patterns: "police", "bank", "government", "court", "department", "agency", "cyber", "crime", "tax", "income" |
| **Datasets Containing It** | None with explicit labels |
| **Number of Examples** | 0 labeled examples |
| **Annotation Quality** | N/A |
| **Usable for Supervised Learning** | **NO** |
| **Gap** | No dataset provides segment-level "authority claim" labels. Derakhshan's "scam type" labels are conversation-level. Wood et al.'s topic model identifies authority themes but not segment labels. |

### 2. THREAT_PRESENTATION

| Property | Value |
|----------|-------|
| **Definition** | Caller presents threats (arrest, legal action, penalties, detention) |
| **Available Evidence** | Keyword patterns: "arrest", "jail", "warrant", "legal", "court", "sue", "fine", "penalty", "detain" |
| **Datasets Containing It** | None with explicit labels |
| **Number of Examples** | 0 labeled examples |
| **Annotation Quality** | N/A |
| **Usable for Supervised Learning** | **NO** |
| **Gap** | No dataset provides segment-level "threat" labels. Social security scams in Wood et al. contain threats but are labeled as scam type, not tactic. |

### 3. TIME_PRESSURE

| Property | Value |
|----------|-------|
| **Definition** | Caller creates urgency (time limits, "now", "immediately", "running out") |
| **Available Evidence** | Keyword patterns: "now", "immediately", "hurry", "quickly", "minutes", "seconds", "running out", "last chance", "final warning" |
| **Datasets Containing It** | None with explicit labels |
| **Number of Examples** | 0 labeled examples |
| **Annotation Quality** | N/A |
| **Usable for Supervised Learning** | **NO** |
| **Gap** | No dataset provides segment-level urgency labels. Wood et al. identify urgency in topic modeling but not as explicit labels. |

### 4. ISOLATION_TACTIC

| Property | Value |
|----------|-------|
| **Definition** | Caller isolates victim (secrecy requests, blocking verification) |
| **Available Evidence** | Keyword patterns: "secret", "confidential", "private", "don't tell", "do not tell", "no one should know", "between us" |
| **Datasets Containing It** | None with explicit labels |
| **Number of Examples** | 0 labeled examples |
| **Annotation Quality** | N/A |
| **Usable for Supervised Learning** | **NO** |
| **Gap** | No dataset provides segment-level isolation labels. This is a subtle tactic that requires expert annotation. |

### 5. CREDENTIAL_REQUEST

| Property | Value |
|----------|-------|
| **Definition** | Caller requests credentials (OTP, passwords, PINs, verification codes) |
| **Available Evidence** | Keyword patterns: "otp", "code", "verification", "one-time", "pin", "password", "passwd", "pwd", "secret answer" |
| **Datasets Containing It** | None with explicit labels |
| **Number of Examples** | 0 labeled examples |
| **Annotation Quality** | N/A |
| **Usable for Supervised Learning** | **NO** |
| **Gap** | No dataset provides segment-level credential request labels. Some datasets contain OTP mentions but without explicit annotation. |

### 6. FINANCIAL_REQUEST

| Property | Value |
|----------|-------|
| **Definition** | Caller requests money (transfers, payments, gift cards, crypto) |
| **Available Evidence** | Keyword patterns: "money", "transfer", "payment", "fee", "fine", "deposit", "send", "pay" |
| **Datasets Containing It** | Composite Scam Transcript Dataset (CC BY-NC — cannot use) |
| **Number of Examples** | ~46,982 (but license prohibits use) |
| **Annotation Quality** | Unknown |
| **Usable for Supervised Learning** | **NO** (license restriction) |
| **Gap** | The largest dataset with financial content is CC BY-NC. No open-license dataset provides segment-level financial request labels. |

### 7. REMOTE_ACCESS_REQUEST

| Property | Value |
|----------|-------|
| **Definition** | Caller requests remote access (software installation, screen sharing) |
| **Available Evidence** | Keyword patterns: "install", "download", "app", "software", "teamviewer", "anydesk", "screen sharing", "remote" |
| **Datasets Containing It** | None with explicit labels |
| **Number of Examples** | 0 labeled examples |
| **Annotation Quality** | N/A |
| **Usable for Supervised Learning** | **NO** |
| **Gap** | No dataset provides segment-level remote access request labels. This is specific to tech support scams. |

### 8. IDENTITY_REQUEST

| Property | Value |
|----------|-------|
| **Definition** | Caller requests identity documents (Aadhaar, PAN, passport, ID, license) |
| **Available Evidence** | Keyword patterns: "aadhaar", "pan", "passport", "id", "document", "license" |
| **Datasets Containing It** | None with explicit labels |
| **Number of Examples** | 0 labeled examples |
| **Annotation Quality** | N/A |
| **Usable for Supervised Learning** | **NO** |
| **Gap** | No dataset provides segment-level identity request labels. This is region-specific (Aadhaar = India). |

### 9. BENIGN_CONVERSATION

| Property | Value |
|----------|-------|
| **Definition** | Normal conversation without social engineering tactics |
| **Available Evidence** | Absence of other tactic indicators |
| **Datasets Containing It** | Kaggle: Call Transcripts (60 calls); Derakhshan (140 non-scam); various non-scam datasets |
| **Number of Examples** | ~445 (60 + 140 + 140 + 105 from various sources) |
| **Annotation Quality** | Low (binary "non-scam" label) |
| **Usable for Supervised Learning** | **PARTIAL** — binary non-scam label exists but not segment-level |
| **Gap** | Non-scam data exists but is conversation-level binary, not segment-level multi-label. Benign segments within scam conversations are not labeled. |

### 10. USER_RESISTANCE

| Property | Value |
|----------|-------|
| **Definition** | User expresses resistance, refusal, or pushback |
| **Available Evidence** | Negation patterns + user speaker attribution |
| **Datasets Containing It** | Scam baiting transcripts (baiters resist, but deliberately) |
| **Number of Examples** | 0 labeled examples |
| **Annotation Quality** | N/A |
| **Usable for Supervised Learning** | **NO** |
| **Gap** | Scam baiting resistance is deliberately deceptive (baiting), not genuine victim resistance. No dataset contains genuine victim resistance labels. |

### 11. ADVICE_OR_WARNING

| Property | Value |
|----------|-------|
| **Definition** | Speaker provides advice or warnings (could be caller or user) |
| **Available Evidence** | Keywords: "never share", "do not share", "warning", "be careful", "remember" |
| **Datasets Containing It** | None with explicit labels |
| **Number of Examples** | 0 labeled examples |
| **Annotation Quality** | N/A |
| **Usable for Supervised Learning** | **NO** |
| **Gap** | No dataset provides segment-level advice/warning labels. This label is uncommon in scam calls. |

### 12. UNKNOWN

| Property | Value |
|----------|-------|
| **Definition** | Unable to classify the segment |
| **Available Evidence** | Default/uncertain classification |
| **Datasets Containing It** | All datasets (implicit) |
| **Number of Examples** | N/A |
| **Annotation Quality** | N/A |
| **Usable for Supervised Learning** | **NO** (catch-all label) |
| **Gap** | This is a fallback label, not a training target. |

---

## Coverage Summary

| Label | Dataset Coverage | Examples Available | Usable for Training |
|-------|-----------------|-------------------|---------------------|
| AUTHORITY_CLAIM | None | 0 | NO |
| THREAT_PRESENTATION | None | 0 | NO |
| TIME_PRESSURE | None | 0 | NO |
| ISOLATION_TACTIC | None | 0 | NO |
| CREDENTIAL_REQUEST | None | 0 | NO |
| FINANCIAL_REQUEST | CC BY-NC (cannot use) | ~46,982 (blocked) | NO |
| REMOTE_ACCESS_REQUEST | None | 0 | NO |
| IDENTITY_REQUEST | None | 0 | NO |
| BENIGN_CONVERSATION | Partial (binary) | ~445 (conversation-level) | NO |
| USER_RESISTANCE | None (baiting ≠ genuine) | 0 | NO |
| ADVICE_OR_WARNING | None | 0 | NO |
| UNKNOWN | All (implicit) | N/A | NO |

**Total Usable Labeled Segments: 0**

---

## Feasible Alternatives

### Option A: Binary Scam/Non-Scam Classification

If the initial supervised task were reduced to **binary classification** (scam vs. non-scam at the conversation level):

| Dataset | Size | License | Notes |
|---------|------|---------|-------|
| Kaggle: Call Transcripts | 60 | Unknown | Too small |
| Derakhshan | 215 | Unknown | Simulated |
| YouTube Scam Transcripts | 243 | Unknown | Scam baiting |
| **Total** | **518** | **Mixed** | **Still insufficient for deep learning** |

**Verdict:** Even binary classification is not feasible with current public data at the scale needed for DeBERTa training.

### Option B: Transfer Learning with Existing Text Classification Models

Using a pre-trained DeBERTa-v3-base without fine-tuning on scam-specific data:

- **Pros:** Can leverage general language understanding
- **Cons:** No domain-specific learning; deterministic baseline may outperform
- **Verdict:** Not a replacement for supervised training; only useful as feature extractor

### Option C: Future Dataset Creation

To enable supervised training, LUMINA would need to create a custom dataset:

1. **Collect** real phone call transcripts (with appropriate consent/licensing)
2. **Annotate** at segment level with multi-label tactic annotations
3. **Validate** annotation quality with inter-annotator agreement
4. **Release** with appropriate license for production use

**Estimated requirements:**
- Minimum 5,000 labeled segments (10,000+ preferred)
- At least 3 expert annotators
- Inter-annotator agreement > 0.7 Cohen's kappa
- Clear licensing for production use
- Domain expertise in social engineering tactics

---

## Recommendation

**DO NOT reduce the initial supervised task to a subset of labels.**

The fundamental blocker is not label granularity — it is the complete absence of segment-level multi-label annotated data for social engineering tactics in phone conversations.

**The deterministic safety engine must remain the sole decision authority.**

ML cannot contribute meaningfully to LUMINA's safety function until a legitimate, sufficiently large, properly annotated dataset exists. The current deterministic baseline (keyword rules) provides reliable, transparent, and auditable behavior that ML cannot replace without real training data.
