# LUMINA ML — Real Pilot Consent Model

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Explicit consent model for LUMINA real-conversation pilot.
**Status:** COMPLETE — Ready for participant enrollment

---

## Consent Philosophy

**No implied consent. No prechecked boxes. No recording before consent.**

Every permission is explicit, granular, and revocable. Consent is obtained BEFORE any recording or data collection occurs.

---

## 1. Consent Record Schema

```json
{
  "consent_id": "uuid-v4",
  "participant_id": "uuid-v4",
  "consent_version": "1.0",
  "consent_document_hash": "sha256:...",
  "consent_timestamp": "ISO 8601",
  "consent_obtained_before_recording": true,
  "permissions": {
    "participation": false,
    "audio_recording": false,
    "speech_to_text": false,
    "behavioral_ml_annotation": false,
    "ml_model_training": false,
    "research_evaluation": false,
    "production_use": false,
    "anonymized_aggregate_reporting": false
  },
  "retention_period_days": 365,
  "withdrawal_mechanism": "email-or-in-app",
  "deletion_mechanism": "verified-deletion",
  "consent_document_version": "1.0",
  "consent_document_url": "https://...",
  "jurisdiction": "US",
  "age_verification": true,
  "age_confirmed_over_18": true
}
```

---

## 2. Permission Definitions

### 2.1 Participation
**What:** Permission to participate in the LUMINA research pilot.
**Default:** false
**Required:** Yes (without this, no data is collected)

### 2.2 Audio Recording
**What:** Permission to record or accept audio of the participant's conversations.
**Default:** false
**Required:** Yes (without this, no audio is collected)

### 2.3 Speech-to-Text Transcription
**What:** Permission to transcribe the participant's audio using automated speech recognition.
**Default:** false
**Required:** Yes (without this, transcripts cannot be generated)

### 2.4 Behavioral ML Annotation
**What:** Permission for human annotators to label the participant's transcript segments with behavioral tactic labels.
**Default:** false
**Required:** Yes (without this, annotations cannot be created)

### 2.5 ML Model Training
**What:** Permission to use the participant's annotated data for training machine learning models.
**Default:** false
**Required:** Yes (without this, data cannot be used for training)

### 2.6 Research Evaluation
**What:** Permission to use the participant's data for research evaluation and benchmarking.
**Default:** false
**Required:** Yes (without this, data cannot be used for evaluation)

### 2.7 Production Use
**What:** Permission to use the participant's data in production LUMINA systems.
**Default:** false
**Required:** No (optional; pilot can proceed without this)

### 2.8 Anonymized Aggregate Reporting
**What:** Permission to include anonymized aggregate statistics about the participant's data in research reports.
**Default:** false
**Required:** No (optional; pilot can proceed without this)

---

## 3. Consent Process

### Step 1: Information Disclosure
Before consent is requested, the participant receives:
- Description of the research project
- What data will be collected
- How data will be used
- Who will have access
- How data will be protected
- Their rights (withdrawal, deletion)
- Contact information for questions

### Step 2: Consent Request
Each permission is presented as a separate, unchecked checkbox:
- ☐ I consent to participate in this research
- ☐ I consent to audio recording of my conversations
- ☐ I consent to speech-to-text transcription
- ☐ I consent to behavioral ML annotation
- ☐ I consent to ML model training
- ☐ I consent to research evaluation
- ☐ I consent to production use (optional)
- ☐ I consent to anonymized aggregate reporting (optional)

### Step 3: Consent Confirmation
After all permissions are selected:
1. Participant reviews their selections
2. Participant confirms consent
3. Consent record is created with timestamp
4. Consent document hash is recorded
5. Recording/data collection begins ONLY after consent is confirmed

### Step 4: Consent Receipt
Participant receives:
- Copy of their consent record
- Consent document hash
- Contact information for withdrawal
- Instructions for how to withdraw

---

## 4. Withdrawal Process

### How to Withdraw
- Email: research@lumina.example.com
- In-app: Settings → Privacy → Withdraw from Research
- Written request to research team

### What Happens on Withdrawal

1. **Immediate:** Participant's data is flagged as WITHDRAWN
2. **Within 24 hours:** No new processing of participant's data
3. **Within 30 days:** Deletion of participant's pilot data
4. **Verification:** Deletion is verified and logged
5. **Notification:** Participant is notified of completed deletion

### What Is Deleted
- Audio recordings
- Transcripts
- Annotations (linked to participant)
- Any derived data

### What May Be Retained
- Audit logs (required for compliance)
- Anonymized aggregate statistics (if consent was given)
- Deletion verification records

---

## 5. Deletion Mechanism

### Technical Deletion
1. Identify all data linked to participant_id
2. Delete from primary storage
3. Delete from backups (within retention period)
4. Delete from annotation exports
5. Delete from ML training data
6. Verify deletion across all systems
7. Log deletion with timestamp

### Verification
- Deletion verification record created
- Record includes: participant_id (anonymized), deletion_timestamp, verification_method
- Record is retained for compliance

---

## 6. Data Retention

### Default Retention Period
- **365 days** from consent date
- After retention period: data is eligible for deletion
- Participant can request early deletion at any time

### Retention Exceptions
- Audit logs: retained for 7 years (compliance requirement)
- Deletion verification records: retained indefinitely
- Anonymized aggregate statistics: retained indefinitely

---

## 7. Privacy Protections

### What Is NOT Collected
- Real name (only random participant_id)
- Phone number (only random identifier)
- Email address (only for consent/withdrawal communication)
- Government ID
- Financial account information
- Biometric data (beyond voice, which is processed and deleted)

### What IS Collected
- Random participant_id
- Consent record
- Audio recordings (deleted after processing)
- Transcripts (sanitized before annotation)
- Annotations (linked to participant_id)
- Provenance metadata

### Access Controls
- Raw audio: admin-only access, encrypted at rest
- Raw transcript: admin-only access, encrypted at rest
- Sanitized transcript: annotator access
- Annotations: annotator and researcher access
- Training data: researcher access only

---

## 8. Legal Compliance

### Jurisdiction
- Default: United States
- One-party consent states: Federal law (18 U.S.C. § 2511) permits recording if one party consents
- All-party consent states: Additional consent may be required
- International: Varies by jurisdiction

### IRB/Ethics
- If applicable: IRB approval obtained before participant enrollment
- If not applicable: Ethical review conducted by research team
- Documented in consent record

### Age Requirement
- Participants must be 18 years or older
- Age verification required before consent

---

## 9. Consent Document Versioning

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-09-07 | Initial consent model |

Future changes require:
1. Impact assessment on existing participants
2. Re-consent from affected participants
3. Version bump and changelog
4. Documentation of changes

---

## 10. Audit Trail

Every consent operation is logged:
- Consent creation
- Consent modification
- Consent withdrawal
- Deletion request
- Deletion completion
- Deletion verification

Audit logs are:
- Immutable (write-once)
- Encrypted
- Access-controlled (admin-only)
- Retained for 7 years

---

## 11. Contact Information

For questions about consent:
- Email: research@lumina.example.com
- In-app: Settings → Privacy → Contact Research Team

For withdrawal:
- Email: withdraw@lumina.example.com
- In-app: Settings → Privacy → Withdraw from Research

---

## 12. Consent Record Validation

### Validation Rules

| Rule | Description |
|------|-------------|
| consent_id present | Must be UUID v4 |
| participant_id present | Must be UUID v4 |
| consent_timestamp present | Must be valid ISO 8601 |
| consent_obtained_before_recording | Must be true |
| All required permissions granted | participation, audio_recording, speech_to_text, behavioral_ml_annotation, ml_model_training, research_evaluation |
| consent_document_hash present | Must be SHA-256 hash |
| age_confirmed_over_18 | Must be true |
| withdrawal_mechanism present | Must be valid string |
| deletion_mechanism present | Must be valid string |

### Validation Failure
If any validation rule fails:
- Consent is INVALID
- No data collection may occur
- Participant is notified
- Issue is logged
