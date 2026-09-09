# LUMINA ML — Real Two-Party Conversation Pilot Collection System

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Production-grade infrastructure for voluntary consent-based real-conversation pilot.
**Status:** INFRASTRUCTURE COMPLETE — AWAITING PARTICIPANTS

---

## Executive Summary

This document defines a complete, production-grade infrastructure for collecting real two-party conversations with explicit consent for LUMINA's behavioral ML pilot. The system is designed to:

1. Collect genuine two-party conversations with full consent
2. Maintain strict privacy and provenance
3. Support segment-level multi-label annotation
4. Enforce fail-closed acceptance gates
5. Never fabricate data, labels, or metrics

**Initial Target:** ≥50 real two-party conversations, ≥500 usable segments
**This is a pilot target, NOT a production sufficiency claim.**

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CONSENT LAYER                        │
│  Participant Consent → Recording Consent → ML Consent   │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                  COLLECTION LAYER                       │
│  User-Provided Recording | Authorized Research Recording │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                 PROVENANCE LAYER                        │
│  conversation_id | participant_id | timestamps | source │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                 SANITIZATION LAYER                      │
│  PII Detection | Secret Redaction | Privacy Filtering   │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│               TRANSCRIPTION LAYER                       │
│  STT Pipeline | Speaker Diarization | Confidence        │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│              ANNOTATION LAYER                           │
│  Segment-Level | Multi-Label | Human-Annotated          │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│               ACCEPTANCE GATE                           │
│  Consent | Provenance | Privacy | Two-Party | Labels    │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│              ML CANDIDATE POOL                          │
│  Real | Two-Party | Annotated | Sanitized | Split       │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Consent Model

### Consent Record Schema

```json
{
  "consent_id": "random-uuid",
  "participant_id": "random-identifier",
  "consent_version": "1.0",
  "consent_timestamp": "ISO 8601",
  "permissions": {
    "participation": true,
    "audio_recording": true,
    "speech_to_text": true,
    "behavioral_ml_annotation": true,
    "ml_model_training": true,
    "research_evaluation": true,
    "production_use": false,
    "anonymized_aggregate_reporting": true
  },
  "retention_period_days": 365,
  "withdrawal_mechanism": "email-or-in-app",
  "deletion_mechanism": "verified-deletion",
  "consent_obtained_before_recording": true,
  "consent_document_version": "1.0",
  "consent_document_hash": "sha256:..."
}
```

### Consent Rules

1. **No implied consent.** Every permission must be explicitly granted.
2. **No prechecked boxes.** All permissions default to false.
3. **No recording before consent.** Recording starts only after consent is valid.
4. **Separate permissions.** Each use case has its own consent toggle.
5. **Revocable.** Participants can withdraw consent at any time.
6. **Deletion.** Withdrawal triggers deletion of participant's pilot data.
7. **Versioned.** Consent documents are versioned and hashed.

### Withdrawal Process

1. Participant requests withdrawal (email or in-app)
2. System identifies all data linked to participant_id
3. Data is flagged as WITHDRAWN
4. Deletion is performed within 30 days
5. Deletion is verified and logged
6. Withdrawal is recorded in audit log

---

## 3. Participant Identifiers

### Rules
- Never use real name, phone, email, or government ID as training identifier
- Generate random participant_id (UUID v4)
- Generate random conversation_id (UUID v4)
- Separate identity metadata from research data
- Store linkage in encrypted, access-controlled system

### Identifier Schema

```json
{
  "participant_id": "uuid-v4",
  "created_at": "ISO 8601",
  "consent_id": "uuid-v4",
  "linkage_encrypted": true,
  "linkage_access_control": "admin-only"
}
```

---

## 4. Conversation Types

### Supported Types

| Type | Description | Training Eligible |
|------|-------------|-------------------|
| REAL_TWO_PARTY | Genuine two-party conversation | ✅ YES |
| ONE_SIDED | One speaker only | ❌ NO |
| ROLEPLAY | Controlled simulation | ❌ NO (separate pool) |
| SYNTHETIC | LLM/TTS generated | ❌ NO (excluded) |
| UNKNOWN | Provenance unclear | ❌ NO |

### Roleplay Handling
- Stored separately from real data
- Labeled ROLEPLAY in provenance
- Never enters real ML candidate pool
- May be used for system testing only

---

## 5. Audio Provenance

### Provenance Schema

```json
{
  "conversation_id": "uuid-v4",
  "participant_ids": ["uuid-v4", "uuid-v4"],
  "recording_timestamp": "ISO 8601",
  "recording_source": "USER_PROVIDED_RECORDING | AUTHORIZED_RESEARCH_RECORDING | CONTROLLED_ROLEPLAY | NOT_VERIFIED",
  "consent_version": "1.0",
  "consent_timestamp": "ISO 8601",
  "speaker_structure": "TWO_PARTY | ONE_SIDED | UNKNOWN",
  "language": "en",
  "audio_format": "wav",
  "sample_rate": 16000,
  "channel_count": 2,
  "processing_history": [],
  "retention_policy": "365_days",
  "deletion_status": "ACTIVE",
  "provenance_verified": true,
  "provenance_verified_by": "annotator_id",
  "provenance_verified_at": "ISO 8601"
}
```

### Recording Sources

| Source | Description | Eligible |
|--------|-------------|----------|
| USER_PROVIDED_RECORDING | Participant uploads existing recording | ✅ (if consent valid) |
| AUTHORIZED_RESEARCH_RECORDING | Recording made with LUMINA authorization | ✅ |
| CONTROLLED_ROLEPLAY | Simulated conversation for testing | ❌ (separate pool) |
| NOT_VERIFIED | Provenance unknown | ❌ |

---

## 6. Real Two-Party Requirements

### Classification Rules

| Property | Requirement |
|----------|-------------|
| Speaker count | ≥2 distinct speakers |
| Speaker roles | CALLER + RECIPIENT (at minimum) |
| Speaker attribution | Evidence-based (not inferred from text) |
| Conversation boundary | Start and end identifiable |
| Both parties consented | Verified consent for both parties |

### What Does NOT Qualify
- Single speaker (monologue)
- Microphone recording of one person
- Speaker-inferred-from-text (no audio evidence)
- Hidden cellular call recording
- Screen scraping
- AccessibilityService tricks
- Any bypass of Android privacy/security

---

## 7. Transcription Pipeline

### Requirements
- Use LUMINA's existing STT pipeline (Whisper-based)
- Record metadata:
  - transcription engine
  - model version
  - processing timestamp
  - language
  - confidence scores
  - audio hash
  - transcript hash
- Never treat ASR output as ground truth
- Original authorized audio remains source artifact

---

## 8. PII + Secret Sanitization

### Detection and Redaction

| Pattern | Redaction | Reversible? |
|---------|-----------|-------------|
| Names | [NAME_REDACTED] | Optional |
| Phone numbers | [PHONE_REDACTED] | Optional |
| Email addresses | [EMAIL_REDACTED] | Optional |
| Addresses | [ADDRESS_REDACTED] | Optional |
| OTPs | [OTP_REDACTED] | No |
| Passwords | [PASSWORD_REDACTED] | No |
| PINs | [PIN_REDACTED] | No |
| Card numbers | [CARD_REDACTED] | No |
| Bank accounts | [ACCOUNT_REDACTED] | No |
| Government IDs | [ID_DOC_REDACTED] | No |

### Storage Separation
- RAW_AUDIO: Original audio (encrypted, access-controlled)
- RAW_TRANSCRIPT: Unredacted transcript (encrypted, access-controlled)
- SANITIZED_TRANSCRIPT: Redacted transcript (for annotation/training)
- ANNOTATION_EXPORT: Fully sanitized (for ML training)

---

## 9. Annotation System

### LUMINA 11-Tactic Taxonomy

| # | Label | Description |
|---|-------|-------------|
| 1 | AUTHORITY_CLAIM | Speaker claims authority/institutional affiliation |
| 2 | THREAT_PRESENTATION | Negative consequences if non-compliant |
| 3 | TIME_PRESSURE | Urgency, deadlines, immediate action required |
| 4 | ISOLATION_TACTIC | Isolating from verification/trusted contacts |
| 5 | CREDENTIAL_REQUEST | Requesting OTPs, passwords, PINs |
| 6 | FINANCIAL_REQUEST | Requesting money, transfers, gift cards |
| 7 | REMOTE_ACCESS_REQUEST | Requesting software installation/screen sharing |
| 8 | IDENTITY_REQUEST | Requesting personal documents/information |
| 9 | BENIGN_CONVERSATION | Normal conversation, no tactics detected |
| 10 | USER_RESISTANCE | Recipient expressing refusal/skepticism |
| 11 | ADVICE_OR_WARNING | Safety guidance or security warnings |

### Annotation Requirements

| Property | Requirement |
|----------|-------------|
| Level | Segment-level (utterance) |
| Multi-label | Yes (multiple per segment) |
| Speaker-aware | Yes (CALLER/RECIPIENT/UNKNOWN) |
| Evidence-grounded | Yes (exact text span) |
| Human-created | Yes (LLM may suggest, human decides) |
| UNKNOWN allowed | Yes (uncertainty preserved) |

### Annotation Record

```json
{
  "segment_id": "uuid-v4",
  "conversation_id": "uuid-v4",
  "annotator_id": "annotator-uuid",
  "labels": [
    {
      "label": "AUTHORITY_CLAIM",
      "confidence": "HIGH",
      "evidence_span": "I am calling from the IRS",
      "annotation_timestamp": "ISO 8601",
      "annotation_version": "1.0"
    }
  ],
  "speaker": "CALLER",
  "adjudication_status": "PENDING | AGREED | ADJUDICATED",
  "adjudicator_id": null,
  "notes": ""
}
```

---

## 10. Acceptance Gate

### Conversation-Level Gate

A conversation enters the REAL ML CANDIDATE POOL only if ALL pass:

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Valid consent | consent_id exists, all permissions granted |
| 2 | Real audio | recording_source != SYNTHETIC |
| 3 | Two-party evidence | speaker_structure == TWO_PARTY |
| 4 | Caller + recipient | Both roles present |
| 5 | Provenance known | provenance_verified == true |
| 6 | English | language == "en" |
| 7 | Privacy satisfied | No unresolved PII issues |
| 8 | No synthetic contamination | recording_source != SYNTHETIC |
| 9 | Conversation boundary known | start/end identifiable |
| 10 | Usable transcript | transcript exists and non-empty |
| 11 | Speaker attribution sufficient | ≥80% segments have speaker labels |
| 12 | Withdrawal status valid | deletion_status == ACTIVE |

### Segment-Level Gate

A segment enters the training candidate pool only if:

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Parent conversation passes | conversation_id in candidate pool |
| 2 | Human annotation exists | annotation record present |
| 3 | Evidence span exists | evidence_span non-empty |
| 4 | Annotation version known | annotation_version present |
| 5 | No unresolved privacy issue | PII check passed |
| 6 | Split assigned | train/val/test assigned |
| 7 | Not withdrawn | deletion_status == ACTIVE |

---

## 11. Quality Dashboard

### Metrics (All start at 0)

| Metric | Value |
|--------|-------|
| Total conversations | 0 |
| Real two-party conversations | 0 |
| One-sided conversations | 0 |
| Roleplay conversations | 0 |
| Synthetic conversations | 0 |
| Unknown provenance | 0 |
| English conversations | 0 |
| Non-English conversations | 0 |
| Conversations with speaker attribution | 0 |
| Conversations with usable transcripts | 0 |
| Annotated segments | 0 |
| Unannotated segments | 0 |
| Segments per tactic | {} |
| Segments per speaker | {} |
| Withdrawn conversations | 0 |
| Excluded conversations | 0 |

---

## 12. Scientific Stop Conditions

After pilot reaches initial target (500 segments), evaluate:

| Criterion | Minimum | Target |
|-----------|---------|--------|
| Conversations | 50 | 100+ |
| Segments | 500 | 1,500+ |
| Per-tactic positives | 10 | 30+ |
| BENIGN coverage | 50 | 100+ |
| USER_RESISTANCE coverage | 15 | 30+ |
| ADVICE_OR_WARNING coverage | 10 | 20+ |
| Speaker balance | 30% minority | 40% minority |
| Annotation agreement (κ) | >0.5 | >0.7 |

### Possible Outcomes

| Outcome | Condition |
|---------|-----------|
| PILOT_READY | All criteria met |
| PILOT_INSUFFICIENT | Some criteria below minimum |
| PILOT_BLOCKED | Fundamental blocker (consent, privacy, provenance) |

---

## 13. Model Training Gate

**TRAINING_STATUS = NO_GO** until ALL are true:

1. Real pilot data exists (≥500 segments)
2. Consent valid for all participants
3. Provenance verified for all conversations
4. Privacy gate passes (no PII in training data)
5. Two-party requirement passes
6. Speaker structure passes (≥80% attributed)
7. Annotation quality passes (κ > 0.5)
8. Conversation-level split passes (no leakage)
9. Critical tactic coverage exists (≥10 per tactic)
10. Dataset diversity acceptable

Only then may a future phase train TF-IDF + LR baseline.

DeBERTa remains blocked until empirical evidence justifies it.

---

## 14. Files Created

### Documentation
- `docs/ml/REAL_PILOT_COLLECTION.md` (this file)
- `docs/ml/REAL_PILOT_CONSENT.md`
- `docs/ml/REAL_PILOT_DATA_CONTRACT.md`
- `docs/ml/REAL_PILOT_ACCEPTANCE.md`
- `docs/ml/REAL_PILOT_OPERATIONS.md`

### Scripts
- `scripts/ml/validate_real_pilot.py`
- `scripts/ml/build_pilot_manifest.py`
- `scripts/ml/split_real_pilot.py`

### Tests
- `tests/test_real_pilot_collection.py`

---

## 15. Hard Stop Compliance

**This document stops at infrastructure design. No actions taken:**
- ❌ No recordings collected
- ❌ No participants enrolled
- ❌ No data downloaded
- ❌ No models trained
- ❌ No synthetic data created
- ❌ No labels fabricated
- ❌ No metrics fabricated

**The system is designed to ACCEPT real data. It does NOT create data.**
