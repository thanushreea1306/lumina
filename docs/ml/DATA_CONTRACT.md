# LUMINA ML — Data Contract

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Define exactly what one training example must contain.  
**Status:** FINAL

---

## Overview

Every training example in LUMINA's ML pipeline must conform to this contract. Non-conforming examples are rejected. This ensures reproducibility, provenance, and legal compliance.

---

## Required Fields

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `conversation_id` | string | Unique identifier for the conversation | Non-empty, globally unique |
| `segment_id` | string | Unique identifier for this segment | Non-empty, unique within conversation |
| `text` | string | The transcript segment text | Non-empty, 1-2000 characters, PII-filtered |
| `tactic_labels` | list[string] | Multi-label tactic annotations | Non-empty, subset of LUMINA_LABELS |
| `speaker` | string | Who is speaking | One of: "CALLER", "USER", "UNKNOWN" |
| `provenance` | object | Data provenance record | See Provenance Schema |
| `consent_status` | string | Consent/license status | One of: "PUBLIC_DOMAIN", "LICENSED", "CONSENTED" |
| `annotation_status` | string | Annotation quality status | One of: "ANNOTATED", "ADJUDICATED", "PROVISIONAL" |

---

## Optional Fields

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `timestamp_start` | float | Segment start time (seconds from call start) | ≥0 or null |
| `timestamp_end` | float | Segment end time (seconds from call start) | > timestamp_start or null |
| `conversation_phase` | string | Phase label | One of: "SETUP", "PRESSURE", "EXTRACTION", "RESISTANCE", "ESCALATION" or null |
| `source` | string | Data source identifier | Free text |
| `annotator_id` | string | Pseudonymous annotator identifier | Non-empty if annotation_status is "ANNOTATED" |
| `annotation_confidence` | float | Annotator confidence | 0.0-1.0 or null |
| `rationale` | string | Annotator rationale for labels | Free text or null |
| `metadata` | object | Additional metadata | Arbitrary key-value pairs |

---

## Allowed Values

### tactic_labels

The following labels are allowed (subset of TacticLabel taxonomy):

```python
ALLOWED_LABELS = {
    "AUTHORITY_CLAIM",
    "THREAT_PRESENTATION",
    "TIME_PRESSURE",
    "ISOLATION_TACTIC",
    "CREDENTIAL_REQUEST",
    "FINANCIAL_REQUEST",
    "REMOTE_ACCESS_REQUEST",
    "IDENTITY_REQUEST",
    "BENIGN_CONVERSATION",
    "USER_RESISTANCE",
    "ADVICE_OR_WARNING",
}
```

**Rules:**
- At least one label required
- Multiple labels allowed (multi-label)
- "UNKNOWN" is NOT a valid training label (it's a fallback, not a training target)
- Labels must be from the allowed set

### speaker

```python
ALLOWED_SPEAKERS = {"CALLER", "USER", "UNKNOWN"}
```

### consent_status

```python
ALLOWED_CONSENT = {"PUBLIC_DOMAIN", "LICENSED", "CONSENTED"}
```

### annotation_status

```python
ALLOWED_ANNOTATION = {"ANNOTATED", "ADJUDICATED", "PROVISIONAL"}
```

- `ANNOTATED`: Single annotator labeled
- `ADJUDICATED`: Multiple annotators agreed or resolved
- `PROVISIONAL`: Label pending review

---

## Privacy Requirements

### PII Detection and Redaction

The following patterns MUST be detected and redacted before storage:

| Pattern | Redaction | Example |
|---------|-----------|---------|
| Phone numbers | `[PHONE]` | 555-123-4567 → [PHONE] |
| Email addresses | `[EMAIL]` | user@example.com → [EMAIL] |
| SSN-like patterns | `[SSN]` | 123-45-6789 → [SSN] |
| Credit card numbers | `[CARD]` | 4111-1111-1111-1111 → [CARD] |
| Aadhaar numbers | `[ID_NUMBER]` | 1234 5678 9012 → [ID_NUMBER] |
| OTP/PIN codes | `[OTP_REDACTED]` | otp: 123456 → otp: [OTP_REDACTED] |
| Passwords | `[SECRET_REDACTED]` | password: secret123 → password: [SECRET_REDACTED] |
| Bank account numbers | `[ACCOUNT_REDACTED]` | account: 1234567890 → account: [ACCOUNT_REDACTED] |

### Storage Requirements

- Raw audio MUST NOT be stored in the training dataset
- Only text transcripts are stored
- PII is redacted before storage
- Training data is SEPARATE from operational incident data
- No user incident data is used without explicit consent

---

## Provenance Schema

Every training example must include a provenance record:

```json
{
  "source_name": "ftc_robocall_ppone",
  "source_url": "https://github.com/wspr-ncsu/robocall-audio-dataset",
  "license": "public_domain",
  "commercial_use": true,
  "training_use": true,
  "language": "en",
  "modality": "audio_transcript",
  "download_date": "2026-09-07",
  "verification_status": "VERIFIED",
  "annotation_date": "2026-09-07",
  "annotation_version": "1.0"
}
```

---

## Annotation Requirements

### Minimum Requirements

- At least 1 annotator per segment
- For ADJUDICATED status: at least 2 annotators
- Inter-annotator agreement target: Cohen's kappa > 0.7
- Annotators must complete training on LUMINA's tactic taxonomy
- Annotators must sign confidentiality agreement

### Quality Control

- Random 10% of segments reviewed by senior annotator
- Disagreements resolved by adjudication
- Annotation audit trail maintained

---

## Exclusion Rules

A segment MUST be excluded if:

1. Text is empty or whitespace-only
2. Text contains unredacted PII
3. Text is a prompt injection attempt
4. Text is in a non-English language
5. Text is synthetic/LLM-generated
6. Text is from a scam-baiting interaction (simulated victim)
7. No annotator has reviewed the segment
8. consent_status is unknown and source is not public domain
9. Text length exceeds 2000 characters
10. Text is a duplicate of another segment (same conversation)

---

## Train/Validation/Test Split Rules

### Split Ratios

- **Train:** 80% of conversations
- **Validation:** 10% of conversations
- **Test:** 10% of conversations

### Split Requirements

1. **Conversation-level splitting:** No conversation appears in multiple splits
2. **Deterministic:** Same seed produces same split
3. **Stratified:** Label distribution roughly consistent across splits
4. **No leakage:** No text overlap between splits
5. **Frozen:** Once frozen, splits never change

### Split Procedure

1. Group segments by conversation_id
2. Shuffle conversations deterministically (seed=42)
3. Assign conversations to train/val/test
4. Verify no conversation overlap
5. Compute label distribution per split
6. Freeze and record manifest

---

## Example Record

```json
{
  "conversation_id": "ftc_ppone_00142",
  "segment_id": "ftc_ppone_00142_seg_03",
  "text": "This is the Social Security Administration. Your social security number has been suspended due to suspicious activity.",
  "tactic_labels": ["AUTHORITY_CLAIM", "THREAT_PRESENTATION"],
  "speaker": "CALLER",
  "timestamp_start": 12.5,
  "timestamp_end": 18.2,
  "conversation_phase": "SETUP",
  "source": "ftc_robocall_ppone",
  "provenance": {
    "source_name": "ftc_robocall_ppone",
    "source_url": "https://github.com/wspr-ncsu/robocall-audio-dataset",
    "license": "public_domain",
    "commercial_use": true,
    "training_use": true,
    "language": "en",
    "modality": "audio_transcript",
    "download_date": "2026-09-07",
    "verification_status": "VERIFIED"
  },
  "consent_status": "PUBLIC_DOMAIN",
  "annotation_status": "ADJUDICATED",
  "annotator_id": "annotator_07",
  "annotation_confidence": 0.9,
  "rationale": "Caller claims SSA authority and implies threat of suspension."
}
```
