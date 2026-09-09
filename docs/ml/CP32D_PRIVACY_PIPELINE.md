# LUMINA ML — CP-32D Privacy / PII Pipeline

**Document Version:** 1.0
**Created:** 2026-09-08
**Phase:** CP-32D
**Status:** PIPELINE DEFINED — NO DATA PROCESSED

---

## 1. Pipeline Stages

```
RAW_AUDIO
  → TEMPORARY_PROCESSING
  → TRANSCRIPT
  → PII_DETECTION
  → REDACTION
  → PRIVACY_REVIEW
  → APPROVED_DATASET_ARTIFACT
```

Stage rules:

- **RAW_AUDIO** exists only inside the secure boundary (§8). Never in Git, never on the
  frontend, never at a public URL, never in logs.
- **TEMPORARY_PROCESSING** is temporary wherever possible: raw audio is deleted as soon as
  the derived artifact it is needed for exists and `voice_retention = false`, or at the
  end of the retention period, whichever comes first.
- **TRANSCRIPT** may itself contain PII — it is untrusted input to the next stage, not an
  approved artifact.
- **PII_DETECTION** is automated detection + mandatory downstream review. It is NOT
  claimed to be perfect.
- **REDACTION** replaces detected PII with typed placeholders (e.g., `[PHONE_REDACTED]`).
  Redaction never fabricates replacement content — a placeholder, not an invented value.
- **PRIVACY_REVIEW** is human-approval. No artifact leaves this stage without it.
- **APPROVED_DATASET_ARTIFACT** is the only form in which content may enter annotation,
  manifests, or training.

---

## 2. PII Categories and Handling

| Category | Examples | Handling |
|----------|----------|----------|
| Names | person names, nicknames, usernames | Redact in approved artifacts; pseudonymize speakers as `SPEAKER_A`/`SPEAKER_B` |
| Phone numbers | caller IDs, numbers read aloud | Redact (digits and spoken forms) |
| Email addresses | any address, spoken or typed | Redact |
| Addresses | home/work addresses, postal codes | Redact |
| Account numbers | bank/account/IBAN | Redact |
| Card numbers | PANs, partial card digits | Redact; never store CVV under any circumstance |
| OTP / authentication codes | one-time codes, verification codes | Redact; **never** preserve a live code |
| Passwords / PINs | spoken or typed secrets | Redact; never persist outside the transient processing window |
| Government identifiers | SSN/passport/national ID | Redact |
| URLs | links read aloud or sent | Redact |
| Financial information | balances, salaries, transaction amounts tied to identity | Review; redact where identifying |
| Device identifiers | IMEI, serials, device names | Redact |
| Voice identity | the speaker's voice itself | Governed by `voice_retention` permission; default is deletion after processing |

**Temporary processing need exception:** if a category is needed transiently (e.g., STT
must hear an OTP to transcribe surrounding text), the specification requires immediate
redaction from the derived transcript and deletion from the transient store at the end of
the processing step. The approved artifact must never contain the secret.

---

## 3. Honesty About Detection Limits

- Automated PII detection is probabilistic. It WILL miss things. It is never described as
  complete or perfect in any artifact, docstring, or report.
- Because detection is imperfect, **human privacy review is mandatory** before any
  artifact is approved. Automation reduces reviewer load; it never replaces approval.
- Reviewers may sample or review exhaustively; the review record must state which.

---

## 4. Privacy States

```
PII_REVIEW_REQUIRED — detection finished, awaiting human review (default after detection)
PII_REDACTED        — redactions applied, human review still pending
PII_CLEARED         — human review passed; artifact approved as privacy-safe
PII_REJECTED        — review failed; artifact excluded from the dataset and handled
                      per withdrawal/deletion rules
```

Only `PII_CLEARED` artifacts may proceed to annotation, manifests, or training.

---

## 5. Redaction Rules

- Replace with typed placeholders, never synthetic realistic values (inventing a fake but
  plausible card number is fabrication and is prohibited).
- Preserve tactic-relevant structure where safe: "he asked for the code" is evidence;
  the code itself is not.
- Log redaction events (category, count, location) — never the redacted values — with
  provenance linking to the pipeline version that performed them.
- PII detection and redaction of dataset artifacts are implemented at artifact
  preparation time, before review. No unapproved artifact is ever readable by annotators.

---

## 6. STT Interaction

- STT runs inside the secure boundary on raw audio under a valid consent record with
  `transcription = true`.
- STT output (raw transcript) enters `PII_DETECTION` immediately; raw transcripts are
  never approved artifacts and never leave the boundary.
- The STT model version used is recorded in provenance (`stt_model_version`), so a
  transcript can always be traced to the model and pipeline that produced it.
- Speaker attribution is preserved as structural metadata (channel or turn order), not as
  real names. Speakers are pseudonymized to `SPEAKER_A`/`SPEAKER_B`.

---

## 7. Withdrawal Integration

Privacy states interact with withdrawal as follows:

- `PII_REVIEW_REQUIRED`, `PII_REDACTED`: artifact not yet approved; on withdrawal it is
  deleted — nothing of value is lost.
- `PII_CLEARED`: on withdrawal, delete audio, transcripts, annotations, and mark manifest
  entries ineligible (see `CP32D_CONSENT_MODEL.md` §4).
- `PII_REJECTED`: excluded already; retained only per deletion policy, then destroyed.

Withdrawal states:

```
WITHDRAWAL_REQUESTED → WITHDRAWAL_CONFIRMED → DATA_DELETED → DERIVED_DATA_HANDLED
```

---

## 8. Storage Zones

| Zone | Contents | Access |
|------|----------|--------|
| RAW zone | Raw audio, transient STT work area | Minimal personnel; encrypted at rest; temp where possible |
| WORK zone | Raw transcripts, detection reports, redaction diffs | Annotators have NO access; privacy reviewers only |
| APPROVED zone | Redacted, reviewed, approved artifacts + annotations | Annotators and pipeline, per role |
| PUBLIC zone | Training manifest summaries, metrics (only after they genuinely exist) | Repository-visible |

Raw recordings are:

- encrypted at rest,
- access controlled,
- temporary where possible,
- excluded from Git, excluded from the frontend, excluded from public URLs, excluded
  from logs.

Derived training artifacts (APPROVED zone) have their own access policy and are not
automatically as restricted as raw audio — but are still excluded from public URLs and
from Git until the manifest gate approves them.

No cloud storage is implemented in this phase. These zones define the boundary a future
implementation must satisfy.

---

## 9. Prohibited Content in Approved Artifacts

Approved artifacts must never contain: passwords, OTP values, PINs, card numbers, bank
credentials, authentication secrets, government ID numbers, or live voice when
`voice_retention = false`. Tests in `tests/test_cp32d_data_governance.py` enforce this.
