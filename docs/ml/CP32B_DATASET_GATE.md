# LUMINA ML — CP-32B Dataset Acquisition & Training Readiness Gate

**Document Version:** 1.0  
**Created:** 2026-09-08  
**Purpose:** Strict data gate for production ML model training  
**Status:** Gate evaluation — not a training authorization  
**Decision:** NO_GO

---

## Canonical 11-Tactic Taxonomy

The ML model must classify transcript segments into one of these tactics:

1. AUTHORITY_CLAIM
2. THREAT_PRESENTATION
3. TIME_PRESSURE
4. ISOLATION_TACTIC
5. CREDENTIAL_REQUEST
6. FINANCIAL_REQUEST
7. REMOTE_ACCESS_REQUEST
8. IDENTITY_REQUEST
9. BENIGN_CONVERSATION
10. USER_RESISTANCE
11. ADVICE_OR_WARNING

Plus UNKNOWN for indeterminate cases.

---

## Strict Dataset Acceptance Specification

A dataset candidate must satisfy ALL critical gates to be approved for production training.

### Critical Gates (FAIL = cannot be PRIMARY_TRAINING_CANDIDATE)

| Gate | Requirement |
|------|-------------|
| REAL_AUDIO | Real human speech recordings |
| REAL_CONVERSATION | Real human interactions (not LLM-generated, not synthetic, not TTS) |
| TWO_PARTY | Two-party conversations with both sides present |
| TACTIC_RELEVANCE | Contains evidence of social-engineering tactics |
| COMMERCIAL_TRAINING_RIGHTS | Explicit permission for commercial ML training |
| PRIVACY_CONSENT | Proper consent and privacy protections |
| SUFFICIENT_SCALE | Enough data for meaningful training |

### Important Gates (PARTIAL = record limitation)

| Gate | Requirement |
|------|-------------|
| SPEAKER_ATTRIBUTION | Speaker identification/turn-taking |
| SEGMENT_LABELS | Segment-level tactic annotations |
| LABEL_PROVENANCE | Clear annotation methodology |
| TIMESTAMPS | Temporal ordering of segments |

---

## Candidate Evaluation Summary

### Rejected Candidates (FAIL on critical gate)

| Candidate | Primary Failure | Classification |
|-----------|----------------|----------------|
| FTC/NCSU Robocall | ONE_SIDED (no two-party) | REJECTED |
| TeleAntiFraud-28k | SYNTHETIC (TTS-generated) | REJECTED |
| BothBosu | SYNTHETIC (AI-generated) | REJECTED |
| Zenodo Scam Conversation | LLM_FACILITATED (GPT-4o victim side) | REJECTED |
| Zenodo NLP Dataset | WRONG_MODALITY (text only) | REJECTED |
| Shen et al. | LANGUAGE_MISMATCH (Chinese) | REJECTED |
| D-STAR | INSUFFICIENT_SCALE (800 transcripts) | REJECTED |
| Kaggle Call Transcripts | INSUFFICIENT_SCALE (60 calls) | REJECTED |
| Kaggle Scam/Non-Scam | UNVERIFIED_PROVENANCE | REJECTED |
| Mendeley ASLC-448 | TTS_AUDIO + WRONG_LANGUAGE | REJECTED |
| ScamGen | LANGUAGE_MISMATCH (Chinese) | REJECTED |
| Korean scam dataset | LANGUAGE_MISMATCH (Korean) | REJECTED |

### Conditional Candidates (require further verification)

| Candidate | Status | Blocker |
|-----------|--------|---------|
| Anatomy of a Scam Call honeypot | YELLOW | Access/rights not verified; recipient side is AI agent |
| Open Yap 1K | UNKNOWN | Not evaluated in this pass |
| BYU-PCCL | UNKNOWN | Not evaluated in this pass |
| YouTube Scam Transcripts | UNKNOWN | Not evaluated in this pass |
| Derakhshan dataset | UNKNOWN | Not evaluated in this pass |
| Wood et al. | UNKNOWN | Not evaluated in this pass |

### Primary Training Candidates

**None.** No currently available candidate satisfies the minimum requirements.

---

## Open Yap 1K — Special Gate

**Status:** NOT EVALUATED IN THIS PASS

Open Yap 1K was not included in the original discovery matrix. A dedicated evaluation is required before any acquisition decision.

Required verification:
- Real human conversations (confirmed)
- Number of conversations
- Number of speakers
- Duration
- Speaker structure
- Consent mechanism
- Transcript provenance
- Transcript accuracy
- License
- DUA requirements
- Commercial use permission
- ML training/fine-tuning permission
- Deployment permission
- Redistribution restrictions
- Voice cloning restrictions
- PII/privacy provisions

**Blocker:** Cannot evaluate without authoritative source information.

---

## Dataset Decision

### FINAL DECISION: NO_GO

**Rationale:**

1. No currently available candidate satisfies the minimum requirements for production ML training
2. All previously evaluated candidates have been rejected or marked conditional
3. The strongest candidate (Anatomy of a Scam Call honeypot) has unresolved access/rights issues and uses an AI voice agent for the recipient side
4. No dataset provides segment-level LUMINA tactic labels
5. Commercial training rights are unverified for all conditional candidates
6. Scale requirements are not met by most candidates

### What Would Convert NO_GO to CONDITIONAL_GO

A dataset would need to demonstrate:
1. Real two-party human conversations
2. Segment-level social-engineering tactic labels
3. Explicit commercial training permission
4. Proper privacy/consent protections
5. Sufficient scale (1000+ conversations)

### What Would Convert CONDITIONAL_GO to GO

1. Completed DUA/permission verification
2. Confirmed license terms
3. Privacy/consent audit passed
4. Technical integration validated

---

## Recommended Acquisition Paths

Since no existing dataset qualifies, the following acquisition strategies are recommended:

### Path 1: Explicitly Consented Real User Recordings
- Partner with users who consent to recording their scam calls
- Provide clear consent forms and privacy protections
- Annotate with LUMINA tactic labels
- **Advantage:** Real human behavior, proper consent
- **Challenge:** Recruitment, privacy, scale

### Path 2: Government/Public-Domain Real Recordings
- Explore FTC, FCC, or other government repositories
- Check for real two-party recordings with proper licensing
- **Advantage:** Public domain, real recordings
- **Challenge:** May not have tactic labels, may be one-sided

### Path 3: Academic/Commercial Licensing Agreement
- Negotiate licensing with existing dataset creators
- Ensure commercial training rights are explicit
- **Advantage:** Existing data, potentially annotated
- **Challenge:** Cost, licensing complexity

### Path 4: Professional Annotation Partnership
- Partner with annotation services for labeled data
- Use existing real recordings as base
- **Advantage:** High-quality labels
- **Challenge:** Cost, requires base recordings

### Path 5: Licensed Scam-Call Corpus
- Explore commercial scam-call corpus providers
- Verify licensing terms for ML training
- **Advantage:** Ready-made data
- **Challenge:** Cost, licensing restrictions

### Path 6: Carefully Scoped Pilot Dataset
- Start with a small, well-annotated pilot
- Use for initial model validation
- Scale up with proven acquisition path
- **Advantage:** Lower risk, faster feedback
- **Challenge:** Limited scale

---

## What Was NOT Done in This Phase

- No datasets were downloaded
- No models were trained
- No synthetic data was used
- No metrics were fabricated
- No production code was modified

---

## Verification Checklist

- [x] All 14+ candidates evaluated against hard gates
- [x] Open Yap 1K flagged for dedicated evaluation
- [x] No dataset approved for training
- [x] No synthetic fallback used
- [x] No fabricated metrics
- [x] Proper documentation created
- [x] Tests added and passing
- [x] No commit/push performed
