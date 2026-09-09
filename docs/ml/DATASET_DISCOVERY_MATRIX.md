# LUMINA ML — Dataset Discovery Admission Matrix

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Scoring matrix for each serious candidate in the real scam conversation discovery pass.  
**Status:** Discovery matrix — not a training authorization

---

## Reading the matrix

Values:

- `YES`
- `PARTIAL`
- `NO`
- `UNKNOWN`
- `NOT_VERIFIED`

Unknown or not-verified fields are not upgraded to `YES`.

---

## Candidate rows

### 1. FTC / NCSU Robocall Audio Dataset

| Dimension | Value | Note |
|-----------|-------|------|
| REAL_AUDIO | YES | Real robocall recordings from FTC PPoNE material |
| REAL_TWO_PARTY | NO | Primarily one-sided caller audio; local-side track not transcribed |
| REAL_VICTIM_BEHAVIOR | NO | Does not provide real victim dialogue behavior |
| ENGLISH | PARTIAL | Majority English; some Mandarin according to repo |
| SCAM_RELEVANCE | PARTIAL | Real suspected illegal robocall material, but not interactive scam dialogue |
| BENIGN_RELEVANCE | NO | Not a benign natural-conversation corpus |
| SEGMENTABLE | PARTIAL | Audio exists; segment-level tactic labels do not |
| SPEAKER_ATTRIBUTION | PARTIAL | Caller-side audio identifiable; two-party attribution limited |
| TACTIC_ANNOTATION | NO | No segment-level tactic annotation in the public corpus |
| COMMERCIAL_ML | YES | Public domain data |
| DERIVATIVE_ANNOTATION | UNKNOWN | Depends on downstream use; not verified for LUMINA |
| PRIVACY | PARTIAL | Public-domain robocall material; still audio that may be sensitive |
| PROVENANCE | YES | FTC PPoNE lineage documented in repo materials |
| OVERALL | RED | Real but one-sided; not the missing victim-behavior signal |

---

### 2. TeleAntiFraud-28k

| Dimension | Value | Note |
|-----------|-------|------|
| REAL_AUDIO | PARTIAL | Built partly from real-call ASR material, then largely TTS-generated |
| REAL_TWO_PARTY | PARTIAL | Two-channel dialog structure exists, but derived from synthetic pipeline |
| REAL_VICTIM_BEHAVIOR | NO | Victim/callee side is synthetic/TTS/imitation-generated |
| ENGLISH | PARTIAL | Paper describes multilingual and synthetic pipeline work |
| SCAM_RELEVANCE | PARTIAL | Telecom fraud topics covered, but not cleanly real human scam dialogs |
| BENIGN_RELEVANCE | PARTIAL | Includes normal-call material in the pipeline |
| SEGMENTABLE | UNKNOWN | Not verified from primary source review |
| SPEAKER_ATTRIBUTION | PARTIAL | Caller/callee roles constructed in pipeline |
| TACTIC_ANNOTATION | PARTIAL | Slow-thinking annotations exist; not LUMINA tactic labels |
| COMMERCIAL_ML | NOT_VERIFIED | Not verified from primary source review for LUMINA |
| DERIVATIVE_ANNOTATION | NOT_VERIFIED | Not verified for LUMINA |
| PRIVACY | PARTIAL | Real-call ASR source material raises privacy concerns |
| PROVENANCE | PARTIAL | Described in paper, but mixed synthetic and real |
| OVERALL | RED | Synthetic/TTS contamination is disqualifying under current non-negotiables |

---

### 3. BothBosu synthetic scam datasets

| Dimension | Value | Note |
|-----------|-------|------|
| REAL_AUDIO | NO | Synthetic agent-generated dialogues |
| REAL_TWO_PARTY | NO | Two-agent synthetic dialogs |
| REAL_VICTIM_BEHAVIOR | NO | Innocent receiver is a synthetic agent personality |
| ENGLISH | PARTIAL | English-language synthetic dialogs |
| SCAM_RELEVANCE | PARTIAL | Scam/non-scam topics, but synthetic |
| BENIGN_RELEVANCE | PARTIAL | Includes non-scam synthetic dialogs |
| SEGMENTABLE | NO | Not a real conversation corpus |
| SPEAKER_ATTRIBUTION | NO | Synthetic roles, not real people |
| TACTIC_ANNOTATION | NO | Binary scam/non-scam labels, not LUMINA tactics |
| COMMERCIAL_ML | NOT_VERIFIED | Apache 2.0 per one dataset README, but dataset is synthetic |
| DERIVATIVE_ANNOTATION | NOT_VERIFIED | Not relevant enough; still synthetic |
| PRIVACY | PARTIAL | Synthetic content reduces some privacy risk, but does not make it real data |
| PROVENANCE | PARTIAL | Source is BothBosu synthetic generation pipeline |
| OVERALL | RED | Explicitly synthetic; violates non-negotiables |

---

### 4. Zenodo Scam Conversation Corpus (`15212527`)

| Dimension | Value | Note |
|-----------|-------|------|
| REAL_AUDIO | PARTIAL | Media folder may contain scam-supplied multimedia; not a clear real phone-call victim audio corpus from record review |
| REAL_TWO_PARTY | PARTIAL | Conversations involve scammer side and GPT-4o-facilitated victim side |
| REAL_VICTIM_BEHAVIOR | NO | Victim side is described as GPT-4o facilitated; not real human victim behavior |
| ENGLISH | PARTIAL | Multi-platform; language mix not confirmed at scale |
| SCAM_RELEVANCE | PARTIAL | Captures scammer-side behavior |
| BENIGN_RELEVANCE | NO | Not a benign corpus |
| SEGMENTABLE | UNKNOWN | Not verified from accessible record review |
| SPEAKER_ATTRIBUTION | PARTIAL | Anonymized identifiers, but victim side is LLM-facilitated |
| TACTIC_ANNOTATION | NO | No LUMINA tactic labels established from accessible record |
| COMMERCIAL_ML | NOT_VERIFIED | Restricted access; not verified for LUMINA |
| DERIVATIVE_ANNOTATION | NOT_VERIFIED | Not verified for LUMINA |
| PRIVACY | PARTIAL | Restricted and pseudonymized identifiers, but content may still be sensitive |
| PROVENANCE | PARTIAL | Thesis and Zenodo record document creation method |
| OVERALL | RED | Not clearly admissible; not a real human victim phone conversation corpus from materials reviewed |

---

### 5. Zenodo Multiclass NLP Dataset (`15235123`)

| Dimension | Value | Note |
|-----------|-------|------|
| REAL_AUDIO | NO | Text messages, no phone audio |
| REAL_TWO_PARTY | NO | Email/SMS-like messages |
| REAL_VICTIM_BEHAVIOR | NO | Not phone scam victim dialogue |
| ENGLISH | YES | English messages |
| SCAM_RELEVANCE | PARTIAL | Phishing/social engineering topics |
| BENIGN_RELEVANCE | PARTIAL | Includes NOT-Malicious class |
| SEGMENTABLE | NO | Too small and wrong modality |
| SPEAKER_ATTRIBUTION | NO | Not phone speaker attribution |
| TACTIC_ANNOTATION | NO | Category labels, not LUMINA tactics |
| COMMERCIAL_ML | NOT_VERIFIED | Not verified for LUMINA |
| DERIVATIVE_ANNOTATION | NOT_VERIFIED | Not verified for LUMINA |
| PRIVACY | PARTIAL | Described as anonymized |
| PROVENANCE | PARTIAL | Zenodo record documents source |
| OVERALL | RED | Wrong modality, too small, not phone scam two-party audio |

---

### 6. Shen et al. real-time detection paper dataset lineage

| Dimension | Value | Note |
|-----------|-------|------|
| REAL_AUDIO | PARTIAL | Real-world transcripts derived from public video audio |
| REAL_TWO_PARTY | PARTIAL | Scammer and victim speech transcribed from public videos |
| REAL_VICTIM_BEHAVIOR | PARTIAL | Real victim speech may be present, but source lineage is indirect |
| ENGLISH | NO | Paper says datasets were in Chinese |
| SCAM_RELEVANCE | PARTIAL | Phone scam transcripts |
| BENIGN_RELEVANCE | PARTIAL | Includes normal calls |
| SEGMENTABLE | NO | Not a LUMINA-ready tactic corpus |
| SPEAKER_ATTRIBUTION | PARTIAL | Scammer/victim sides in transcripts |
| TACTIC_ANNOTATION | NO | Fraud/safe labels, not LUMINA tactics |
| COMMERCIAL_ML | NOT_VERIFIED | Not verified for LUMINA |
| DERIVATIVE_ANNOTATION | NOT_VERIFIED | Not verified for LUMINA |
| PRIVACY | PARTIAL | Public video-derived transcripts may still carry concerns |
| PROVENANCE | PARTIAL | Paper describes source type |
| OVERALL | RED | Language mismatch and indirect source lineage |

---

### 7. D-STAR scam/non-scam transcript set

| Dimension | Value | Note |
|-----------|-------|------|
| REAL_AUDIO | NO | Text transcripts |
| REAL_TWO_PARTY | PARTIAL | Transcripts may include two sides |
| REAL_VICTIM_BEHAVIOR | UNKNOWN | Source lineage too weak to verify from materials reviewed |
| ENGLISH | PARTIAL | Unclear from accessible record |
| SCAM_RELEVANCE | PARTIAL | Scam/non-scam framing |
| BENIGN_RELEVANCE | PARTIAL | Includes non-scam calls |
| SEGMENTABLE | NO | Not tactic-annotated in accessible record |
| SPEAKER_ATTRIBUTION | UNKNOWN | Not verified |
| TACTIC_ANNOTATION | NO | Category labels only |
| COMMERCIAL_ML | NOT_VERIFIED | Not verified for LUMINA |
| DERIVATIVE_ANNOTATION | NOT_VERIFIED | Not verified for LUMINA |
| PRIVACY | UNKNOWN | Not verified |
| PROVENANCE | PARTIAL | Publicly available sources cited, but not fully traceable here |
| OVERALL | RED | Source certainty and modality insufficient |

---

### 8. Kaggle “Call Transcripts Scam Determinations”

| Dimension | Value | Note |
|-----------|-------|------|
| REAL_AUDIO | NO | Transcripts |
| REAL_TWO_PARTY | PARTIAL | Transcripts may show both sides |
| REAL_VICTIM_BEHAVIOR | UNKNOWN | Too small and provenance too weak to verify |
| ENGLISH | PARTIAL | Likely English but not verified from primary review |
| SCAM_RELEVANCE | PARTIAL | Scam/not-scam labels |
| BENIGN_RELEVANCE | PARTIAL | Includes non-scam calls |
| SEGMENTABLE | NO | 60 calls; too small |
| SPEAKER_ATTRIBUTION | UNKNOWN | Not verified |
| TACTIC_ANNOTATION | NO | Binary labels only |
| COMMERCIAL_ML | NOT_VERIFIED | License not verified from primary review |
| DERIVATIVE_ANNOTATION | NOT_VERIFIED | Not verified for LUMINA |
| PRIVACY | UNKNOWN | Not verified |
| PROVENANCE | PARTIAL | Kaggle page only |
| OVERALL | RED | Too small and insufficiently verified |

---

### 9. Kaggle “Scam and Non-Scam Call Conversation Dataset”

| Dimension | Value | Note |
|-----------|-------|------|
| REAL_AUDIO | NO | Transcript text |
| REAL_TWO_PARTY | PARTIAL | Two-sided call transcripts |
| REAL_VICTIM_BEHAVIOR | UNKNOWN | Source certainty too weak from materials reviewed |
| ENGLISH | PARTIAL | English framing |
| SCAM_RELEVANCE | PARTIAL | Scam/non-scam topic |
| BENIGN_RELEVANCE | PARTIAL | Includes non-scam calls |
| SEGMENTABLE | NO | Not tactic annotated in accessible record |
| SPEAKER_ATTRIBUTION | UNKNOWN | Not verified |
| TACTIC_ANNOTATION | NO | Binary labels only |
| COMMERCIAL_ML | NOT_VERIFIED | License/source not verified for LUMINA |
| DERIVATIVE_ANNOTATION | NOT_VERIFIED | Not verified for LUMINA |
| PRIVACY | UNKNOWN | Not verified |
| PROVENANCE | PARTIAL | Kaggle page and citation trail only |
| OVERALL | RED | Insufficient source-level certainty |

---

### 10. Mendeley ASLC-448

| Dimension | Value | Note |
|-----------|-------|------|
| REAL_AUDIO | NO | Audio is TTS-generated |
| REAL_TWO_PARTY | PARTIAL | Simulated caller/receiver turns |
| REAL_VICTIM_BEHAVIOR | NO | Simulated recipients and TTS audio |
| ENGLISH | NO | Arabic dialects |
| SCAM_RELEVANCE | PARTIAL | Scam topics in Arabic |
| BENIGN_RELEVANCE | PARTIAL | Includes legitimate-call simulation |
| SEGMENTABLE | UNKNOWN | Not verified for LUMINA |
| SPEAKER_ATTRIBUTION | NO | Simulated, not real speakers |
| TACTIC_ANNOTATION | PARTIAL | Risk scores and categories exist, not LUMINA tactics |
| COMMERCIAL_ML | NOT_VERIFIED | Not verified for LUMINA |
| DERIVATIVE_ANNOTATION | NOT_VERIFIED | Not verified for LUMINA |
| PRIVACY | PARTIAL | Synthetic/TTS material reduces some risk but not relevant enough |
| PROVENANCE | PARTIAL | Mendeley record documents construction |
| OVERALL | RED | Wrong language and TTS audio |

---

### 11. Anatomy of a Scam Call honeypot corpus

| Dimension | Value | Note |
|-----------|-------|------|
| REAL_AUDIO | YES | Real inbound scam/spam call audio recorded by honeypot |
| REAL_TWO_PARTY | YES | Real two-party dialogue between scammer and answered line |
| REAL_VICTIM_BEHAVIOR | NO | Recipient side is AI voice agent, not real human victim |
| ENGLISH | PARTIAL | Dominantly English real calls expected, but not fully verified from accessible materials |
| SCAM_RELEVANCE | YES | Real scam and spam calls at scale |
| BENIGN_RELEVANCE | PARTIAL | Includes some legitimate/gray traffic in taxonomy design, but main corpus is unsolicited inbound |
| SEGMENTABLE | PARTIAL | Turns exist; LUMINA tactic labels do not |
| SPEAKER_ATTRIBUTION | PARTIAL | Scammer side is real; recipient side is AI agent |
| TACTIC_ANNOTATION | NO | Machine-generated silver labels, not human LUMINA tactic annotations |
| COMMERCIAL_ML | NOT_VERIFIED | Access and exact terms not verified from materials reviewed |
| DERIVATIVE_ANNOTATION | NOT_VERIFIED | Not verified for LUMINA |
| PRIVACY | PARTIAL | Real inbound fraud calls may carry sensitive content; access path unresolved |
| PROVENANCE | YES | Paper and referenced companion descriptor document the construction |
| OVERALL | YELLOW | Strongest real-scam lead, but victim side is AI, access/rights not verified, not human-victim two-party audio yet |

---

## Final matrix verdict

| Verdict | Meaning |
|---------|---------|
| GREEN | None found in this pass |
| YELLOW | Anatomy of a Scam Call honeypot corpus, conditional on access/rights and victim-side interpretation |
| RED | All other serious candidates in this pass |

**Overall board:**

- GO: no
- CONDITIONAL_GO: possible future path around the honeypot corpus only if access/rights/privacy/realism are confirmed
- NO_GO now: yes
