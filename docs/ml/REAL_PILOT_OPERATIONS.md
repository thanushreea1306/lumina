# LUMINA ML — Real Pilot Operations

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Operational procedures for real-conversation pilot collection.
**Status:** COMPLETE — Ready for operations

---

## 1. Overview

This document defines the operational procedures for running the LUMINA real-conversation pilot collection system. It covers participant enrollment, recording collection, processing, annotation, and quality control.

---

## 2. Participant Enrollment

### Prerequisites
- Participant is 18+ years old
- Participant has read and understood the consent document
- Participant has access to a device for recording/uploading

### Enrollment Steps

1. **Information Session**
   - Present research description
   - Explain data collection process
   - Explain rights (withdrawal, deletion)
   - Answer questions

2. **Consent Collection**
   - Present consent form with granular permissions
   - Participant selects each permission explicitly
   - No prechecked boxes
   - Participant confirms consent
   - Consent record created

3. **Identifier Generation**
   - Generate random participant_id (UUID v4)
   - Store consent_id ↔ participant_id linkage (encrypted)
   - Provide participant with their anonymized identifier

4. **Enrollment Confirmation**
   - Send consent receipt to participant
   - Include contact information for withdrawal
   - Include instructions for recording/uploading

---

## 3. Recording Collection

### Source 1: User-Provided Recording

**Process:**
1. Participant uploads existing recording via secure upload
2. System validates file format (WAV, MP3, etc.)
3. System creates conversation record with provenance
4. Recording is stored encrypted
5. Participant confirms recording is authorized

**Requirements:**
- Participant must have legal right to share the recording
- Both parties must have consented to recording
- Participant confirms both-party consent

### Source 2: Authorized Research Recording

**Process:**
1. Research team schedules recording session
2. Both participants confirm consent before recording
3. Recording begins only after consent confirmation
4. Recording is stored encrypted
5. Provenance metadata is recorded

**Requirements:**
- Both participants must be enrolled
- Both participants must confirm consent before recording
- Recording must be authorized by research team

### Source 3: Controlled Roleplay (Separate Pool)

**Process:**
1. Research team designs scenario
2. Participants agree to roleplay
3. Recording is made
4. Recording is labeled ROLEPLAY
5. Stored separately from real data

**Requirements:**
- Clearly labeled as ROLEPLAY
- Never enters real ML candidate pool
- Used for system testing only

---

## 4. Processing Pipeline

### Step 1: Provenance Verification
- Verify consent records
- Verify recording source
- Verify two-party structure
- Assign provenance metadata

### Step 2: PII/Secret Sanitization
- Detect and redact PII
- Detect and redact secrets
- Create sanitized transcript
- Verify sanitization

### Step 3: Transcription
- Run STT pipeline (Whisper-based)
- Generate transcript
- Record transcription metadata
- Link transcript to audio

### Step 4: Speaker Diarization
- Identify speakers
- Assign speaker labels (CALLER/RECIPIENT/UNKNOWN)
- Record speaker attribution confidence
- Verify ≥80% attribution

### Step 5: Segmentation
- Split transcript into utterance-level segments
- Assign segment IDs
- Record timestamps
- Link segments to conversation

### Step 6: Quality Check
- Validate data contract
- Check for duplicates
- Check for empty segments
- Check for invalid labels

---

## 5. Annotation Process

### Step 1: Annotation Assignment
- Assign segments to annotators
- Ensure ≥20% double-annotation
- Track annotation progress

### Step 2: Annotation Execution
- Annotator reads full conversation
- Annotator labels each segment
- Annotator provides evidence spans
- Annotator records confidence levels
- LLM may suggest labels (human decides)

### Step 3: Quality Control
- Compare double-annotated segments
- Calculate inter-annotator agreement
- Identify disagreements
- Route disagreements to adjudicator

### Step 4: Adjudication
- Third annotator reviews disagreements
- Third annotator makes final decision
- Record adjudication decision
- Update annotation records

### Step 5: Validation
- Validate annotation schema
- Check label validity
- Check evidence span presence
- Check annotation version

---

## 6. Quality Dashboard

### Dashboard Metrics

| Category | Metric | Value |
|----------|--------|-------|
| **Scale** | Total conversations | 0 |
| | Real two-party conversations | 0 |
| | One-sided conversations | 0 |
| | Roleplay conversations | 0 |
| | Synthetic conversations | 0 |
| | Unknown provenance | 0 |
| **Language** | English conversations | 0 |
| | Non-English conversations | 0 |
| **Attribution** | Conversations with speaker attribution | 0 |
| | Conversations with usable transcripts | 0 |
| **Annotation** | Annotated segments | 0 |
| | Unannotated segments | 0 |
| | Double-annotated segments | 0 |
| **Labels** | Segments per tactic | {} |
| | Segments per speaker | {} |
| **Privacy** | Withdrawn conversations | 0 |
| | Excluded conversations | 0 |
| | PII detections | 0 |
| **Quality** | Inter-annotator κ | N/A |
| | Disagreement rate | N/A |

### Dashboard Update Frequency
- Real-time for new recordings
- Daily for annotation progress
- Weekly for quality metrics
- On-demand for reporting

---

## 7. Withdrawal and Deletion

### Withdrawal Request
1. Participant contacts research team
2. Research team verifies participant identity
3. Withdrawal is recorded
4. Deletion process begins

### Deletion Process
1. Identify all data linked to participant_id
2. Flag data as WITHDRAWN
3. Delete from primary storage (within 30 days)
4. Delete from backups (within retention period)
5. Delete from annotation exports
6. Delete from ML training data
7. Verify deletion
8. Log deletion with timestamp

### Deletion Verification
- Deletion verification record created
- Record includes: participant_id (anonymized), deletion_timestamp, verification_method
- Record is retained for compliance

---

## 8. Security

### Access Controls
- Raw audio: admin-only, encrypted at rest
- Raw transcript: admin-only, encrypted at rest
- Sanitized transcript: annotator access
- Annotations: annotator and researcher access
- Training data: researcher access only

### Authentication
- All access requires authentication
- Role-based access control
- Audit logging for all access

### Encryption
- Data at rest: AES-256
- Data in transit: TLS 1.3
- Keys managed via secure key management

---

## 9. Retention and Deletion

### Default Retention
- Audio recordings: 365 days from consent
- Transcripts: 365 days from consent
- Annotations: Indefinite (research value)
- Training data: Indefinite (model lineage)
- Audit logs: 7 years (compliance)

### Deletion Triggers
- Participant withdrawal
- Retention period expiration
- Research project completion
- Legal requirement

---

## 10. Incident Response

### Privacy Breach
1. Contain the breach
2. Assess impact
3. Notify affected participants
4. Notify regulatory authorities (if required)
5. remediate
6. Document lessons learned

### Data Integrity Issue
1. Identify affected data
2. Assess impact on research
3. Determine if re-collection needed
4. Document issue and resolution

---

## 11. Reporting

### Weekly Report
- New recordings collected
- Annotations completed
- Quality metrics
- Issues encountered

### Monthly Report
- Cumulative statistics
- Quality trends
- Participant engagement
- Resource utilization

### Final Pilot Report
- Total data collected
- Quality assessment
- Acceptance gate results
- Training readiness
- Recommendations

---

## 12. Roles and Responsibilities

| Role | Responsibilities |
|------|-----------------|
| Research Lead | Overall pilot management, quality oversight |
| Consent Manager | Consent collection, withdrawal processing |
| Recording Manager | Recording collection, provenance verification |
| Processing Engineer | PII sanitization, transcription, segmentation |
| Annotation Lead | Annotation quality, inter-annotator agreement |
| Annotator | Segment labeling, evidence grounding |
| Adjudicator | Disagreement resolution |
| Privacy Officer | Privacy compliance, incident response |
| Data Engineer | Storage, access controls, security |
