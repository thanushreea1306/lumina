# LUMINA ML — CP-32D Data Quality Gates

**Document Version:** 1.0
**Created:** 2026-09-08
**Phase:** CP-32D
**Status:** GATES DEFINED — NO DATA EVALUATED

---

## 1. Gate Model

Every dataset record must be evaluated against the gates below. Each gate takes exactly
one of four statuses:

```
PASS    — requirement verified with evidence
PARTIAL — requirement met with documented limitations (never sufficient for critical gates)
FAIL    — requirement not met
UNKNOWN — could not be verified; absence of evidence is NOT evidence of success
```

**Rule: a record cannot enter training data if a critical gate is FAIL or UNKNOWN.**
PARTIAL on a critical gate also blocks entry (PARTIAL is not PASS). Only an explicit,
evidenced PASS on every critical gate allows eligibility.

---

## 2. Gate Definitions

| # | Gate | Criticality | PASS requires |
|---|------|-------------|----------------|
| 1 | CONSENT | CRITICAL | Valid versioned consent record, state `CONSENT_GRANTED`, document hash verified, all required permissions `true` |
| 2 | REAL_HUMAN_PARTICIPATION | CRITICAL | Real humans on all sides; no TTS, no LLM-facilitated participants, no scam-baiting fabrication of the interaction |
| 3 | AUDIO_INTEGRITY | CRITICAL | Audio loadable, audible, correct duration; corruption or truncation fails |
| 4 | TRANSCRIPT_QUALITY | CRITICAL | Transcript accurately reflects audio (spot-check verified); STT model version recorded |
| 5 | SPEAKER_ATTRIBUTION | CRITICAL | Speaker turns attributed by a verifiable method (channel separation or verified annotation) |
| 6 | TIMESTAMPS | CRITICAL | Segment start/end times present, monotonic, within audio duration |
| 7 | PII_REVIEW | CRITICAL | Artifact state `PII_CLEARED` with a human review record |
| 8 | ANNOTATION_COMPLETENESS | CRITICAL | Every segment labeled (any label including `UNKNOWN`) by two annotators independently |
| 9 | ANNOTATION_AGREEMENT | CRITICAL | Agreement computed from real dual annotations; disagreements adjudicated; metrics derived only from real data |
| 10 | PROVENANCE | CRITICAL | Complete provenance manifest (see `CP32D_DATASET_MANIFEST.md`); no missing fields |
| 11 | LICENSE | CRITICAL | License/consent terms explicitly permit LUMINA's ML training and product use |
| 12 | WITHDRAWAL_STATE | CRITICAL | Withdrawal state is `NONE` (no pending or confirmed withdrawal on any contributing participant) |

Non-critical (informational) gates may be PARTIAL and recorded as limitations:

| Gate | Note |
|------|------|
| TRANSCRIPT_ALIGNMENT | Word-level alignment quality |
| AUDIO_NOISE_LEVEL | Background noise characteristics |
| SEGMENTATION_GRANULARITY | Segment boundaries at natural turns |

---

## 3. Eligibility Computation

```
training_eligible = (
    consent state == CONSENT_GRANTED
    AND privacy state == PII_CLEARED
    AND withdrawal state == NONE
    AND license permits training
    AND every critical gate == PASS
)
```

If any critical gate is FAIL, PARTIAL, or UNKNOWN → record is NOT eligible. There is no
override, no weighted score, and no operator bypass. The only way a record becomes
eligible is for the failing gate to be genuinely re-satisfied and re-evaluated.

`METRIC_STATUS = NOT_AVAILABLE` whenever agreement metrics would be derived from fewer
annotations than actually exist. Metrics are computed from data; they are never asserted.

---

## 4. Gate Evaluation Honesty Rules

- Gates are evaluated per record, from evidence — never copied from another record.
- `UNKNOWN` is the honest default when verification was not performed.
- A gate may not be marked PASS by an automated tool where the definition requires human
  verification (PII review, transcript spot-check, agreement adjudication).
- Every gate evaluation is timestamped and attributed (evaluator ID, method).
