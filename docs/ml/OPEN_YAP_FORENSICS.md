# Open Yap 1K — Source Forensics

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Primary-source record for the LUMINA benign-corpus gate review.  
**Status:** Gate review record — not a training authorization

---

## Scope and method

This document records what the publisher states, where it states it, and how confident we are in that record.

It does **not** assert that Open Yap 1K is suitable for LUMINA training. Suitability is assessed separately in `OPEN_YAP_LUMINA_GATE.md`.

**Rule applied throughout:** we rely only on publisher primary sources. Third-party summaries were not used as evidence.

---

## Primary sources

| # | Source | URL | Role |
|---|--------|-----|------|
| 1 | Hugging Face dataset page | `https://huggingface.co/datasets/TheAgenticDataCompany/open-yap-1k` | Public dataset metadata and sample distribution point |
| 2 | Repository root tree | `https://huggingface.co/datasets/TheAgenticDataCompany/open-yap-1k/tree/main` | Files actually shipped on the Hub |
| 3 | Dataset README | `https://huggingface.co/datasets/TheAgenticDataCompany/open-yap-1k/resolve/main/README.md` | Publisher description of method, consent, license split, and intended use |
| 4 | Sample license file | `https://huggingface.co/datasets/TheAgenticDataCompany/open-yap-1k/resolve/main/LICENSE.txt` | CC-BY-4.0 governs the **sample only** |
| 5 | Official project page | `https://theagenticdatacompany.com/open-yap-1k` | Publisher's own description, specs, access flow, and corpus comparison |
| 6 | Full corpus Data Use Agreement | `https://theagenticdatacompany.com/open-yap-1k/license` | Governing terms for the **full corpus**, requested under a DUA |

**Confidence in source authenticity:** HIGH for Hugging Face pages and the published BSD-style repository files; HIGH for the publisher's own Web pages; the publisher identity is an entity named The Agentic Data Company, a Delaware corporation according to the DUA.

---

## Claim table

| Claim | Source | Evidence | Confidence |
|------|--------|----------|------------|
| 1,000 hours, 1,602 conversations, 239 speakers | README, project page | Both publisher pages repeat consistent numbers; README says "1000 hours"; dataset info page says full corpus is 1,000 hours, 1,602 conversations, 239 speakers | HIGH for the publisher's representation; the numbers have not been independently recomputed from the delivered corpus |
| Real English two-speaker conversations | README, project page, DUA | README describes a self-pairing app; DUA defines the Dataset as "English two-speaker conversational speech"; project page repeats "two-speaker" | HIGH for the publisher's representation |
| Separate channels for both speakers | README, project page, repo tree structure | README says "both sides are captured as separate tracks"; project page says "Dual (one file per speaker)"; example code expects `a.flac` and `b.flac` | HIGH |
| Shared timeline | README, repo example code | README says "one timeline, by construction"; sample code asserts `len(a) == len(b)` and describes aligned tracks | HIGH for the publisher's representation |
| Explicit participant consent | README, project page, DUA clause 11 | README says "Speakers register, give explicit consent before their first recording"; DUA says "Every Speaker gave explicit consent before recording" | HIGH for publisher record |
| Commercial use and model training permitted under a Data Use Agreement | README, project page, DUA clause 4 | README splits license: sample CC-BY-4.0, full corpus "free for commercial use... under the Open Yap 1K Data Use Agreement"; DUA clause 4 explicitly lists training, fine-tuning, evaluation, and deployment | HIGH for the legal record of the full corpus, conditional on the Recipient actually entering the DUA |
| Free for commercial and research use | README, project page, DUA clause 3 | README and project page both say "free for commercial and research use"; DUA clause 3 says "no fee is payable" | HIGH |

---

## Realism / syntheticity

**AUDIO_STATUS:** Publisher claims real human recordings captured on the publisher's own app, with no scraping. This is a primary-source claim, not an audibly verified fact from our side.

**CONVERSATION_STATUS:** Publisher claims natural, unscripted conversations between friends/family/colleagues/romantic partners, with self-selected partners and free topics.

**SYNTHETIC_STATUS:** Publisher explicitly states the corpus is not scripted and not assigned-topic stranger conversations. The README contrasts it against Fisher/Switchboard in precisely those terms. No claim of LLM-generated or synthesized audio was found in the primary sources.

**CONSENT_STATUS:** Publisher claims explicit pre-recording consent plus payment. DUA clause 11 repeats the consent record.

**Important limitation:** we did not audit the recordings, the collection pipeline, the exclusion pipeline, or the consent records. We only reviewed what the publisher publishes.

---

## Transcript status

**TRANSCRIPT_STATUS:** MACHINE

Evidence:

- README: "Transcripts are machine-generated (Deepgram Nova-3, word-level) and are not human-verified."
- Project page: "Transcription type: ASR, word-level with timings (not human-verified)"
- DUA clause 16: "Transcripts are machine generated and are not human verified."

Publisher claims word-level timestamps exist and that filler/laugh/cough/noise events are tagged separately. That metadata structure is plausible from the described transcript schema, but it has not been verified against delivered files.

**Ground truth rule:** the audio should be treated as the primary signal. The transcripts are not human gold annotation.

---

## Speaker structure

**SPEAKER_STRUCTURE:** VALID as SPEAKER_A / SPEAKER_B

The publisher describes two speakers per conversation with separate tracks and stable pseudonymous identifiers. The current publisher labels are "Speaker A" and "Speaker B".

LUMINA-specific conversational roles such as CALLER and RECIPIENT are **not** established by this dataset. The dataset should be modeled as SPEAKER_A / SPEAKER_B until evidence in the corpus establishes a LUMINA role.

---

## Privacy and PII

**PRIVACY_STATUS:** UNKNOWN from our side; publisher describes pseudonymization and screening.

What the publisher claims:

- Names, contact details, and account identifiers are excluded.
- Speaker identifiers are pseudonymous and stable within the release.
- Demographics are self-reported and not inferred from audio.
- Transcripts are screened with an LLM for personally identifying information, and flagged conversations are excluded.
- DUA clause 7 prohibits re-identification and linking recordings to external records.
- DUA clause 8 prohibits voice cloning / generative reproductions identifiable as a corpus speaker.

What we do **not** claim:

- That the audio contains zero PII.
- That pseudonymization prevents all re-identification routes.
- That the screen is perfect.

The publisher itself does not warrant that no PII remains; DUA clause 16 says the Dataset is screened for PII but the Company does not warrant that none remains.

---

## Scale and sample interpretation

**Full corpus (publisher claim):**

- 1,000 hours
- 1,602 conversations
- 239 speakers
- Available only under the full-corpus DUA
- Not downloadable from the Hub

**Sample (publisher claim):**

- 8.9 hours
- 16 conversations
- 8 speakers
- CC-BY-4.0
- Hand-picked, not random

**Important rule:** the sample is not representative of the full corpus, and nothing about the sample's distribution should be extrapolated to the full corpus. The README states this explicitly.

---

## Final gate descriptors from this forensics pass

These are source-record descriptors, not training authorizations.

| Field | Value |
|-------|-------|
| OPEN_YAP_STATUS | YELLOW — primary sources are coherent and largely consistent, but access, training rights, and corpus-level content still depend on the DUA and on material review |
| BENIGN_CORPUS | CONDITIONAL — natural conversation claim is strong, but benign-ness for LUMINA is a labeling/decision question, not a property of the raw corpus |
| REAL_TWO_PARTY | YES — per publisher primary sources |
| COMMERCIAL_ML | NOT_VERIFIED — permitted by DUA clause 4, but not yet verified for LUMINA because no DUA has been executed and no corpus content has been reviewed |
| SYNTHETIC_CONTAMINATION | UNKNOWN — no evidence of synthetic generation in primary sources, but no independent audit either |
| TRANSCRIPT_STATUS | MACHINE |
| SPEAKER_STRUCTURE | VALID as A/B |
| PRIVACY_STATUS | UNKNOWN |
| LUMINA_ROLE | AUXILIARY_ONLY — at most a benign/natural-conversation foundation candidate, not a complete corpus and not a scam dataset |
| TRAINING_STATUS | NO_GO |

---

## Notes and caution

1. The dataset card and README are internally consistent about the license split between sample and full corpus. Do not treat CC-BY-4.0 as if it governs the full corpus.
2. The full corpus terms are conditional on entering the DUA. Until that happens, commercial ML rights for LUMINA remain NOT_VERIFIED.
3. Even if the DUA is executed, Open Yap 1K is a natural-conversation corpus, not a scam-behavior corpus. It does not contain positive evidence for the main LUMINA tactic classes by itself.
