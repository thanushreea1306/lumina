# LUMINA ML — Tactic Taxonomy

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Finalized 11-label taxonomy for segment-level tactic classification.  
**Status:** FINAL

---

## Overview

LUMINA's tactic taxonomy defines 11 social-engineering tactic labels for segment-level classification of phone conversation transcripts. Each label represents a specific behavioral pattern that can be observed in a single utterance/segment.

**Key Principles:**
- Labels describe **observed behavior**, not intent or outcome
- Labels are **multi-label** — a segment can have multiple labels
- Labels are **mutually inclusive** — a segment can simultaneously exhibit authority claim and threat presentation
- UNKNOWN is excluded from training (it's a fallback, not a learning target)

---

## Label Definitions

### 1. AUTHORITY_CLAIM

**Canonical Name:** AUTHORITY_CLAIM  
**Definition:** The speaker claims or implies authority, official capacity, or institutional affiliation to establish credibility or compliance pressure.

**Positive Criteria:**
- Explicit claim of official role ("I am calling from the IRS")
- Reference to institutional authority ("This is the police department")
- Implication of official capacity ("We have a warrant")
- Use of authoritative titles ("Agent", "Officer", "Inspector")
- Reference to government agencies ("Social Security Administration", "FBI")

**Negative Criteria:**
- Legitimate identity statements (user identifying themselves)
- Reporting what someone else said (attribution, not claim)
- General references to institutions without authority claim context

**Boundary Cases:**
- "I'm from your bank" → AUTHORITY_CLAIM (institutional authority)
- "My friend works at the bank" → NOT AUTHORITY_CLAIM (third-party reference)
- "The police are looking for you" → AUTHORITY_CLAIM + THREAT_PRESENTATION (both apply)

**Severity Relevance:** High — authority claims are foundational to most scam scripts  
**Multi-label Allowed:** Yes — commonly co-occurs with THREAT_PRESENTATION

**Examples from legitimate sources:**  
EXAMPLE_REQUIRED_FROM_REAL_DATA

---

### 2. THREAT_PRESENTATION

**Canonical Name:** THREAT_PRESENTATION  
**Definition:** The speaker presents or implies negative consequences, punishment, legal action, or harm if the listener does not comply.

**Positive Criteria:**
- Explicit threats ("You will be arrested")
- Implied consequences ("Your account will be frozen")
- Legal threats ("We will file a lawsuit")
- Criminal accusations ("You are involved in money laundering")
- Penalty references ("You will face a fine of $10,000")

**Negative Criteria:**
- Warnings about genuine risks (e.g., "be careful with your password")
- General advice about consequences
- Reporting past events (not threatening future action)

**Boundary Cases:**
- "Your account will be suspended" → THREAT_PRESENTATION (negative consequence)
- "You should change your password" → ADVICE_OR_WARNING (helpful, not threatening)
- "If you don't pay now, we'll arrest you" → THREAT_PRESENTATION + TIME_PRESSURE

**Severity Relevance:** Critical — threats create urgency and compliance pressure  
**Multi-label Allowed:** Yes — commonly co-occurs with AUTHORITY_CLAIM, TIME_PRESSURE

**Examples from legitimate sources:**  
EXAMPLE_REQUIRED_FROM_REAL_DATA

---

### 3. TIME_PRESSURE

**Canonical Name:** TIME_PRESSURE  
**Definition:** The speaker creates urgency by imposing deadlines, time limits, or pressure to act immediately without deliberation.

**Positive Criteria:**
- Explicit time limits ("You have 30 minutes")
- Urgency language ("Do this immediately", "Right now")
- Countdown pressure ("The clock is ticking")
- Last-chance framing ("This is your final warning")
- Rushing ("Hurry up", "We're running out of time")

**Negative Criteria:**
- Normal scheduling ("Let's meet at 3pm")
- Genuine urgency (actual deadline)
- Patient explanations without pressure

**Boundary Cases:**
- "You must act within 24 hours" → TIME_PRESSURE (artificial deadline)
- "Your payment is due tomorrow" → MAYBE TIME_PRESSURE (depends on context)
- "Take your time to think" → NOT TIME_PRESSURE (opposite)

**Severity Relevance:** High — pressure prevents deliberation  
**Multi-label Allowed:** Yes — commonly co-occurs with THREAT_PRESENTATION

**Examples from legitimate sources:**  
EXAMPLE_REQUIRED_FROM_REAL_DATA

---

### 4. ISOLATION_TACTIC

**Canonical Name:** ISOLATION_TACTIC  
**Definition:** The speaker attempts to isolate the listener from independent verification, trusted contacts, or alternative information sources.

**Positive Criteria:**
- Secrecy requests ("Don't tell anyone about this")
- Blocking verification ("Don't contact your bank")
- Isolation instructions ("Go to a private room")
- Confidentiality framing ("This is classified information")
- Discouraging outside help ("No one else needs to know")

**Negative Criteria:**
- Genuine privacy requests
- Normal confidentiality (e.g., doctor-patient)
- Advice to seek help

**Boundary Cases:**
- "Don't tell your family" → ISOLATION_TACTIC (blocking trusted contacts)
- "This is confidential" → MAYBE ISOLATION_TACTIC (depends on context)
- "You should talk to your bank" → ADVICE_OR_WARNING (opposite)

**Severity Relevance:** High — isolation prevents course-correction  
**Multi-label Allowed:** Yes — commonly co-occurs with AUTHORITY_CLAIM, TIME_PRESSURE

**Examples from legitimate sources:**  
EXAMPLE_REQUIRED_FROM_REAL_DATA

---

### 5. CREDENTIAL_REQUEST

**Canonical Name:** CREDENTIAL_REQUEST  
**Definition:** The speaker requests authentication credentials, verification codes, passwords, PINs, or other security-sensitive information.

**Positive Criteria:**
- OTP/code requests ("Give me the verification code")
- Password requests ("What's your password?")
- PIN requests ("Enter your PIN")
- Security question requests ("What's your mother's maiden name?")
- Authentication bypass requests ("Read me the code that was just sent")

**Negative Criteria:**
- Legitimate service provider verification (with proper context)
- User-initiated sharing of credentials
- General discussion about passwords without request

**Boundary Cases:**
- "I need your OTP to verify" → CREDENTIAL_REQUEST (requesting code)
- "Did you receive an OTP?" → MAYBE CREDENTIAL_REQUEST (informational vs. request)
- "Never share your OTP" → ADVICE_OR_WARNING (opposite)

**Severity Relevance:** Critical — credential theft enables account compromise  
**Multi-label Allowed:** Yes — commonly co-occurs with AUTHORITY_CLAIM

**Examples from legitimate sources:**  
EXAMPLE_REQUIRED_FROM_REAL_DATA

---

### 6. FINANCIAL_REQUEST

**Canonical Name:** FINANCIAL_REQUEST  
**Definition:** The speaker requests money transfer, payment, gift cards, cryptocurrency, or other financial transactions.

**Positive Criteria:**
- Money transfer requests ("Send money to this account")
- Payment requests ("You need to pay a fee")
- Gift card requests ("Purchase gift cards and read me the codes")
- Cryptocurrency requests ("Transfer Bitcoin to this wallet")
- Wire transfer instructions ("Wire the funds to..."

**Negative Criteria:**
- Legitimate billing discussions
- User-initiated payments
- General financial advice

**Boundary Cases:**
- "Buy gift cards and give me the numbers" → FINANCIAL_REQUEST (clear request)
- "Your bill is overdue" → MAYBE FINANCIAL_REQUEST (depends on legitimacy)
- "Invest in this opportunity" → FINANCIAL_REQUEST (investment scam)

**Severity Relevance:** Critical — direct financial loss  
**Multi-label Allowed:** Yes — commonly co-occurs with AUTHORITY_CLAIM, TIME_PRESSURE

**Examples from legitimate sources:**  
EXAMPLE_REQUIRED_FROM_REAL_DATA

---

### 7. REMOTE_ACCESS_REQUEST

**Canonical Name:** REMOTE_ACCESS_REQUEST  
**Definition:** The speaker requests installation of software, screen sharing, remote desktop access, or other device access.

**Positive Criteria:**
- Software installation requests ("Install TeamViewer")
- Screen sharing requests ("Share your screen with me")
- Remote desktop requests ("Let me access your computer")
- App installation requests ("Download this app")
- Configuration changes ("Change your settings to...")

**Negative Criteria:**
- Legitimate technical support (with proper verification)
- User-initiated troubleshooting
- General software recommendations

**Boundary Cases:**
- "Install AnyDesk so I can help" → REMOTE_ACCESS_REQUEST (tech support scam)
- "Download our official app" → MAYBE (depends on legitimacy)
- "Update your software" → NOT REMOTE_ACCESS_REQUEST (maintenance)

**Severity Relevance:** Critical — remote access enables device compromise  
**Multi-label Allowed:** Yes — commonly co-occurs with AUTHORITY_CLAIM

**Examples from legitimate sources:**  
EXAMPLE_REQUIRED_FROM_REAL_DATA

---

### 8. IDENTITY_REQUEST

**Canonical Name:** IDENTITY_REQUEST  
**Definition:** The speaker requests identity documents, personal information, or identification numbers.

**Positive Criteria:**
- Document requests ("Send me a photo of your passport")
- ID number requests ("What's your Aadhaar number?")
- Personal information requests ("What's your date of birth?")
- Address requests ("What's your current address?")
- Employment information requests ("Where do you work?")

**Negative Criteria:**
- Legitimate identity verification (with proper context)
- User-initiated information sharing
- General conversation about identity

**Boundary Cases:**
- "Send me your PAN card photo" → IDENTITY_REQUEST (document request)
- "What's your name?" → MAYBE (depends on context)
- "Verify your identity through the official app" → ADVICE_OR_WARNING

**Severity Relevance:** High — identity theft enables fraud  
**Multi-label Allowed:** Yes — commonly co-occurs with AUTHORITY_CLAIM

**Examples from legitimate sources:**  
EXAMPLE_REQUIRED_FROM_REAL_DATA

---

### 9. BENIGN_CONVERSATION

**Canonical Name:** BENIGN_CONVERSATION  
**Definition:** The segment contains normal conversation without detectable social-engineering tactics.

**Positive Criteria:**
- Greetings and small talk
- Neutral information exchange
- Normal questions and answers
- No authority claims, threats, urgency, or requests
- Absence of other tactic indicators

**Negative Criteria:**
- Any segment with detectable tactics
- Ambiguous segments (use UNKNOWN instead)
- Segments with mixed signals

**Boundary Cases:**
- "Hello, how are you?" → BENIGN_CONVERSATION
- "I'm calling about your account" → MAYBE BENIGN (depends on what follows)
- "Thank you for your time" → BENIGN_CONVERSATION

**Severity Relevance:** None — baseline negative class  
**Multi-label Allowed:** No — exclusive (if any other label applies, BENIGN is not assigned)

**Examples from legitimate sources:**  
EXAMPLE_REQUIRED_FROM_REAL_DATA

---

### 10. USER_RESISTANCE

**Canonical Name:** USER_RESISTANCE  
**Definition:** The listener (user/victim) expresses resistance, refusal, skepticism, or pushback against the speaker's requests or claims.

**Positive Criteria:**
- Direct refusal ("I'm not going to do that")
- Skepticism ("That doesn't sound right")
- Pushback ("I don't believe you")
- Seeking verification ("Let me call the bank myself")
- Questioning authority ("How do I know you're real?")

**Negative Criteria:**
- Compliance ("Okay, I'll do it")
- Passive agreement
- Confusion (not resistance)

**Boundary Cases:**
- "I don't think so" → USER_RESISTANCE (skepticism)
- "I'm not sure" → MAYBE (depends on context)
- "Okay, fine" → NOT USER_RESISTANCE (compliance)

**Severity Relevance:** Positive — resistance indicates the user is not fully compliant  
**Multi-label Allowed:** Yes — can co-occurs with any tactic label (user resisting while caller applies tactics)

**Examples from legitimate sources:**  
EXAMPLE_REQUIRED_FROM_REAL_DATA

---

### 11. ADVICE_OR_WARNING

**Canonical Name:** ADVICE_OR_WARNING  
**Definition:** The speaker provides advice, warnings, or guidance about safety, security, or appropriate behavior.

**Positive Criteria:**
- Safety advice ("Never share your OTP with anyone")
- Security warnings ("Be careful with suspicious calls")
- Protective guidance ("Hang up and call the official number")
- Educational content ("Legitimate organizations never ask for OTPs")
- Cautionary statements ("Don't click on suspicious links")

**Negative Criteria:**
- Threats disguised as warnings
- Pressure disguised as advice
- General conversation without safety content

**Boundary Cases:**
- "Don't share your OTP" → ADVICE_OR_WARNING (safety advice)
- "If you don't share your OTP, we'll arrest you" → THREAT_PRESENTATION (threat, not advice)
- "You should be careful" → ADVICE_OR_WARNING (general caution)

**Severity Relevance:** Positive — indicates protective content  
**Multi-label Allowed:** Yes — can co-occurs with other labels in educational contexts

**Examples from legitimate sources:**  
EXAMPLE_REQUIRED_FROM_REAL_DATA

---

## Label Relationships

### Common Co-occurrences

| Label Pair | Frequency | Notes |
|-----------|-----------|-------|
| AUTHORITY_CLAIM + THREAT_PRESENTATION | Very High | Foundation of most scam scripts |
| AUTHORITY_CLAIM + TIME_PRESSURE | High | Authority + urgency pattern |
| THREAT_PRESENTATION + TIME_PRESSURE | High | Threat + urgency pattern |
| AUTHORITY_CLAIM + CREDENTIAL_REQUEST | High | Authority + credential theft |
| AUTHORITY_CLAIM + FINANCIAL_REQUEST | High | Authority + financial fraud |
| USER_RESISTANCE + (any tactic) | Variable | User pushing back against any tactic |

### Exclusive Pairs

| Label Pair | Notes |
|-----------|-------|
| BENIGN_CONVERSATION + (any tactic) | BENIGN is exclusive — if any tactic applies, BENIGN is not assigned |

---

## Taxonomy Versioning

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-09-07 | Initial taxonomy definition |

Future changes to the taxonomy require:
1. Impact assessment on existing annotations
2. Re-annotation of affected segments
3. Version bump and changelog
4. Model retraining if taxonomy changes
