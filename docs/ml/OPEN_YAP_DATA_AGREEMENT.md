# Open Yap 1K — License and Data Use Agreement Record

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Separate the sample license from the full-corpus Data Use Agreement, and record exactly what each one claims to permit.  
**Status:** Primary-source record — not legal advice

---

## The central distinction

Open Yap 1K is published under **two different legal instruments**, and they do **not** cover the same material.

| Layer | Instrument | Governs |
|-------|------------|---------|
| Sample on Hugging Face Hub | CC-BY-4.0 | The 8.9-hour, 16-conversation, 8-speaker sample |
| Full corpus | Open Yap 1K Data Use Agreement, Version 1 | The 1,000-hour, 1,602-conversation full corpus, delivered under the DUA |

This is not a subtle point. The repo root `LICENSE.txt` is explicitly a sample license, and the README explicitly says the full corpus is available only on request under the DUA.

---

## Sample license

**URL:** `https://huggingface.co/datasets/TheAgenticDataCompany/open-yap-1k/resolve/main/LICENSE.txt`

**Name:** Creative Commons Attribution 4.0 International, CC-BY-4.0

**Material governed:** the sample only

**Publisher framing:** the LICENSE.txt file is titled "Open Yap 1K — sample dataset".

**Publisher add-on requests:** the sample license file includes a non-binding rider asking users not to attempt to identify any speaker and not to use the audio to create voice clones, replicas, or generative reproductions identifiable as a speaker in the corpus. This rider is not the same as the DUA clauses and should not be treated as equivalent to the full-corpus prohibition text.

**What CC-BY-4.0 is generally known to permit under its own terms:**

- Share and adapt the licensed material
- Commercial use
- With attribution

**What we cannot infer from the sample license alone:**

- That the sample license governs the full corpus
- That the full corpus is freely redistributable
- That voice cloning and re-identification are permitted for the full corpus
- That the full corpus terms are identical to CC-BY-4.0

---

## Full corpus Data Use Agreement

**URL:** `https://theagenticdatacompany.com/open-yap-1k/license`

**Version:** 1

**Parties:** The Agentic Data Company and the Recipient

**Form:** accepted electronically when the access request box is marked

**Nature of the grant:** non-exclusive, non-transferable, non-sublicensable, royalty-free, worldwide, for commercial or research purposes

**Material governed:** the Dataset as delivered to the Recipient, including audio, transcripts, speaker and conversation metadata, per-conversation metrics, manifest, and documentation

---

## Permissions recorded for the full corpus

The DUA explicitly lists the following as permitted:

- Internal commercial or research use, including developing products the Recipient sells
- Training, fine-tuning, adapting, evaluating, benchmarking, and testing Models on the Dataset, including generative speech, speech-to-speech, recognition, diarization, and audio understanding models
- Deploying, licensing, and commercializing those Models and their Outputs
- Creating and using Derived Materials for those purposes
- Internal copies and access for personnel and contractors under the same terms
- Retaining the delivered dataset and Derived Materials after a speaker withdraws, subject to the agreement
- Using the Dataset's own speaker identifiers for speaker verification, diarization, or similar models, provided it does not seek the identity behind the identifier

The DUA also explicitly states that a Model or Output is not restricted by the redistribution clause merely because the Dataset was among the training data.

**Important scope note for LUMINA:** the permitted uses are broad and do include model training and deployment. That is a real advantage relative to many candidate datasets. However, this permission exists only under the DUA, only for the full corpus, and only once a Recipient actually enters the DUA.

---

## Restrictions recorded for the full corpus

The DUA explicitly prohibits or limits the following:

- Redistributing, resharing, sublicensing, reselling, lending, or otherwise making the Dataset or any part of it available to third parties
- Depositing the Dataset in a public repository, shared research archive, model hub, or other third-party repository
- Attempting to identify any Speaker, or link any recording, transcript, or metadata to a name, account, contact detail, external voice sample, or any other external identifier, record, or dataset
- Attempting to reverse the pseudonymous speaker and conversation identifiers
- Creating or configuring a Model to produce a synthetic voice, voice replica, or generative reproduction of a person's voice or likeness that a reasonable person would identify as matching an individual in the Dataset
- Training, tuning, or conditioning a Model on the recordings of a single Speaker or a selected group of Speakers in order to reproduce that voice
- Using a Dataset recording as a reference, prompt, or target for voice conversion or zero-shot voice cloning
- Publishing, selling, or otherwise making available a voice, voice preset, or speaker embedding derived from an individual Speaker
- Holding the Dataset under weaker controls than the Recipient's own confidential material
- Retaining any copy of the Dataset after a breach or after a written request from the Company

The redistribution restriction also applies to Derived Materials to the extent they contain, reproduce, or allow reconstruction of Dataset audio, transcripts, or speaker metadata. It does not restrict publication of Models, Outputs, aggregate statistics, or research results that do not.

Short transcript excerpts of a few sentences from a small number of conversations may be quoted in a publication or presentation where necessary to illustrate a finding. Publishing Dataset audio in any length or form requires the Company's prior written consent.

---

## Privacy and personal-data provisions

- The Dataset contains personal data: recorded voices and self-reported demographic information.
- It is pseudonymized, not anonymous.
- Names, contact details, and account identifiers are not included.
- The Recipient must handle the Dataset in accordance with the data protection law that applies to it.
- The parties act as independent controllers; neither is a processor or joint controller of the other for the personal data in the Dataset.
- The Company remains responsible for the lawfulness of collection and disclosure to the Recipient; the Recipient is responsible for its own processing from delivery onward.

---

## Retention and withdrawal

- The license over a delivery already made is perpetual.
- A Speaker may withdraw at any time. Withdrawal ends further collection and further distribution by the Company, but does not require the Recipient to delete, stop using, or retrain anything already delivered or any Derived Materials.
- The Recipient must permanently delete all copies of the Dataset and all Derived Materials that contain or reproduce Dataset audio, transcripts, or speaker metadata if it breaches the agreement or on written request from the Company, within 30 days.
- Models trained before a deletion event, and Derived Materials that do not contain or reproduce Dataset content, may be retained and used, except where the Model or material is itself the subject of a breach of the re-identification or voice-cloning clauses.
- The Company may ask for compliance confirmation once per twelve-month period.

---

## Warranty posture

- The Dataset is provided "as is" and "as available."
- The Company disclaims warranties including merchantability, fitness for a particular purpose, accuracy, completeness, quiet enjoyment, and non-infringement.
- Transcripts are explicitly described as machine generated and not human verified.
- Demographic fields are self-reported and not verified against any external record.
- Quality figures describe the corpus in aggregate and are not a warranty about any individual file.
- The Company does **not** warrant that no personally identifying information remains.

---

## Limits on what this document concludes

- This document is a record of publisher primary sources, not a legal opinion.
- For LUMINA, the full-corpus permissions are promising but **NOT_VERIFIED** until LUMINA actually enters the DUA, receives a delivery, and confirms which version of the DUA governs that delivery.
- The sample license is useful for inspection and evaluation, but it is not the instrument under which the full corpus would be used.

---

## Bottom line for the LUMINA gate

| Issue | Record |
|-------|--------|
| Sample license | CC-BY-4.0, sample only |
| Full corpus license | Open Yap 1K Data Use Agreement v1, DUA-only access |
| Commercial use | Explicitly permitted under the DUA |
| Model training | Explicitly permitted under the DUA |
| Fine-tuning | Explicitly permitted under the DUA |
| Model evaluation | Explicitly permitted under the DUA |
| Model deployment | Explicitly permitted under the DUA |
| Internal copies and contractor access | Explicitly permitted under the DUA |
| Redistribution | Explicitly prohibited under the DUA |
| Re-identification | Explicitly prohibited under the DUA |
| Voice cloning / identifiable speaker reproduction | Explicitly prohibited under the DUA |
| Attribution | Required for published work using the Dataset |
| Privacy posture | Pseudonymized, not anonymous; screened but not warranted clean |
| LUMINA verification state | NOT_VERIFIED — permitted by text, but no executed DUA and no delivered corpus review yet |
