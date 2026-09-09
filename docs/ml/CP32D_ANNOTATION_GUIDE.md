# LUMINA ML — CP-32D Annotation Guide

**Document Version:** 1.0
**Created:** 2026-09-08
**Phase:** CP-32D
**Status:** GUIDE DEFINED — NO ANNOTATIONS EXIST

---

## 1. Scope and Source of Truth

Annotators label **only observable evidence in the segment text**. This guide reuses the
canonical taxonomy verbatim from `TACTIC_TAXONOMY.md` (FINAL). Definitions below are the
CP-32D operating rules for annotators; where wording differs, `TACTIC_TAXONOMY.md` is
authoritative.

**The 11 canonical tactic labels:**

1. `AUTHORITY_CLAIM`
2. `THREAT_PRESENTATION`
3. `TIME_PRESSURE`
4. `ISOLATION_TACTIC`
5. `CREDENTIAL_REQUEST`
6. `FINANCIAL_REQUEST`
7. `REMOTE_ACCESS_REQUEST`
8. `IDENTITY_REQUEST`
9. `BENIGN_CONVERSATION`
10. `USER_RESISTANCE`
11. `ADVICE_OR_WARNING`

Plus `UNKNOWN` for indeterminate cases.

**Adding new labels is prohibited.** No annotator, adjudicator, or tooling may introduce
a label outside this set. If the taxonomy proves insufficient during the pilot, the
finding is recorded and escalated to a taxonomy change process — the dataset does not
grow ad-hoc labels.

---

## 2. Segment Annotation Record Schema

```json
{
  "conversation_id": "uuid-v4",
  "segment_id": "uuid-v4",
  "speaker_id": "SPEAKER_A|SPEAKER_B|SPEAKER_UNKNOWN",
  "start_time": 12.4,
  "end_time": 15.9,
  "text": "PII-cleared segment text",
  "tactic_labels": ["AUTHORITY_CLAIM", "TIME_PRESSURE"],
  "annotator_id": "pseudonymous-annotator-uuid",
  "annotation_timestamp": "ISO-8601-UTC",
  "annotation_version": "1.0",
  "evidence_span": [{"start": 0, "end": 34, "quoted_text": "..."}],
  "annotator_notes": "optional free text, PII-free",
  "quality_status": "DRAFT|SUBMITTED|AGREED|ADJUDICATED|REJECTED"
}
```

Rules:

- `text` must be a PII-cleared artifact (`PII_CLEARED`). Annotators never see unapproved
  content.
- `evidence_span` quotes the exact span of the segment text supporting the label. A label
  with no supporting span is incomplete.
- `annotator_notes` must themselves be PII-free; notes are dataset artifacts too.
- `speaker_id` uses pseudonymous labels only.

---

## 3. Multi-Label Support

A single segment can carry multiple tactic labels. This is consistent with the existing
classifier contract (`TacticLabel` multi-label design in `app/incident/ml_intelligence.py`
and the `tactic_labels` list in `DATA_CONTRACT.md`).

- `BENIGN_CONVERSATION` is exclusive with the seven scam-side tactic labels
  (`AUTHORITY_CLAIM`, `THREAT_PRESENTATION`, `TIME_PRESSURE`, `ISOLATION_TACTIC`,
  `CREDENTIAL_REQUEST`, `FINANCIAL_REQUEST`, `REMOTE_ACCESS_REQUEST`). A segment cannot
  be both benign and an active scam tactic; annotate the evidence, and if genuinely mixed,
  split the segment or use `UNKNOWN` plus notes.
- `UNKNOWN` is a standalone label meaning **insufficient evidence to decide**. It is not
  a fifth "skip" — it is an honest outcome.

---

## 4. UNKNOWN — Do Not Force a Label

If the evidence in the segment does not clearly support a label, annotators MUST use
`UNKNOWN`. Forcing a guess to avoid "UNKNOWN" is a quality violation. `UNKNOWN` is
excluded from training targets (existing convention) but its frequency is reported
honestly — a high `UNKNOWN` rate is a signal about segment quality or guideline clarity,
not a failure to hide.

---

## 5. Observable-Evidence-Only Rules Per Tactic

Annotators label what is observable in the segment. They do NOT use context that is not
in the segment, and they never infer tactics from the fact that a conversation is
suspected or classified as a scam.

| Tactic | Label ONLY when... | Do NOT label when... |
|--------|--------------------|-----------------------|
| `AUTHORITY_CLAIM` | The speaker actually claims authority/official identity ("I'm calling from the tax office") | Reporting what someone else said; vague institutional references |
| `THREAT_PRESENTATION` | An explicit or clearly observable threat is present ("your account will be frozen") | Genuine warnings about real risks; past events reported neutrally |
| `TIME_PRESSURE` | Urgency/deadline pressure is actually expressed ("within the next hour") | Routine scheduling references |
| `ISOLATION_TACTIC` | The speaker attempts to isolate the recipient from trusted people/help ("don't discuss this with anyone") | Advice that happens to mention other people |
| `CREDENTIAL_REQUEST` | An actual credential/authentication request is made (password, PIN, OTP) | Talking about credentials abstractly or advising protection |
| `FINANCIAL_REQUEST` | An actual financial/payment request is made | Discussing money without requesting action |
| `REMOTE_ACCESS_REQUEST` | An actual remote-access request is made (software, device control) | Mentions of technical support without control requests |
| `IDENTITY_REQUEST` | A request for identity information is made (DOB, SSN, addresses) | Identity *claims* by the speaker (that's `AUTHORITY_CLAIM`) |
| `BENIGN_CONVERSATION` | The segment is genuinely non-threatening, non-social-engineering conversation | Any segment exhibiting a scam tactic |
| `USER_RESISTANCE` | Actual recipient resistance is observable ("I'm not doing that") | Mere questions that are not refusals/pushback |
| `ADVICE_OR_WARNING` | Actual advice/warning content is present ("you should report that") | Threatening statements (that's `THREAT_PRESENTATION`) |

**The inference ban:** never reason "this call is a scam, therefore this segment is
`THREAT_PRESENTATION`." Label the segment's own content. A scam call contains benign
segments; a legitimate call can contain authority claims.

---

## 6. Annotation Workflow

```
PII_CLEARED segment → Annotator A labels → Annotator B labels independently
    → Agreement computed per tactic
    → Matches → AGREED
    → Disagreements → Adjudicator → ADJUDICATED (final) or REJECTED
```

- Annotators work independently; they do not see each other's labels before submitting.
- The adjudicator sees both annotations plus the guideline and may consult the evidence
  spans; the adjudicator's decision is final and recorded with their own annotator ID.
- Annotators escalate guideline ambiguity to guideline maintainers; they do not patch
  the guide themselves.

---

## 7. Quality Statuses

```
DRAFT        — being worked on
SUBMITTED    — annotator finished one pass
AGREED       — A and B independently produced compatible labels
ADJUDICATED  — disagreement resolved by adjudicator; final label set
REJECTED     — segment unusable (bad segmentation, PII leak, unfixable ambiguity)
```

Only `AGREED` and `ADJUDICATED` segments may enter agreement statistics or manifests.

---

## 8. Annotator Conduct Rules

- Label only from the segment text and timestamps shown. No external research about the
  caller, phone number, or incident.
- Complete every segment: forced-choice is prohibited; `UNKNOWN` is always available.
- Record evidence spans honestly; if you cannot point to the span, you do not have the
  evidence for the label.
- Take breaks; fatigue produces label drift. Sessions are capped by tooling at
  implementation time.
- Report suspected PII leaks in shown text immediately — the segment is pulled from
  annotation and returns to `PII_REVIEW_REQUIRED`.
