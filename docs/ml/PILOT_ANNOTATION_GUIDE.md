# LUMINA ML — Pilot Annotation Guide

**Document Version:** 1.0
**Created:** 2026-09-07
**Purpose:** Annotation methodology for the pilot dataset feasibility study.
**Status:** COMPLETE — Ready for annotation

---

## Overview

This guide defines how human annotators label transcript segments with LUMINA's 11 tactic labels. The goal is to produce high-quality, reproducible annotations for the pilot feasibility study.

**Critical Principle:** Annotate OBSERVED BEHAVIOR, not inferred intent.

---

## 1. Annotation Task

### Input
A conversation transcript divided into segments (utterances), with speaker attribution where available.

### Output
For each segment:
- One or more tactic labels (multi-label)
- Confidence level (HIGH / MEDIUM / LOW)
- Evidence span (the exact text supporting the label)
- Notes (optional, for boundary cases)

---

## 2. Tactic Label Definitions

### 2.1 AUTHORITY_CLAIM

**Definition:** The speaker claims or implies authority, official capacity, or institutional affiliation to establish credibility or compliance pressure.

**Positive Examples:**
- "I am calling from the IRS"
- "This is the police department"
- "We have a warrant for your arrest"
- "Agent Smith from the Social Security Administration"

**Negative Examples:**
- "I'm John from XYZ Company" (legitimate business identification)
- "My friend works at the bank" (third-party reference)
- "The police are looking for you" (reporting, not claiming authority)

**Boundary Cases:**
- "I'm from your bank" → AUTHORITY_CLAIM (institutional authority)
- "Your account has been compromised" → MAYBE AUTHORITY_CLAIM (depends on context)

### 2.2 THREAT_PRESENTATION

**Definition:** The speaker presents or implies negative consequences, punishment, legal action, or harm if the listener does not comply.

**Positive Examples:**
- "You will be arrested"
- "Your account will be frozen"
- "We will file a lawsuit"
- "You are involved in money laundering"
- "You will face a fine of $10,000"

**Negative Examples:**
- "Be careful with your password" (genuine warning)
- "Your payment is due tomorrow" (normal deadline)
- "If you don't pay, we'll report to credit bureau" (depends on legitimacy)

**Boundary Cases:**
- "Your account will be suspended" → THREAT_PRESENTATION (negative consequence)
- "You should change your password" → ADVICE_OR_WARNING (helpful)
- "If you don't pay now, we'll arrest you" → THREAT_PRESENTATION + TIME_PRESSURE

### 2.3 TIME_PRESSURE

**Definition:** The speaker creates urgency by imposing deadlines, time limits, or pressure to act immediately without deliberation.

**Positive Examples:**
- "You have 30 minutes"
- "Do this immediately"
- "Right now"
- "The clock is ticking"
- "This is your final warning"
- "Hurry up"

**Negative Examples:**
- "Let's meet at 3pm" (normal scheduling)
- "Take your time to think" (opposite)
- "Your payment is due tomorrow" (genuine deadline)

**Boundary Cases:**
- "You must act within 24 hours" → TIME_PRESSURE (artificial deadline)
- "We need to resolve this today" → MAYBE TIME_PRESSURE (depends on context)

### 2.4 ISOLATION_TACTIC

**Definition:** The speaker attempts to isolate the listener from independent verification, trusted contacts, or alternative information sources.

**Positive Examples:**
- "Don't tell anyone about this"
- "Don't contact your bank"
- "Go to a private room"
- "This is classified information"
- "No one else needs to know"

**Negative Examples:**
- "This is confidential" (normal business practice)
- "You should talk to your bank" (opposite)
- Doctor-patient confidentiality (legitimate privacy)

**Boundary Cases:**
- "Don't tell your family" → ISOLATION_TACTIC (blocking trusted contacts)
- "This is between us" → MAYBE ISOLATION_TACTIC (depends on context)

### 2.5 CREDENTIAL_REQUEST

**Definition:** The speaker requests authentication credentials, verification codes, passwords, PINs, or other security-sensitive information.

**Positive Examples:**
- "Give me the verification code"
- "What's your password?"
- "Enter your PIN"
- "What's your mother's maiden name?"
- "Read me the code that was just sent"

**Negative Examples:**
- "Did you receive an OTP?" (informational)
- "Never share your OTP" (safety advice)
- "Please verify your identity through the official app" (proper verification)

**Boundary Cases:**
- "I need your OTP to verify" → CREDENTIAL_REQUEST (requesting code)
- "Did you get a code?" → MAYBE CREDENTIAL_REQUEST (informational vs. request)

### 2.6 FINANCIAL_REQUEST

**Definition:** The speaker requests money transfer, payment, gift cards, cryptocurrency, or other financial transactions.

**Positive Examples:**
- "Send money to this account"
- "You need to pay a fee"
- "Purchase gift cards and read me the codes"
- "Transfer Bitcoin to this wallet"
- "Wire the funds to..."

**Negative Examples:**
- "Your bill is overdue" (informational)
- "You can pay online" (legitimate payment option)
- "Invest in this opportunity" (depends on context)

**Boundary Cases:**
- "Buy gift cards and give me the numbers" → FINANCIAL_REQUEST (clear request)
- "Your bill is overdue" → MAYBE FINANCIAL_REQUEST (depends on legitimacy)

### 2.7 REMOTE_ACCESS_REQUEST

**Definition:** The speaker requests installation of software, screen sharing, remote desktop access, or other device access.

**Positive Examples:**
- "Install TeamViewer"
- "Share your screen with me"
- "Let me access your computer"
- "Download this app"
- "Change your settings to..."

**Negative Examples:**
- "Update your software" (maintenance)
- "Download our official app" (legitimate)
- "Please verify through the website" (proper verification)

**Boundary Cases:**
- "Install AnyDesk so I can help" → REMOTE_ACCESS_REQUEST (tech support scam)
- "Download our app" → MAYBE (depends on legitimacy)

### 2.8 IDENTITY_REQUEST

**Definition:** The speaker requests identity documents, personal information, or identification numbers.

**Positive Examples:**
- "Send me a photo of your passport"
- "What's your Aadhaar number?"
- "What's your date of birth?"
- "What's your current address?"
- "Where do you work?"

**Negative Examples:**
- "Please verify your identity through the official app" (proper verification)
- "What's your name?" (normal conversation)
- General discussion about identity

**Boundary Cases:**
- "Send me your PAN card photo" → IDENTITY_REQUEST (document request)
- "What's your name?" → MAYBE (depends on context)

### 2.9 BENIGN_CONVERSATION

**Definition:** The segment contains normal conversation without detectable social-engineering tactics.

**Positive Examples:**
- "Hello, how are you?"
- Neutral information exchange
- Normal questions and answers
- Greetings and small talk

**Negative Examples:**
- Any segment with detectable tactics
- Ambiguous segments (use UNKNOWN instead)
- Segments with mixed signals

**Rules:**
- BENIGN is EXCLUSIVE — if any other label applies, BENIGN is NOT assigned
- Use UNKNOWN when uncertain

### 2.10 USER_RESISTANCE

**Definition:** The listener (user/victim) expresses resistance, refusal, skepticism, or pushback against the speaker's requests or claims.

**Positive Examples:**
- "I'm not going to do that"
- "That doesn't sound right"
- "I don't believe you"
- "Let me call the bank myself"
- "How do I know you're real?"

**Negative Examples:**
- "Okay, I'll do it" (compliance)
- "I'm not sure" (confusion, not resistance)
- Passive agreement

**Boundary Cases:**
- "I don't think so" → USER_RESISTANCE (skepticism)
- "I'm not sure" → MAYBE (depends on context)
- "Okay, fine" → NOT USER_RESISTANCE (compliance)

### 2.11 ADVICE_OR_WARNING

**Definition:** The speaker provides advice, warnings, or guidance about safety, security, or appropriate behavior.

**Positive Examples:**
- "Never share your OTP with anyone"
- "Be careful with suspicious calls"
- "Hang up and call the official number"
- "Legitimate organizations never ask for OTPs"
- "Don't click on suspicious links"

**Negative Examples:**
- Threats disguised as warnings
- Pressure disguised as advice
- General conversation without safety content

**Boundary Cases:**
- "Don't share your OTP" → ADVICE_OR_WARNING (safety advice)
- "If you don't share your OTP, we'll arrest you" → THREAT_PRESENTATION (threat, not advice)

---

## 3. Annotation Procedure

### Step 1: Read the Full Conversation
Before annotating individual segments, read the entire conversation to understand context.

### Step 2: Annotate Each Segment
For each segment:
1. Identify the speaker (CALLER / RECIPIENT / UNKNOWN)
2. Read the text carefully
3. Apply ALL applicable tactic labels (multi-label)
4. For each label, note the evidence span
5. Rate your confidence (HIGH / MEDIUM / LOW)
6. Add notes for boundary cases

### Step 3: Review for Consistency
After annotating all segments in a conversation:
1. Check for consistent speaker labels
2. Verify tactic labels make sense in context
3. Ensure no contradictory labels

### Step 4: Flag Difficult Cases
If a segment is genuinely ambiguous:
1. Apply the most likely label(s)
2. Set confidence to LOW
3. Add a note explaining the ambiguity
4. Do NOT leave labels empty — use UNKNOWN if truly uncertain

---

## 4. Quality Control

### Inter-Annotator Agreement

For the pilot, at least 20% of segments should be double-annotated.

**Metrics:**
- Cohen's kappa (per-label and macro)
- Percentage agreement
- Disagreement rate

**Targets:**
- Cohen's κ > 0.7 (good agreement)
- Percentage agreement > 80%
- Disagreement rate < 20%

### Adjudication

When annotators disagree:
1. Both annotations are preserved
2. A third expert annotator reviews
3. The third annotator's label is used
4. The disagreement is documented

### Gold Set Validation

The gold set (50-100 expert-reviewed segments) is used to:
1. Calibrate annotator performance
2. Identify systematic errors
3. Refine annotation guidelines

---

## 5. Annotation Output Format

### Per-Segment Annotation

```json
{
  "segment_id": "seg_001",
  "conversation_id": "conv_001",
  "speaker": "CALLER",
  "text": "I am calling from the IRS regarding your tax returns",
  "tactic_labels": [
    {
      "label": "AUTHORITY_CLAIM",
      "confidence": "HIGH",
      "evidence_span": "I am calling from the IRS"
    }
  ],
  "conversation_phase": "SETUP",
  "annotator_id": "annotator_01",
  "annotation_timestamp": "2026-09-07T12:00:00Z",
  "notes": ""
}
```

### Per-Conversation Annotation

```json
{
  "conversation_id": "conv_001",
  "source": "kaggle_youtube_scam",
  "license": "CC0",
  "total_segments": 15,
  "speakers": ["CALLER", "RECIPIENT"],
  "overall_tactics": ["AUTHORITY_CLAIM", "THREAT_PRESENTATION", "TIME_PRESSURE"],
  "conversation_phase": "EXTRACTION",
  "annotation_quality": "HIGH",
  "annotator_ids": ["annotator_01", "annotator_02"],
  "adjudication_needed": false
}
```

---

## 6. Common Annotation Errors

### Error 1: Annotating Intent Instead of Behavior
❌ "The speaker is trying to scam the victim"
✅ "The speaker claims to be from the IRS" (AUTHORITY_CLAIM)

### Error 2: Using Labels Interchangeably
❌ THREAT_PRESENTATION for "You should change your password"
✅ ADVICE_OR_WARNING for "You should change your password"

### Error 3: Forcing Labels When Uncertain
❌ Applying a label when evidence is ambiguous
✅ Use UNKNOWN or LOW confidence

### Error 4: Ignoring Multi-Label
❌ Applying only the most obvious label
✅ Apply ALL applicable labels

### Error 5: Annotating Without Context
❌ Annotating segments in isolation
✅ Read the full conversation first

---

## 7. Pilot-Specific Guidelines

### Minimum Annotations per Tactic
- At least 30 positive examples per common tactic
- At least 15 positive examples per rare tactic
- At least 50 BENIGN_CONVERSATION examples

### Priority Order
1. First, annotate all conversations with clear tactic evidence
2. Then, annotate benign conversations for negative examples
3. Finally, annotate ambiguous/boundary cases

### Time Estimate
- ~2-5 minutes per segment (depending on complexity)
- ~30-60 minutes per conversation (10-15 segments)
- Total pilot estimate: ~50-100 hours for 500-1,500 segments

---

## 8. Ethical Considerations

### Do No Harm
- Annotators should not be exposed to excessively disturbing content
- Provide resources for mental health support if needed
- Allow annotators to skip segments they find distressing

### Confidentiality
- Annotator identities are confidential
- Annotation data is stored securely
- No sharing of raw data outside the annotation team

### Fairness
- Annotate consistently regardless of speaker demographics
- Do not assume scam/non-scam based on accent or dialect
- Focus on behavioral evidence, not stereotypes
