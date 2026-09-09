# LUMINA ML — Real Pilot Data Contract

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Data schema and contract for real pilot dataset.
**Status:** COMPLETE — Ready for data ingestion

---

## Overview

Every piece of data in the LUMINA real pilot must conform to this contract. Non-conforming data is rejected. This ensures reproducibility, provenance, and legal compliance.

---

## 1. Conversation Record

```json
{
  "conversation_id": "uuid-v4",
  "participant_ids": ["uuid-v4", "uuid-v4"],
  "consent_ids": ["uuid-v4", "uuid-v4"],
  "recording_timestamp": "ISO 8601",
  "recording_source": "USER_PROVIDED_RECORDING | AUTHORIZED_RESEARCH_RECORDING | CONTROLLED_ROLEPLAY | NOT_VERIFIED",
  "conversation_type": "REAL_TWO_PARTY | ONE_SIDED | ROLEPLAY | SYNTHETIC | UNKNOWN",
  "speaker_structure": "TWO_PARTY | ONE_SIDED | UNKNOWN",
  "language": "en",
  "audio_format": "wav",
  "sample_rate": 16000,
  "channel_count": 2,
  "duration_seconds": 120.5,
  "provenance": {
    "source": "string",
    "license": "string",
    "consent_status": "VERIFIED | PENDING | WITHDRAWN | UNKNOWN",
    "verified_by": "annotator-uuid",
    "verified_at": "ISO 8601"
  },
  "processing_history": [
    {
      "step": "recording",
      "timestamp": "ISO 8601",
      "engine": "string",
      "version": "string"
    }
  ],
  "retention_policy": "365_days",
  "deletion_status": "ACTIVE | WITHDRAWN | DELETED",
  "deletion_timestamp": null,
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601"
}
```

### Required Fields
- conversation_id
- participant_ids (≥2 for TWO_PARTY)
- consent_ids (≥2 for TWO_PARTY)
- recording_timestamp
- recording_source
- conversation_type
- speaker_structure
- language
- provenance
- deletion_status

### Validation Rules

| Field | Rule |
|-------|------|
| conversation_id | UUID v4 format |
| participant_ids | Array of UUID v4, length ≥2 for TWO_PARTY |
| consent_ids | Array of UUID v4, length ≥2 for TWO_PARTY |
| recording_source | Must be valid enum value |
| conversation_type | Must be valid enum value |
| speaker_structure | Must be valid enum value |
| language | Must be "en" for English |
| deletion_status | Must be "ACTIVE" for training candidates |

---

## 2. Segment Record

```json
{
  "segment_id": "uuid-v4",
  "conversation_id": "uuid-v4",
  "start_time": 0.0,
  "end_time": 3.5,
  "speaker": "CALLER | RECIPIENT | UNKNOWN",
  "text": "string (transcript text)",
  "text_hash": "sha256:...",
  "speaker_confidence": 0.95,
  "transcription_confidence": 0.88,
  "tactic_labels": [
    {
      "label": "AUTHORITY_CLAIM",
      "confidence": "HIGH | MEDIUM | LOW",
      "evidence_span": "I am calling from the IRS",
      "annotator_id": "annotator-uuid",
      "annotation_timestamp": "ISO 8601",
      "annotation_version": "1.0",
      "adjudication_status": "PENDING | AGREED | ADJUDICATED"
    }
  ],
  "conversation_phase": "SETUP | PRESSURE | EXTRACTION | RESISTANCE | ESCALATION | UNKNOWN",
  "segment_index": 0,
  "provenance": {
    "source": "string",
    "consent_status": "VERIFIED | PENDING | WITHDRAWN | UNKNOWN"
  },
  "sanitization_status": "SANITIZED | RAW | PENDING",
  "pii_check_passed": true,
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601"
}
```

### Required Fields
- segment_id
- conversation_id
- start_time
- end_time
- speaker (CALLER, RECIPIENT, or UNKNOWN)
- text (non-empty)
- tactic_labels (array, may be empty)
- provenance
- sanitization_status

### Validation Rules

| Field | Rule |
|-------|------|
| segment_id | UUID v4 format |
| conversation_id | Must exist in conversations table |
| start_time | ≥ 0, < end_time |
| end_time | > start_time |
| speaker | Must be CALLER, RECIPIENT, or UNKNOWN |
| text | Non-empty, ≤ 2000 characters |
| tactic_labels | Array of valid LUMINA labels |
| sanitization_status | Must be "SANITIZED" for training |

---

## 3. Annotation Record

```json
{
  "annotation_id": "uuid-v4",
  "segment_id": "uuid-v4",
  "conversation_id": "uuid-v4",
  "annotator_id": "annotator-uuid",
  "labels": [
    {
      "label": "AUTHORITY_CLAIM",
      "confidence": "HIGH",
      "evidence_span": "I am calling from the IRS",
      "rationale": "Optional explanation"
    }
  ],
  "annotation_timestamp": "ISO 8601",
  "annotation_version": "1.0",
  "adjudication_status": "PENDING | AGREED | ADJUDICATED",
  "adjudicator_id": null,
  "adjudication_timestamp": null,
  "adjudication_notes": "",
  "llm_suggestion_used": false,
  "llm_suggestion_accepted": null,
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601"
}
```

### Valid Labels

```python
LUMINA_LABELS = {
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

### Label Rules
- Labels must be from LUMINA_LABELS
- A segment can have 0 labels (use UNKNOWN if uncertain)
- A segment can have multiple labels (multi-label)
- BENIGN_CONVERSATION is exclusive (if any other label applies, BENIGN is not assigned)
- UNKNOWN is valid when annotator is uncertain
- Evidence span must be non-empty for each label
- Confidence must be HIGH, MEDIUM, or LOW

---

## 4. Consent Record

```json
{
  "consent_id": "uuid-v4",
  "participant_id": "uuid-v4",
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
  "consent_document_hash": "sha256:...",
  "withdrawal_mechanism": "email-or-in-app",
  "deletion_mechanism": "verified-deletion",
  "age_confirmed_over_18": true,
  "jurisdiction": "US",
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601"
}
```

### Required Fields
- consent_id
- participant_id
- consent_timestamp
- All permissions (must be boolean)
- consent_document_hash
- age_confirmed_over_18 (must be true)

---

## 5. Dataset Manifest

```json
{
  "manifest_id": "uuid-v4",
  "dataset_version": "pilot-v0.1",
  "schema_version": "1.0",
  "taxonomy_version": "1.0",
  "consent_version": "1.0",
  "sanitization_version": "1.0",
  "annotation_version": "1.0",
  "split_version": "1.0",
  "created_at": "ISO 8601",
  "created_by": "system",
  "total_conversations": 0,
  "total_segments": 0,
  "real_two_party_conversations": 0,
  "annotated_segments": 0,
  "label_distribution": {},
  "split_distribution": {
    "train": 0,
    "validation": 0,
    "test": 0
  },
  "provenance_registry": [],
  "acceptance_status": "PENDING | ACCEPTED | REJECTED",
  "training_status": "NO_GO | CONDITIONAL_GO | GO",
  "checksums": {}
}
```

---

## 6. Split Record

```json
{
  "split_id": "uuid-v4",
  "dataset_version": "pilot-v0.1",
  "seed": 42,
  "train_ratio": 0.8,
  "val_ratio": 0.1,
  "test_ratio": 0.1,
  "split_algorithm": "conversation-level",
  "train_conversations": [],
  "val_conversations": [],
  "test_conversations": [],
  "train_segments": 0,
  "val_segments": 0,
  "test_segments": 0,
  "leakage_check_passed": true,
  "created_at": "ISO 8601"
}
```

---

## 7. File Formats

| File | Format | Description |
|------|--------|-------------|
| conversations.jsonl | JSONL | One conversation per line |
| segments.jsonl | JSONL | One segment per line |
| annotations.jsonl | JSONL | One annotation per line |
| consents.jsonl | JSONL | One consent per line |
| manifest.json | JSON | Dataset manifest |
| split.json | JSON | Split configuration |
| checksums.json | JSON | SHA-256 checksums |

---

## 8. Validation Rules Summary

### Conversation Validation
- conversation_id: UUID v4
- participant_ids: ≥2 for TWO_PARTY
- consent_ids: ≥2 for TWO_PARTY
- recording_source: valid enum
- conversation_type: valid enum
- speaker_structure: valid enum
- language: "en"
- deletion_status: "ACTIVE"

### Segment Validation
- segment_id: UUID v4
- conversation_id: exists
- start_time: ≥ 0
- end_time: > start_time
- speaker: CALLER/RECIPIENT/UNKNOWN
- text: non-empty, ≤ 2000 chars
- sanitization_status: "SANITIZED"

### Annotation Validation
- annotation_id: UUID v4
- segment_id: exists
- annotator_id: present
- labels: valid LUMINA labels
- evidence_span: non-empty per label
- confidence: HIGH/MEDIUM/LOW

### Consent Validation
- consent_id: UUID v4
- participant_id: UUID v4
- consent_timestamp: valid ISO 8601
- All permissions: boolean
- age_confirmed_over_18: true
