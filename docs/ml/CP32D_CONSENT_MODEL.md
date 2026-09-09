# LUMINA ML — CP-32D Consent Model

**Document Version:** 1.0
**Created:** 2026-09-08
**Phase:** CP-32D
**Status:** PROTOCOL DEFINED — NO PARTICIPANTS ENROLLED
**Supersedes:** `REAL_PILOT_CONSENT.md` (retained for history; conflicts resolve in favor of this document)

---

## Core Principle

**Consent for recording does NOT imply consent for ML training.** Every use is a separate,
explicit, granular permission with its own default of `false`. No prechecked boxes. No
implied consent. No bundling.

---

## 1. Consent Record Schema (versioned)

```json
{
  "consent_id": "uuid-v4",
  "participant_id": "pseudonymous-uuid-v4",
  "conversation_ids": ["uuid-v4", "..."],
  "consent_version": "1.0",
  "consent_document_hash": "sha256:...",
  "consent_timestamp": "ISO-8601-UTC",
  "consent_obtained_before_recording": true,
  "permissions": {
    "recording": false,
    "transcription": false,
    "annotation": false,
    "ml_training": false,
    "model_evaluation": false,
    "deployment": false,
    "research_use": false,
    "product_use": false,
    "voice_retention": false,
    "derived_transcript_retention": false
  },
  "retention_period_days": 365,
  "withdrawal_mechanism": "in-app-or-email",
  "deletion_mechanism": "verified-deletion",
  "age_confirmed_over_18": true,
  "jurisdiction": "recorded-at-enrollment"
}
```

Field rules:

- `consent_version` is a semantic version. Any change to the consent document requires a
  new version and a new signed record. Old records keep their old version.
- `consent_document_hash` binds the record to the exact text the participant agreed to.
- `participant_id` is pseudonymous. Real identity, if operationally unavoidable (e.g., a
  withdrawal request email), is stored outside the dataset artifact set with its own
  access policy (see `CP32D_PRIVACY_PIPELINE.md` §8).
- The record must never contain passwords, OTPs, PINs, card numbers, government IDs, or
  other authentication secrets.

### Permission Definitions

| Permission | Covers |
|------------|--------|
| `recording` | Capture or acceptance of participant audio |
| `transcription` | STT processing of that audio |
| `annotation` | Human annotators reading and labeling transcript segments |
| `ml_training` | Use of derived artifacts to train models |
| `model_evaluation` | Use in validation/test measurement |
| `deployment` | Use in models that ship to production |
| `research_use` | Academic/internal research reporting |
| `product_use` | Product improvement beyond a specific model |
| `voice_retention` | Retaining voice-bearing audio after processing |
| `derived_transcript_retention` | Retaining anonymized transcripts/annotations |

Defaults are all `false`. A record with any permission the workflow needs set to `false`
is not eligible for that use — silently widening permissions is prohibited.

---

## 2. Consent States

```
CONSENT_PENDING    — record created, participant has not completed the flow
CONSENT_GRANTED    — all required permissions explicitly granted, document hash recorded
CONSENT_WITHDRAWN  — participant exercised withdrawal; processing stops
CONSENT_EXPIRED    — retention period elapsed without renewal
CONSENT_INVALID    — failed verification (age, coercion indication, hash mismatch, corrupt record)
```

Transitions:

```
CONSENT_PENDING  → CONSENT_GRANTED      (explicit completion, hash verified)
CONSENT_GRANTED  → CONSENT_WITHDRAWN    (participant request, verified)
CONSENT_GRANTED  → CONSENT_EXPIRED      (retention elapsed)
any state        → CONSENT_INVALID      (verification failure; terminal pending review)
CONSENT_WITHDRAWN / EXPIRED / INVALID are terminal for dataset eligibility
```

---

## 3. Eligibility Rule

```
If consent is absent            → DATA_STATUS = NOT_ELIGIBLE (consent gate = UNKNOWN)
If consent is not CONSENT_GRANTED → DATA_STATUS = NOT_ELIGIBLE
If consent_version is unrecognized → DATA_STATUS = NOT_ELIGIBLE (consent gate = UNKNOWN)
If document hash cannot be verified → CONSENT_INVALID → NOT_ELIGIBLE
```

There is no path from missing/invalid consent to dataset entry. Consent verification is
stage 2 of the pipeline and runs **before** secure acquisition — nothing about an
unconsented contribution is stored beyond the refusal record itself.

---

## 4. Withdrawal & Deletion

States (see also `CP32D_PRIVACY_PIPELINE.md` §7):

```
WITHDRAWAL_REQUESTED → WITHDRAWAL_CONFIRMED → DATA_DELETED → DERIVED_DATA_HANDLED
```

- Withdrawal must be exercisable through the same channel enrollment used (in-app or
  email) and must not require explaining a reason.
- On `WITHDRAWAL_CONFIRMED`: raw audio is deleted first, then transcripts, then
  annotations, then manifest entries are marked ineligible.
- **DERIVED_DATA_HANDLING limitation (must be stated, never hidden):** if a model has
  already been trained using a contribution, deleting the original training artifact does
  NOT automatically remove learned information from the already-trained model. Machine
  unlearning is NOT implemented and must not be promised. The honest mitigations are:
  (a) withdrawal blocks the contribution from all *future* training runs and manifests,
  (b) the next training run simply excludes it, and (c) retention limits bound how long
  contributions can ever enter training. If a deployed model was trained on withdrawn
  data, the deployment decision must record that fact.

---

## 5. Prohibited Consent Practices

- No consent-by-usage, consent-by-inference, or consent-by-default.
- No retroactive consent: data acquired before a valid consent record exists is
  permanently `NOT_ELIGIBLE` — consent cannot be applied backwards.
- No pressure, incentives conditioned on permission grants, or bundling of unrelated
  permissions.
- Recording may never begin before `consent_obtained_before_recording = true`.
