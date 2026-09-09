# LUMINA ML — CP-32D Real Data Acquisition & Human Annotation Infrastructure

**Document Version:** 1.0
**Created:** 2026-09-08
**Phase:** CP-32D
**Status:** INFRASTRUCTURE & GOVERNANCE DEFINED — NO DATA COLLECTED, NO MODEL TRAINED
**Predecessors:** CP-32A (inference architecture), CP-32B (dataset acceptance gate), CP-32C (candidate investigation)

---

## Executive Summary

CP-32A established real ML inference architecture. CP-32B established dataset acceptance
gates. CP-32C investigated all remaining public candidates and returned:

```
PUBLIC DATASET STATUS = NO_GO
```

The fundamental missing resource is:

**REAL + CONSENTED + TWO-PARTY HUMAN + ENGLISH** social-engineering conversations with
**SEGMENT-LEVEL HUMAN TACTIC ANNOTATIONS** and **LEGITIMATE ML TRAINING RIGHTS**.

CP-32D builds the infrastructure and protocol required to obtain such data legitimately.
This phase is governance and plumbing only.

---

## The Canonical Data Pipeline

Every contribution must pass through the full pipeline. **No stage may silently fabricate
missing information.** Each stage either produces real artifacts with provenance or the
record halts at that stage with an explicit status.

```
REAL CONSENTED CONVERSATION
    → CONSENT VERIFICATION
    → SECURE ACQUISITION
    → PRIVACY / PII PROCESSING
    → STT
    → SEGMENTATION
    → HUMAN ANNOTATION
    → SECOND ANNOTATION
    → AGREEMENT
    → ADJUDICATION
    → QUALITY GATE
    → PROVENANCE MANIFEST
    → TRAIN/VALIDATION/TEST SPLIT
    → MODEL TRAINING
```

CP-32D defines and tests stages 1–13. Model training (the final stage) remains blocked
until a dataset produced by this pipeline passes every gate.

---

## What CP-32D Does NOT Do

- Does NOT collect real user recordings.
- Does NOT download datasets.
- Does NOT train a model.
- Does NOT create synthetic training data.
- Does NOT create fake labels.
- Does NOT add personal recordings to Git.
- Does NOT modify the production ML classifier.
- Does NOT commit or push.

The only production-audio asset in the repository is `tests/fixtures/otp_scam_call.wav` —
a pre-existing project-authored test fixture (spoken content read aloud for the gated
`RUN_REAL_STT` test). It is not participant data and predates CP-32D.

---

## Framework-Independence Requirement

The dataset record schema, consent model, privacy pipeline, annotation schema, quality
gates, provenance manifest, and split rules are specified as **framework-independent**
artifacts. They depend on:

- The canonical 11-tactic taxonomy (see `TACTIC_TAXONOMY.md` — FINAL)
- The honest-status conventions established by CP-32A/B/C

They do NOT depend on PyTorch, Transformers, the DeBERTa checkpoint format, or any other
training framework. A future training harness consumes the manifest format defined here;
nothing in this phase writes model code.

---

## CP-32D Document Set

| Document | Purpose |
|----------|---------|
| `CP32D_DATA_ACQUISITION_PROTOCOL.md` | This document — master pipeline and phase map |
| `CP32D_CONSENT_MODEL.md` | Versioned consent records, states, withdrawal/deletion |
| `CP32D_PRIVACY_PIPELINE.md` | PII detection, redaction, review states |
| `CP32D_ANNOTATION_GUIDE.md` | Segment schema, observable-evidence-only labeling rules |
| `CP32D_DATA_QUALITY_GATES.md` | PASS/PARTIAL/FAIL/UNKNOWN gates and eligibility |
| `CP32D_DATASET_MANIFEST.md` | Training-manifest format and critical-gate enforcement |
| `CP32D_PILOT_PLAN.md` | Staged pilot (0–4) with explicit stage-exit criteria |

Reference documents this phase aligns with but does not replace:

| Existing document | Relationship |
|-------------------|--------------|
| `TACTIC_TAXONOMY.md` | Canonical 11-label taxonomy — reused verbatim |
| `DATA_CONTRACT.md` | Training-example field contract — extended, not replaced |
| `DATA_PROVENANCE.md` | Public-dataset provenance registry — unchanged |
| `REAL_PILOT_CONSENT.md` | Prior consent draft — superseded by `CP32D_CONSENT_MODEL.md` |
| `CP32B_DATASET_GATE.md` / `CP32C_FINAL_CANDIDATE_INVESTIGATION.md` | NO_GO basis |

---

## Truthfulness Rules (binding)

1. This phase creates infrastructure and governance. It does NOT create training data.
2. It does NOT prove that a dataset exists.
3. It does NOT prove model performance.
4. Agreement metrics may not be reported until real annotations exist
   (`METRIC_STATUS = NOT_AVAILABLE` until then).
5. No stage may fabricate missing information. Missing → explicit status, never a guess.
6. A small pilot must never be presented as production-scale ML evidence.

---

## Repository Artifacts Added by CP-32D

Documentation:

```
docs/ml/CP32D_DATA_ACQUISITION_PROTOCOL.md
docs/ml/CP32D_CONSENT_MODEL.md
docs/ml/CP32D_PRIVACY_PIPELINE.md
docs/ml/CP32D_ANNOTATION_GUIDE.md
docs/ml/CP32D_DATA_QUALITY_GATES.md
docs/ml/CP32D_DATASET_MANIFEST.md
docs/ml/CP32D_PILOT_PLAN.md
```

Tests:

```
tests/test_cp32d_data_governance.py
```

No datasets, recordings, participant records, annotations, or model artifacts are added.

---

## Exact Next Action After CP-32D

**CP-32E — Consent workflow implementation:** turn the consent schema, state machine, and
withdrawal path defined here into a working (but not yet enrolled) service layer with
endpoints and persistence, still with zero participant data. Stage 0 of the pilot plan
(`CP32D_PILOT_PLAN.md`) may then begin protocol validation.
