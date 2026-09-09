# LUMINA ML — Annotation Guidelines

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Rigorous annotation protocol for segment-level tactic classification.  
**Status:** FINAL

---

## 1. Overview

These guidelines define how human annotators label transcript segments with LUMINA's 11 tactic labels. The goal is to produce high-quality, reproducible annotations for training the ML classifier.

**Core Principle:** Annotate what is OBSERVED in the text, not what is INFERRED about intent or outcome.

---

## 2. Annotator Instructions

### 2.1 Before You Begin

1. Read the Tactic Taxonomy (TACTIC_TAXONOMY.md) completely
2. Complete the training exercise (10 pre-labeled examples)
3. Achieve >80% agreement with gold labels
4. Sign the confidentiality agreement

### 2.2 Annotation Process

For each segment:

1. **Read the segment text** carefully
2. **Read surrounding context** (previous and next segments if available)
3. **Identify the speaker** (CALLER, USER, or UNKNOWN)
4. **Apply labels** based on observed behavior
5. **Provide rationale** for each label applied
6. **Rate confidence** (how confident you are in your labels)
7. **Flag ambiguities** if the segment is unclear

### 2.3 Key Rules

- **Annotate behavior, not intent:** Label what the speaker SAID, not what they MEANT
- **Multi-label is normal:** A segment can have multiple labels
- **When in doubt, use fewer labels:** Don't over-label
- **BENIGN is exclusive:** If any tactic applies, don't also assign BENIGN
- **UNKNOWN is not a training label:** Only use it if you genuinely cannot determine any label
- **Context matters:** Use surrounding segments to inform your judgment

---

## 3. Segment Boundaries

### 3.1 What is a Segment?

A segment is a single utterance or turn in the conversation. It corresponds to:
- One speaker's continuous speech
- A natural break in the conversation
- A semantic unit (one idea or request)

### 3.2 Segment Boundary Rules

- **Split at speaker turns:** Each speaker change creates a new segment
- **Split at long pauses:** >3 seconds of silence
- **Split at topic changes:** When the speaker shifts to a new subject
- **Don't split mid-sentence:** Keep complete thoughts together
- **Don't split mid-phrase:** Keep "give me your" + "OTP" together

### 3.3 Segment Length

- **Minimum:** 1 word (e.g., "Yes")
- **Maximum:** 2000 characters (longer segments should be split)
- **Typical:** 5-50 words

---

## 4. Multi-Label Rules

### 4.1 When to Apply Multiple Labels

Apply multiple labels when a single segment exhibits multiple tactics:

**Example:**
> "I am Officer Smith from the IRS. You owe $5,000 in back taxes and must pay immediately or face arrest."

Labels: AUTHORITY_CLAIM, FINANCIAL_REQUEST, TIME_PRESSURE, THREAT_PRESENTATION

### 4.2 Label Priority

If multiple labels apply, apply ALL of them. There is no priority ordering. The model learns to predict all applicable labels.

### 4.3 BENIGN Exclusivity

BENIGN_CONVERSATION is exclusive. If ANY tactic label applies, do NOT also assign BENIGN.

**Correct:**
- Segment with authority claim → [AUTHORITY_CLAIM]
- Segment with no tactics → [BENIGN_CONVERSATION]

**Incorrect:**
- Segment with authority claim → [AUTHORITY_CLAIM, BENIGN_CONVERSATION] ← WRONG

---

## 5. Ambiguity Handling

### 5.1 When Segments are Ambiguous

If a segment is genuinely ambiguous:

1. **Apply the labels you're most confident about**
2. **Set annotation_confidence to 0.5 or lower**
3. **Add a rationale explaining the ambiguity**
4. **Flag for review**

### 5.2 Context-Dependent Labels

Some segments require context to label correctly:

- "You need to do this now" → Could be TIME_PRESSURE or legitimate urgency
- "Don't tell anyone" → Could be ISOLATION_TACTIC or genuine privacy
- "Give me the code" → Could be CREDENTIAL_REQUEST or legitimate verification

**Use surrounding segments to disambiguate.**

### 5.3 Unknown Segments

Use UNKNOWN only when:
- The text is unintelligible
- The speaker cannot be determined
- The context is insufficient
- You genuinely cannot apply any label

UNKNOWN is not a training target — it's a catch-all for unclassifiable segments.

---

## 6. Disagreement Handling

### 6.1 When Annotators Disagree

If two annotators disagree on a segment:

1. **Adjudicator reviews** both annotations and rationale
2. **Adjudicator decides** the final labels
3. **Adjudicator documents** the decision rationale
4. **Adjudication is recorded** in the annotation record

### 6.2 Disagreement Types

| Type | Description | Resolution |
|------|-------------|------------|
| Missing label | One annotator applied a label the other didn't | Adjudicator reviews and decides |
| Conflicting labels | Annotators applied different labels | Adjudicator reviews and decides |
| Partial overlap | Some labels match, some don't | Adjudicator reviews the disagreements |

### 6.3 Inter-Annotator Agreement

**Target:** Cohen's kappa > 0.7

**Measurement:**
- Compute kappa on a subset of double-annotated segments
- If kappa < 0.7, revise guidelines and retrain annotators
- If kappa < 0.5, halt annotation and investigate

---

## 7. Adjudication

### 7.1 Adjudicator Role

The adjudicator is a senior annotator who:
- Reviews disagreements
- Makes final decisions
- Documents rationale
- Maintains consistency

### 7.2 Adjudication Process

1. Receive disagreement cases
2. Read both annotations and rationales
3. Read the segment and context
4. Apply the taxonomy rules
5. Make a decision
6. Document the rationale
7. Update the annotation record

### 7.3 Adjudication Criteria

The adjudicator should consider:
- Which annotation better follows the guidelines
- Which annotation is more consistent with the taxonomy
- Whether the disagreement reflects genuine ambiguity
- Whether the guidelines need updating

---

## 8. Quality Control

### 8.1 Gold Standard Testing

- 10% of segments are pre-labeled (gold standard)
- Annotators don't know which segments are gold
- Agreement with gold is tracked
- Annotators below 80% accuracy are retrained

### 8.2 Random Review

- Senior annotator reviews 10% of all annotations
- Inconsistencies are flagged and corrected
- Feedback is provided to annotators

### 8.3 Consistency Checks

- Same annotator should produce consistent labels for similar segments
- Label distribution should be reasonable (not all BENIGN)
- Rationales should be substantive (not just "yes" or "no")

---

## 9. Annotator Qualifications

### 9.1 Minimum Requirements

- Native or near-native English speaker
- Understanding of social engineering tactics
- Attention to detail
- Ability to follow guidelines precisely
- Availability for training and calibration

### 9.2 Training Requirements

1. Read TACTIC_TAXONOMY.md completely
2. Complete 10-example training exercise
3. Achieve >80% agreement with gold labels
4. Sign confidentiality agreement
5. Complete calibration session

### 9.3 Ongoing Requirements

- Maintain >80% agreement with gold
- Participate in calibration sessions
- Provide substantive rationales
- Flag ambiguous cases

---

## 10. Annotation Audit Trail

Every annotation must include:

| Field | Description |
|-------|-------------|
| annotation_id | Unique identifier |
| segment_id | Segment being annotated |
| annotator_id | Pseudonymous annotator ID |
| labels | Applied labels |
| confidence | Annotator confidence (0.0-1.0) |
| rationale | Explanation for labels |
| created_at | Timestamp |
| review_status | PENDING, REVIEWED, ADJUDICATED |
| adjudicator_id | If adjudicated, who resolved |

---

## 11. Epistemic Status Rules

### 11.1 What Annotators Can Determine

Annotators can determine:
- **OBSERVED:** What the speaker said (direct text evidence)
- **INFERRED:** What the speaker likely meant (interpretation)

### 11.2 What Annotators Cannot Determine

Annotators CANNOT determine:
- **FACT:** Whether the speaker is actually who they claim to be
- **CONFIRMED:** Whether the user actually performed any action
- **INTENT:** What the speaker actually intended

### 11.3 Annotation Epistemic Status

All annotations are **INFERENCE-level**. We are inferring what tactic is being employed based on the text. We are NOT confirming that:
- The speaker is actually a scammer
- The user actually complied
- The tactic was actually effective

This distinction is critical for LUMINA's safety guarantees.
