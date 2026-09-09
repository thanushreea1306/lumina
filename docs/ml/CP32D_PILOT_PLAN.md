# LUMINA ML — CP-32D Staged Pilot Plan

**Document Version:** 1.0
**Created:** 2026-09-08
**Phase:** CP-32D
**Status:** PLAN DEFINED — NO STAGE STARTED

---

## 1. Purpose and Honesty Rule

This plan defines a staged path from protocol validation to production-scale acquisition.
**A small pilot must NOT be presented as production-scale ML evidence.** Pilot results
validate process and infrastructure; they never validate model performance at scale, and
pilot metrics are always labeled with their stage and sample size.

---

## 2. Stages

### STAGE 0 — Protocol Validation
**Goal:** prove the paperwork and plumbing work before any participant is enrolled.

- Dry-run the consent flow end-to-end with internal reviewers acting as mock participants
  (clearly marked as such; their records are flagged `MOCK` and can never enter a
  dataset).
- Exercise the privacy pipeline on a project-authored dummy recording, not participant
  audio.
- Verify every quality gate evaluates honestly (intentionally fail each gate once and
  confirm blocking).
- **Exit criteria:** consent flow produces valid versioned records; privacy pipeline
  produces `PII_CLEARED` artifacts from the dummy input; all 12 gates demonstrably block
  on induced failures; withdrawal path completes the full state chain.

### STAGE 1 — Small Consented Pilot
**Goal:** first real contributions under full protocol.

- A handful of volunteers (target: fewer than 10 participants), fully consented.
- Real recordings of *previously experienced* interactions only — participants are never
  asked to contact scammers (see `CP32D_DATA_ACQUISITION_PROTOCOL.md` and
  `CP32D_PRIVACY_PIPELINE.md` safety rules).
- Full pipeline: consent → acquisition → privacy → STT → segmentation.
- **Exit criteria:** every contributed record has a complete consent record; every
  artifact reaches `PII_CLEARED` or is rejected; zero unredacted PII found in approved
  artifacts during audit; retention and withdrawal tested with at least one real
  withdrawal request.

### STAGE 2 — Annotation Reliability Pilot
**Goal:** prove humans can label consistently with the existing taxonomy and guide.

- Dual annotation of the Stage 1 corpus by two independent annotators, plus adjudication.
- Compute per-tactic agreement **only from real annotations**.
- Measure `UNKNOWN` rate; investigate whether it reflects guideline ambiguity or segment
  quality.
- **Exit criteria:** agreement computed and reported honestly with sample size; every
  disagreement adjudicated; guideline revisions (if any) produce a new guideline version —
  labels are never silently relabeled under a changed guide.
- **Honesty constraint:** small-sample agreement is reported as small-sample agreement.
  It is not evidence of production-scale reliability.

### STAGE 3 — Expanded Acquisition
**Goal:** grow the corpus under the now-validated protocol.

- Requires Stage 2 exit criteria met.
- Add annotator training and calibration sets; monitor agreement per tactic continuously.
- **Exit criteria:** sustained agreement at or above the threshold set by the training
  gate (defined when real data exists — not before); governance audit passes; withdrawal
  handling keeps working at volume.

### STAGE 4 — Production-Scale Dataset
**Goal:** a dataset that can legitimately enter model training.

- Requires Stage 3 exit criteria met and a fresh governance audit.
- Only here may the manifest feed a training run, and only through the existing
  CP-32B/32C gate semantics: no candidate is promoted; the dataset itself must pass the
  acceptance specification.
- **Exit criteria:** full-manifest critical-gate compliance; leakage-free split executed
  and audited; then — and only then — model training becomes discussable.

---

## 3. What Each Stage Validates

| Validation target | Stage |
|-------------------|-------|
| Consent workflow | 0, 1 |
| Privacy workflow | 0, 1 |
| Annotation quality | 2 |
| Annotator agreement | 2 |
| Taxonomy usefulness | 2 |
| Transcript quality | 0, 1 |
| Data governance | 0, 1, 3, 4 |

---

## 4. Prohibitions at Every Stage

- No stage may instruct participants to contact, provoke, or engage scammers.
- No stage may present pilot data as production evidence.
- No stage may create synthetic data to fill gaps between stages.
- No stage may relax a critical gate to meet a timeline.
- No stage may fabricate agreement or performance numbers.
- Stage advancement requires the exit criteria in writing; skipping stages is prohibited.

---

## 5. Current Position

```
CURRENT STAGE = NONE (Stage 0 not started)
```

The next concrete action after CP-32D is CP-32E: implement the consent workflow service
so Stage 0 protocol validation has real machinery to validate.
