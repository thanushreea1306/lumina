# Open Yap 1K — LUMINA Benign Corpus Gate

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Determine whether Open Yap 1K can legitimately become the BENIGN / NATURAL-CONVERSATION portion of LUMINA's real ML corpus.  
**Status:** Gate record — NO_GO for training; auxiliary candidate only

---

## What this gate decides

This gate asks one question:

> Can Open Yap 1K legitimately provide the BENIGN side of LUMINA's real ML problem?

It does **not** ask whether Open Yap 1K is a scam dataset. It is explicitly not being forced into that role.

It also does **not** approve any labeling, any annotation, or any training use. This is a suitability assessment only.

---

## What Open Yap 1K is

Per primary sources, Open Yap 1K is a corpus of English two-speaker natural conversations captured on the publisher's own platform, with separate tracks per speaker and a shared timeline.

If its claims hold, it is precisely the kind of material that can provide a natural-conversation negative class: ordinary talk, ordinary disagreement, ordinary questions, ordinary financial or health or shopping discussion when those occur in a normal relationship context.

That is a real asset for the benign side of the problem.

---

## What Open Yap 1K is not

Open Yap 1K is not, by itself:

- A scam-corpus
- A positive example source for LUMINA's main tactic classes
- A dataset that establishes behavioral labels automatically
- A dataset with speaker roles such as CALLER and RECIPIENT
- A dataset whose transcripts are human annotation
- A dataset whose sample is representative of the full corpus
- A dataset whose full-corpus rights are verified for LUMINA until the DUA is executed

---

## Benign suitability

### Strongly relevant properties

- Two-speaker natural conversation
- Real-world settings and varied dynamics
- Overlap, interruption, backchannel, quick turns, laughter in the publisher's description
- Ordinary relationship contexts: friends, colleagues, romantic partners, family

These properties are useful for building a benign baseline of how real people talk to people they know.

### Relevant benign behaviors the publisher's description suggests may appear

The publisher describes natural conversation with varied dynamics. That suggests the full corpus could contain examples of:

- ordinary requests
- disagreement
- hesitation
- uncertainty
- questions
- interruptions
- normal urgency
- emotional conversation
- financial discussion
- health discussion
- online-shopping discussion
- authority-related discussion
- ordinary advice
- ordinary refusals

### The crucial constraint

The presence of a behavior in natural conversation does **not** mean it should receive a LUMINA tactic label.

LUMINA labels are behavioral-context labels, not topic labels.

For example:

- ordinary urgency is **not** automatically TIME_PRESSURE
- ordinary advice is **not** automatically ADVICE_OR_WARNING in the LUMINA sense
- ordinary financial discussion is **not** automatically FINANCIAL_REQUEST
- ordinary disagreement is **not** automatically USER_RESISTANCE
- ordinary authority-related discussion is **not** automatically AUTHORITY_CLAIM

A segment from Open Yap 1K may contain subject matter that overlaps with LUMINA's label names while still being benign under LUMINA's definitions.

This is exactly why Open Yap 1K cannot be used as if it were already annotated for LUMINA tactics.

---

## Speaker structure

Open Yap 1K can be represented as:

- SPEAKER_A
- SPEAKER_B

It should not be represented as CALLER and RECIPIENT unless and until there is evidence in the specific conversation that establishes those LUMINA conversational roles.

The publisher's own track labels are "Speaker A" and "Speaker B", which matches the safe representation.

---

## Transcript status and ground truth

Open Yap 1K transcripts are machine-generated, word-level, and not human verified.

For LUMINA purposes:

- the transcript is metadata, not gold annotation
- the audio is the primary signal
- any downstream labeling would need human review under LUMINA's own annotation rules
- the machine transcript cannot be treated as if it were human annotation

This matters because a benign corpus is still a corpus that must eventually be segmented and reviewed for LUMINA purposes if it is to feed a behavioral classifier.

---

## Scale and sample caution

The publisher says the sample is 8.9 hours / 16 conversations / 8 speakers and is hand-picked.

The publisher says the full corpus is 1,000 hours / 1,602 conversations / 239 speakers and is available only under the DUA.

Important:

- The sample is not representative.
- The sample cannot be treated as if it were the corpus.
- The full corpus has not been downloaded or reviewed here.
- Any conclusion about full-corpus suitability is therefore provisional.

---

## Privacy

Open Yap 1K is described as pseudonymized, with names, contact details, and account identifiers excluded, and with transcript screening for PII.

That is encouraging for a benign-corpus candidate, but:

- pseudonymized is not anonymous
- the audio itself may contain identifying information
- the publisher does not warrant that no PII remains
- re-identification is contractually prohibited under the DUA

For LUMINA, this means the corpus would still require its own privacy review before any training ingestion, even if the DUA is executed.

---

## Split potential

The publisher describes stable pseudonymous conversation and speaker identifiers.

That suggests split by:

- `conversation_id`

is at least structurally plausible, and split by:

- `speaker_id` / participant_id

may be possible depending on how the delivered metadata is organized.

However, this has not been verified against delivered files. Any split design must be validated against the actual manifest before use.

The core rule still applies: segments from the same conversation must not be allowed into multiple splits.

---

## Where Open Yap 1K can fit in LUMINA

Best case role:

- REAL_BENIGN_CONVERSATION_CORPUS candidate
- negative / natural-conversation foundation for the benign side of the ML problem

Not a fit for:

- SCAM_CORPUS
- TACTIC_CORPUS
- VICTIM_BEHAVIOR_CORPUS

A realistic LUMINA posture is:

- LUMINA_ROLE: AUXILIARY_ONLY

That means Open Yap 1K can help supply the benign landscape, but it cannot by itself supply the positive behavioral diversity LUMINA needs.

---

## What Open Yap 1K cannot do alone

Open Yap 1K alone cannot train LUMINA's complete behavioral classifier.

In particular, it does **not** by itself establish positive examples for:

- AUTHORITY
- THREAT
- TIME_PRESSURE
- ISOLATION
- CREDENTIAL_REQUEST
- FINANCIAL_REQUEST
- IDENTITY_IMPERSONATION
- REMOTE_ACCESS

unless actual evidence and human annotation later establish those behaviors in the data.

Topic metadata is not sufficient. A conversation that mentions banks, police, urgency, or payments is not automatically a LUMINA tactic segment.

This is the same scientific limitation that applies to natural-conversation corpora generally: the benign side is easier to obtain than the positive side.

---

## Trainer-gate status

Training remains:

**TRAINING_STATUS = NO_GO**

Reasons:

1. Full-corpus commercial ML rights are permitted by DUA text but NOT_VERIFIED for LUMINA because no DUA has been executed.
2. The sample license is CC-BY-4.0 and does not govern the full corpus.
3. No delivery has been reviewed.
4. No LUMINA-specific annotation exists.
5. No split, privacy, or provenance pipeline exists for this corpus in LUMINA's stack.
6. Open Yap 1K cannot by itself provide the positive classes LUMINA needs.

The training gate in `TRAINING_GATE.md` stays NO_GO. This dataset does not change that by itself.

---

## Final classification

| Field | Value |
|-------|-------|
| OPEN_YAP_STATUS | YELLOW |
| BENIGN_CORPUS | CONDITIONAL — can be a benign-foundation candidate, but not yet verified into LUMINA |
| REAL_TWO_PARTY | YES |
| COMMERCIAL_ML | NOT_VERIFIED |
| SYNTHETIC_CONTAMINATION | UNKNOWN |
| TRANSCRIPT_STATUS | MACHINE |
| SPEAKER_STRUCTURE | VALID |
| PRIVACY_STATUS | UNKNOWN |
| LUMINA_ROLE | AUXILIARY_ONLY |
| TRAINING_STATUS | NO_GO |

---

## Recommended posture

If the team wants to pursue Open Yap 1K further, the correct next steps are gate-preserving, not training-enabling:

1. Decide whether LUMINA should request the full corpus under the DUA.
2. If yes, record the exact DUA version accepted and the delivery details.
3. Review the delivered corpus for privacy, content, and usefulness before any ML planning.
4. Treat transcripts as machine metadata, not annotation.
5. Keep Open Yap 1K in the benign-foundation role only.
6. Do not infer LUMINA tactic labels from topic or from the mere presence of ordinary urgency, advice, financial talk, or disagreement.

In short: Open Yap 1K looks like a plausible benign foundational source, but it is not yet in the LUMINA training path, and it should not be described as if it were.
