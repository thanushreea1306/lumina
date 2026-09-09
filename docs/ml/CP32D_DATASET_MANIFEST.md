# LUMINA ML — CP-32D Dataset Manifest

**Document Version:** 1.0
**Created:** 2026-09-08
**Phase:** CP-32D
**Status:** MANIFEST FORMAT DEFINED — MANIFEST IS EMPTY

---

## 1. Purpose

The dataset manifest is the machine-readable register of every record considered for
training. It is the single artifact a future training harness may consume. If a record is
not in a manifest with every critical gate PASS, it cannot be trained on. The manifest is
**empty** after CP-32D — nothing exists to put in it.

---

## 2. Provenance Metadata (immutable)

Each record carries immutable provenance metadata. Once written, provenance fields are
never edited; corrections create a new record version.

| Field | Description |
|-------|-------------|
| `dataset_version` | Semantic version of the dataset this record belongs to |
| `record_id` | Globally unique record identifier |
| `source_type` | e.g., `CONSENTED_PILOT_CONTRIBUTION` |
| `source_origin` | Where the conversation came from (mechanism, not identity) |
| `consent_version` | Consent document version the participant signed |
| `license_version` | License/terms version governing the contribution |
| `processing_pipeline_version` | Version of the CP-32D privacy/processing pipeline |
| `stt_model_version` | Exact STT model that produced the transcript |
| `annotation_guideline_version` | Version of `CP32D_ANNOTATION_GUIDE.md` in force |
| `annotator_versions` | Annotator ID → guideline/training version mapping |
| `privacy_review_version` | Version of the privacy review procedure |
| `created_at` | Record creation timestamp (ISO-8601 UTC) |
| `updated_at` | Record last-update timestamp (ISO-8601 UTC) |

Rules:

- Provenance fields are mandatory. A record with any missing provenance field fails the
  PROVENANCE gate (status `UNKNOWN`), which blocks entry.
- Do not store raw secrets. Provenance contains hashes and versions, never keys.
- Do not store participant identity. `participant_id` is pseudonymous; real identity, if
  operationally unavoidable, lives outside the dataset artifact set.

---

## 3. Manifest Entry Format

```json
{
  "record_id": "uuid-v4",
  "conversation_id": "uuid-v4",
  "license_status": "LICENSED|CONSENTED|NOT_VERIFIED|RESTRICTED",
  "consent_status": "CONSENT_GRANTED|CONSENT_PENDING|CONSENT_WITHDRAWN|CONSENT_EXPIRED|CONSENT_INVALID",
  "privacy_status": "PII_CLEARED|PII_REVIEW_REQUIRED|PII_REDACTED|PII_REJECTED",
  "annotation_status": "ANNOTATED|ADJUDICATED|NOT_ANNOTATED|ANNOTATION_IN_PROGRESS",
  "quality_status": "PASS|PARTIAL|FAIL|UNKNOWN",
  "withdrawal_status": "NONE|WITHDRAWAL_REQUESTED|WITHDRAWAL_CONFIRMED|DATA_DELETED|DERIVED_DATA_HANDLED",
  "split": "TRAIN|VALIDATION|TEST|UNASSIGNED",
  "provenance_hash": "sha256:... over the immutable provenance block"
}
```

`provenance_hash` is computed over the canonical serialization of the provenance block so
that any later tampering with provenance is detectable.

---

## 4. Critical-Gate Enforcement

**A record must not enter a training manifest unless every critical gate passes.**

A record enters the manifest only with:

```
consent_status     == CONSENT_GRANTED
privacy_status     == PII_CLEARED
annotation_status  == ANNOTATED or ADJUDICATED (dual-annotated, adjudicated where needed)
quality_status     == PASS
withdrawal_status  == NONE
license_status     == LICENSED or CONSENTED (with verified training rights)
split              == TRAIN | VALIDATION | TEST (assigned only per CP-32D split rules)
provenance_hash    present
```

Any other combination is an error: tooling must refuse to write such an entry, and tests
in `tests/test_cp32d_data_governance.py` enforce the same rules.

---

## 5. Tamper Evidence

- `provenance_hash` covers the provenance block; a mismatch invalidates the record.
- Manifest writes are append-only; corrections are new record versions, never edits.
- The manifest itself records `processing_pipeline_version` so future readers know exactly
  which rules produced it.

---

## 6. Current State

```
MANIFEST RECORDS = 0
```

This is the honest state after CP-32D. No entry may be created until real consented,
privacy-cleared, dual-annotated, gate-passing data exists.
