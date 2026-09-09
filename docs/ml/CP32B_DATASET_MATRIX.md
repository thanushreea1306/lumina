# LUMINA ML — CP-32B Dataset Admission Matrix

**Document Version:** 1.0  
**Created:** 2026-09-08  
**Purpose:** Hard-gate scoring for each dataset candidate  
**Status:** Gate matrix — not a training authorization

---

## Gate Definitions

Each gate must be one of:
- **PASS** — Requirement fully met
- **PARTIAL** — Requirement partially met; limitation recorded
- **FAIL** — Requirement not met; disqualifying
- **UNKNOWN** — Cannot determine from available information

A dataset with a FAIL on any critical gate cannot be approved for production model training.

### Critical Gates
- REAL_AUDIO
- REAL_CONVERSATION
- TWO_PARTY
- TACTIC_RELEVANCE
- COMMERCIAL_TRAINING_RIGHTS
- PRIVACY_CONSENT
- SUFFICIENT_SCALE

### Important Gates
- SPEAKER_ATTRIBUTION
- SEGMENT_LABELS
- LABEL_PROVENANCE
- TIMESTAMPS

---

## Candidate Matrix

### 1. FTC / NCSU Robocall Audio Dataset

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | PASS | Real robocall recordings from FTC PPoNE material |
| REAL_CONVERSATION | PASS | Real robocall interactions |
| TWO_PARTY | FAIL | Primarily one-sided caller audio; local-side track not transcribed |
| TACTIC_RELEVANCE | PARTIAL | Real suspected illegal robocall material, but not interactive scam dialogue |
| COMMERCIAL_TRAINING_RIGHTS | PASS | Public domain data |
| PRIVACY_CONSENT | PARTIAL | Public-domain robocall material; still audio that may be sensitive |
| SUFFICIENT_SCALE | PASS | Large corpus available |
| SPEAKER_ATTRIBUTION | PARTIAL | Caller-side audio identifiable; two-party attribution limited |
| SEGMENT_LABELS | FAIL | No segment-level tactic annotation |
| LABEL_PROVENANCE | FAIL | No labels exist |
| TIMESTAMPS | PARTIAL | Audio timestamps available |

**Classification:** REJECTED  
**Primary Failure:** TWO_PARTY + SEGMENT_LABELS

---

### 2. TeleAntiFraud-28k

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | FAIL | Built partly from real-call ASR material, then largely TTS-generated |
| REAL_CONVERSATION | FAIL | Synthetic/TTS pipeline |
| TWO_PARTY | PARTIAL | Two-channel dialog structure exists, but derived from synthetic pipeline |
| TACTIC_RELEVANCE | PARTIAL | Telecom fraud topics covered, but not cleanly real human scam dialogs |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | Not verified from primary source review |
| PRIVACY_CONSENT | PARTIAL | Real-call ASR source material raises privacy concerns |
| SUFFICIENT_SCALE | PASS | 28k conversations |
| SPEAKER_ATTRIBUTION | PARTIAL | Caller/callee roles constructed in pipeline |
| SEGMENT_LABELS | PARTIAL | Slow-thinking annotations exist; not LUMINA tactic labels |
| LABEL_PROVENANCE | UNKNOWN | Not verified |
| TIMESTAMPS | UNKNOWN | Not verified |

**Classification:** REJECTED  
**Primary Failure:** REAL_AUDIO + REAL_CONVERSATION (synthetic/TTS)

---

### 3. BothBosu synthetic scam datasets

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | FAIL | Synthetic agent-generated dialogues |
| REAL_CONVERSATION | FAIL | Two-agent synthetic dialogs |
| TWO_PARTY | FAIL | Two-agent synthetic dialogs |
| TACTIC_RELEVANCE | PARTIAL | Scam/non-scam topics, but synthetic |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | Apache 2.0 per one dataset README, but dataset is synthetic |
| PRIVACY_CONSENT | PARTIAL | Synthetic content reduces some privacy risk |
| SUFFICIENT_SCALE | PASS | Multiple datasets available |
| SPEAKER_ATTRIBUTION | FAIL | Synthetic roles, not real people |
| SEGMENT_LABELS | FAIL | Binary scam/non-scam labels, not LUMINA tactics |
| LABEL_PROVENANCE | FAIL | Synthetic labels |
| TIMESTAMPS | UNKNOWN | Not verified |

**Classification:** REJECTED  
**Primary Failure:** REAL_AUDIO + REAL_CONVERSATION (explicitly synthetic)

---

### 4. Zenodo Scam Conversation Corpus (15212527)

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | PARTIAL | Media folder may contain scam-supplied multimedia |
| REAL_CONVERSATION | FAIL | Victim side is GPT-4o facilitated |
| TWO_PARTY | PARTIAL | Conversations involve scammer side and GPT-4o-facilitated victim side |
| TACTIC_RELEVANCE | PARTIAL | Captures scammer-side behavior |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | Restricted access; not verified |
| PRIVACY_CONSENT | PARTIAL | Restricted and pseudonymized identifiers |
| SUFFICIENT_SCALE | UNKNOWN | Not verified from accessible record |
| SPEAKER_ATTRIBUTION | PARTIAL | Anonymized identifiers, but victim side is LLM-facilitated |
| SEGMENT_LABELS | FAIL | No LUMINA tactic labels |
| LABEL_PROVENANCE | FAIL | No labels exist |
| TIMESTAMPS | UNKNOWN | Not verified |

**Classification:** REJECTED  
**Primary Failure:** REAL_CONVERSATION (LLM-facilitated victim side)

---

### 5. Zenodo Multiclass NLP Dataset (15235123)

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | FAIL | Text messages, no phone audio |
| REAL_CONVERSATION | FAIL | Email/SMS-like messages, not conversations |
| TWO_PARTY | FAIL | Not phone conversations |
| TACTIC_RELEVANCE | PARTIAL | Phishing/social engineering topics |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | Not verified |
| PRIVACY_CONSENT | PARTIAL | Described as anonymized |
| SUFFICIENT_SCALE | FAIL | 624 messages; too small |
| SPEAKER_ATTRIBUTION | FAIL | Not phone speaker attribution |
| SEGMENT_LABELS | FAIL | Category labels, not LUMINA tactics |
| LABEL_PROVENANCE | FAIL | No tactic labels |
| TIMESTAMPS | UNKNOWN | Not verified |

**Classification:** REJECTED  
**Primary Failure:** REAL_AUDIO + REAL_CONVERSATION + SUFFICIENT_SCALE

---

### 6. Shen et al. real-time detection paper dataset lineage

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | PARTIAL | Real-world transcripts derived from public video audio |
| REAL_CONVERSATION | PARTIAL | Scammer and victim speech transcribed from public videos |
| TWO_PARTY | PARTIAL | Scammer and victim sides present |
| TACTIC_RELEVANCE | PARTIAL | Phone scam transcripts |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | Not verified |
| PRIVACY_CONSENT | PARTIAL | Public video-derived transcripts |
| SUFFICIENT_SCALE | UNKNOWN | Not verified |
| SPEAKER_ATTRIBUTION | PARTIAL | Scammer/victim sides in transcripts |
| SEGMENT_LABELS | FAIL | Fraud/safe labels, not LUMINA tactics |
| LABEL_PROVENANCE | FAIL | Binary labels only |
| TIMESTAMPS | UNKNOWN | Not verified |

**Classification:** REJECTED  
**Primary Failure:** LANGUAGE_MISMATCH (Chinese) + SEGMENT_LABELS

---

### 7. D-STAR scam/non-scam transcript set

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | FAIL | Text transcripts |
| REAL_CONVERSATION | PARTIAL | Transcripts may include two sides |
| TWO_PARTY | PARTIAL | Transcripts may show both sides |
| TACTIC_RELEVANCE | PARTIAL | Scam/non-scam framing |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | Not verified |
| PRIVACY_CONSENT | UNKNOWN | Not verified |
| SUFFICIENT_SCALE | FAIL | 800 transcripts; too small |
| SPEAKER_ATTRIBUTION | UNKNOWN | Not verified |
| SEGMENT_LABELS | FAIL | Category labels only |
| LABEL_PROVENANCE | FAIL | No tactic labels |
| TIMESTAMPS | UNKNOWN | Not verified |

**Classification:** REJECTED  
**Primary Failure:** SUFFICIENT_SCALE + SEGMENT_LABELS

---

### 8. Kaggle "Call Transcripts Scam Determinations"

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | FAIL | Transcripts |
| REAL_CONVERSATION | PARTIAL | Transcripts may show both sides |
| TWO_PARTY | PARTIAL | Transcripts may show both sides |
| TACTIC_RELEVANCE | PARTIAL | Scam/not-scam labels |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | License not verified |
| PRIVACY_CONSENT | UNKNOWN | Not verified |
| SUFFICIENT_SCALE | FAIL | 60 calls; too small |
| SPEAKER_ATTRIBUTION | UNKNOWN | Not verified |
| SEGMENT_LABELS | FAIL | Binary labels only |
| LABEL_PROVENANCE | FAIL | No tactic labels |
| TIMESTAMPS | UNKNOWN | Not verified |

**Classification:** REJECTED  
**Primary Failure:** SUFFICIENT_SCALE + SEGMENT_LABELS

---

### 9. Kaggle "Scam and Non-Scam Call Conversation Dataset"

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | FAIL | Transcript text |
| REAL_CONVERSATION | PARTIAL | Two-sided call transcripts |
| TWO_PARTY | PARTIAL | Two-sided call transcripts |
| TACTIC_RELEVANCE | PARTIAL | Scam/non-scam topic |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | License/source not verified |
| PRIVACY_CONSENT | UNKNOWN | Not verified |
| SUFFICIENT_SCALE | UNKNOWN | Not verified |
| SPEAKER_ATTRIBUTION | UNKNOWN | Not verified |
| SEGMENT_LABELS | FAIL | Binary labels only |
| LABEL_PROVENANCE | FAIL | No tactic labels |
| TIMESTAMPS | UNKNOWN | Not verified |

**Classification:** REJECTED  
**Primary Failure:** SEGMENT_LABELS + UNVERIFIED_PROVENANCE

---

### 10. Mendeley ASLC-448

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | FAIL | Audio is TTS-generated |
| REAL_CONVERSATION | FAIL | Simulated conversations |
| TWO_PARTY | PARTIAL | Simulated caller/receiver turns |
| TACTIC_RELEVANCE | PARTIAL | Scam topics in Arabic |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | Not verified |
| PRIVACY_CONSENT | PARTIAL | Synthetic/TTS material reduces some risk |
| SUFFICIENT_SCALE | FAIL | 448 conversations; too small |
| SPEAKER_ATTRIBUTION | FAIL | Simulated, not real speakers |
| SEGMENT_LABELS | PARTIAL | Risk scores and categories exist, not LUMINA tactics |
| LABEL_PROVENANCE | FAIL | No LUMINA tactic labels |
| TIMESTAMPS | UNKNOWN | Not verified |

**Classification:** REJECTED  
**Primary Failure:** REAL_AUDIO + REAL_CONVERSATION + WRONG_LANGUAGE

---

### 11. Anatomy of a Scam Call honeypot corpus

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | PASS | Real inbound scam/spam call audio |
| REAL_CONVERSATION | PARTIAL | Real scammer side; recipient side is AI voice agent |
| TWO_PARTY | PARTIAL | Real two-party dialogue, but recipient is AI |
| TACTIC_RELEVANCE | PASS | Real scam and spam calls at scale |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | Access and exact terms not verified |
| PRIVACY_CONSENT | PARTIAL | Real inbound fraud calls; access path unresolved |
| SUFFICIENT_SCALE | PASS | 10,211 calls, 913 hours, 330,956 turns |
| SPEAKER_ATTRIBUTION | PARTIAL | Scammer side is real; recipient side is AI agent |
| SEGMENT_LABELS | FAIL | Machine-generated silver labels, not human LUMINA tactic annotations |
| LABEL_PROVENANCE | FAIL | No human-annotated LUMINA tactic labels |
| TIMESTAMPS | PASS | Turn-level timestamps available |

**Classification:** CONDITIONAL (closest to passing, but blockers remain)  
**Blockers:** ACCESS_RIGHTS + RECIPIENT_AI + SEGMENT_LABELS

---

### 12. Open Yap 1K

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | UNKNOWN | Not evaluated in this pass |
| REAL_CONVERSATION | UNKNOWN | Not evaluated in this pass |
| TWO_PARTY | UNKNOWN | Not evaluated in this pass |
| TACTIC_RELEVANCE | UNKNOWN | Not evaluated in this pass |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | Not evaluated in this pass |
| PRIVACY_CONSENT | UNKNOWN | Not evaluated in this pass |
| SUFFICIENT_SCALE | UNKNOWN | Not evaluated in this pass |
| SPEAKER_ATTRIBUTION | UNKNOWN | Not evaluated in this pass |
| SEGMENT_LABELS | UNKNOWN | Not evaluated in this pass |
| LABEL_PROVENANCE | UNKNOWN | Not evaluated in this pass |
| TIMESTAMPS | UNKNOWN | Not evaluated in this pass |

**Classification:** UNRESOLVED  
**Blocker:** Not evaluated; requires dedicated investigation

---

### 13. BYU-PCCL

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | UNKNOWN | Not evaluated in this pass |
| REAL_CONVERSATION | UNKNOWN | Not evaluated in this pass |
| TWO_PARTY | UNKNOWN | Not evaluated in this pass |
| TACTIC_RELEVANCE | UNKNOWN | Not evaluated in this pass |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | Not evaluated in this pass |
| PRIVACY_CONSENT | UNKNOWN | Not evaluated in this pass |
| SUFFICIENT_SCALE | UNKNOWN | Not evaluated in this pass |
| SPEAKER_ATTRIBUTION | UNKNOWN | Not evaluated in this pass |
| SEGMENT_LABELS | UNKNOWN | Not evaluated in this pass |
| LABEL_PROVENANCE | UNKNOWN | Not evaluated in this pass |
| TIMESTAMPS | UNKNOWN | Not evaluated in this pass |

**Classification:** UNRESOLVED  
**Blocker:** Not evaluated; requires dedicated investigation

---

### 14. YouTube Scam Transcripts

| Gate | Status | Note |
|------|--------|------|
| REAL_AUDIO | UNKNOWN | Not evaluated in this pass |
| REAL_CONVERSATION | UNKNOWN | Not evaluated in this pass |
| TWO_PARTY | UNKNOWN | Not evaluated in this pass |
| TACTIC_RELEVANCE | UNKNOWN | Not evaluated in this pass |
| COMMERCIAL_TRAINING_RIGHTS | UNKNOWN | Not evaluated in this pass |
| PRIVACY_CONSENT | UNKNOWN | Not evaluated in this pass |
| SUFFICIENT_SCALE | UNKNOWN | Not evaluated in this pass |
| SPEAKER_ATTRIBUTION | UNKNOWN | Not evaluated in this pass |
| SEGMENT_LABELS | UNKNOWN | Not evaluated in this pass |
| LABEL_PROVENANCE | UNKNOWN | Not evaluated in this pass |
| TIMESTAMPS | UNKNOWN | Not evaluated in this pass |

**Classification:** UNRESOLVED  
**Blocker:** Not evaluated; requires dedicated investigation

---

## Summary

| Classification | Count | Candidates |
|----------------|-------|------------|
| REJECTED | 11 | FTC/NCSU, TeleAntiFraud, BothBosu, Zenodo SCC, Zenodo NLP, Shen et al., D-STAR, Kaggle Mealss, Kaggle Teeconnie, Mendeley ASLC-448, ScamGen/Korean |
| CONDITIONAL | 1 | Anatomy of a Scam Call honeypot |
| UNRESOLVED | 3 | Open Yap 1K, BYU-PCCL, YouTube Scam Transcripts |
| PRIMARY_TRAINING_CANDIDATE | 0 | None |

**Final Decision:** NO_GO
