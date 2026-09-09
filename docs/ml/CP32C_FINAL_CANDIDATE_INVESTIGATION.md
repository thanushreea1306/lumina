# LUMINA ML — CP-32C Final Unresolved Dataset Investigation

**Document Version:** 1.0
**Created:** 2026-09-08
**Purpose:** Resolve the 4 unresolved candidates from CP-32B
**Status:** Investigation complete — NO_GO confirmed
**Decision:** NO_GO

---

## Executive Summary

CP-32B identified 4 unresolved candidates. This phase investigated each using authoritative primary sources.

**Result: All 4 candidates are resolved. None qualify for LUMINA's production ML training.**

| Candidate | Final Classification | Blocking Reason |
|-----------|---------------------|-----------------|
| Open Yap 1K | REJECTED | Not scam-relevant; no tactic labels; DUA required |
| BYU-PCCL | REJECTED | No original dataset; aggregates from other sources |
| YouTube Scam Transcripts | REJECTED | Scambaiter conversations; no audio; no license |
| Anatomy of a Scam Call | REJECTED | AI recipient; dataset not publicly available |

---

## Candidate 1 — Open Yap 1K

### Authoritative Sources
- HuggingFace: `TheAgenticDataCompany/open-yap-1k`
- Dataset card, LICENSE.txt, and full-corpus DUA (reviewed via secondary source analysis)
- LinkedIn announcement by Matias Voldby Drejer (Voice Arena, 3 Sep 2026)
- Third-party analysis (DMarketer Tayeeb, 4 Sep 2026)

### Official Dataset Identity
- **Name:** Open Yap 1K
- **Maintainer:** The Agentic Data Company
- **Publication:** 3 September 2026

### Scale (Publisher-Claimed)
- **Total hours:** 1,000 hours
- **Conversations:** 1,602
- **Speakers:** 239
- **Format:** 48 kHz, 16-bit PCM (full corpus); 48 kHz, 16-bit FLAC (sample)
- **Dual-channel:** Yes — separate speaker tracks preserved

### Public Sample
- 8.9 hours, 16 conversations, 8 speakers
- License: CC-BY-4.0
- Transcripts: Machine-generated (Deepgram Nova-3), NOT human-verified
- Some tracks lack energy above 8 kHz despite 48 kHz sample rate
- Hand-picked, not random draw

### Real Human Participation
**PASS** — Conversations are self-paired friends and family in real rooms on their own devices.

### Conversation Structure
**PARTIAL** — Natural two-speaker English conversation, full-duplex, dual-channel. But these are general conversations, NOT scam/social-engineering interactions.

### LUMINA Tactic Relevance
**FAIL** — Open Yap 1K is a general conversational speech dataset. It contains NO scam calls, NO social-engineering interactions, NO authority impersonation, NO threats, NO urgency tactics, NO credential requests. It is fundamentally irrelevant to LUMINA's behavioral tactic classifier.

### Labels
**FAIL** — No segment-level labels. No tactic annotations. No scam/non-scam labels. The dataset provides raw conversation audio and machine-generated transcripts only.

### Transcript Quality
**PARTIAL** — Machine-generated (Deepgram Nova-3), NOT human-verified. Some tracks have limited frequency content.

### Speaker Attribution
**PASS** — Dual-channel recording preserves speaker identity on separate tracks.

### Timestamps
**PASS** — Shared timeline with overlap information preserved.

### Consent Mechanism
**PARTIAL** — Speakers participated voluntarily. But the exact consent terms for the full corpus are governed by the Open Yap 1K Data Use Agreement, which has not been reviewed.

### Privacy Protections
**PARTIAL** — The LICENSE.txt includes a rider requesting users not identify speakers or create voice clones. But full privacy terms are in the unreviewed DUA.

### License (Public Sample)
- CC-BY-4.0
- Rider: Do not identify speakers, create voice clones, or imply speaker endorsement

### License (Full Corpus)
- **UNKNOWN** — Available on request under the "Open Yap 1K Data Use Agreement"
- The DUA has NOT been reviewed
- Commercial ML training permission has NOT been verified
- Fine-tuning, deployment, and contractor access terms are UNKNOWN

### DUA Requirements
**UNKNOWN** — A DUA is required for the full corpus. The exact terms have not been verified. The public CC-BY-4.0 license applies ONLY to the sample, not the full corpus.

### Commercial ML Training
**UNKNOWN** — The dataset card claims "licensed for commercial use" but the full corpus DUA has not been reviewed. The CC-BY-4.0 sample license does NOT cover the full corpus.

### Voice Restrictions
The LICENSE.txt rider requests no speaker identification, no voice cloning, no generative reproductions identifiable as a speaker.

### Classification: **REJECTED**

**Primary Failure:** LUMINA_TACTIC_RELEVANCE (not a scam dataset) + SEGMENT_LABELS (no labels)

**Blocking Reasons:**
1. Not a scam/social-engineering dataset — fundamentally irrelevant to LUMINA's task
2. No segment-level tactic labels
3. Full corpus DUA not reviewed — commercial ML training rights unknown
4. Transcripts are machine-generated, not human-verified

---

## Candidate 2 — BYU-PCCL

### Authoritative Sources
- GitHub: `BYU-PCCL/scam-call-identification`
- README and repository structure (reviewed directly)

### Official Dataset Identity
- **Name:** Scam Call Identification System (NOT a standalone dataset)
- **Maintainer:** BYU Perception, Control and Cognition Lab (BYU-PCCL)
- **License:** MIT (for code only)
- **Status:** "In development"

### Data Sources (Aggregated)
The BYU-PCCL project aggregates transcripts from multiple sources:
1. YouTube Scam Calls: 243+ transcripts from scam baiting videos
2. Candor Dataset: Legitimate phone call recordings
3. Switchboard Dataset: Standard conversational telephone speech
4. Thai Call Center Dataset: Additional call center conversations
5. Internet Search Calls: Curated scam call examples

### Original Dataset
**FAIL** — BYU-PCCL does NOT have its own original two-party scam conversation dataset. It aggregates from other sources, each with their own licenses and restrictions.

### Real Human Participation
**PARTIAL** — Some sources (YouTube scam baiting) contain real human interactions, but the conversations are between scammers and scambaiters (not real victims).

### Conversation Structure
**PARTIAL** — Mix of real and synthetic sources. The project includes `scripts/generating-synthetic-calls/` for synthetic data generation.

### LUMINA Tactic Relevance
**PARTIAL** — Some transcripts may contain scam tactics, but they are primarily scambaiter interactions (where the "victim" is intentionally wasting the scammer's time).

### Labels
**FAIL** — No segment-level LUMINA tactic labels. The system uses LLM (ChatGPT, Gemini) for feature extraction, but these are not ground-truth tactic annotations.

### Speaker Attribution
**UNKNOWN** — Not clearly documented for the aggregated sources.

### Timestamps
**UNKNOWN** — Not clearly documented.

### License
**PARTIAL** — Code is MIT licensed. But the aggregated data sources have their own licenses:
- YouTube content: Subject to YouTube Terms of Service
- Candor/Switchboard: Academic use licenses
- Thai Call Center: Unknown

### Commercial ML Training
**FAIL** — No verifiable commercial ML training permission for the aggregated data. YouTube content cannot be used for commercial ML training under YouTube's Terms of Service.

### Classification: **REJECTED**

**Primary Failure:** NO_ORIGINAL_DATASET + COMMERCIAL_TRAINING_RIGHTS

**Blocking Reasons:**
1. Not a standalone dataset — aggregates from other sources
2. No original two-party scam conversation data
3. Mixed licenses — no unified commercial ML training permission
4. Includes synthetic data generation
5. No segment-level tactic labels

---

## Candidate 3 — YouTube Scam Transcripts

### Authoritative Sources
- Kaggle: `rivalcults/youtube-scam-phone-call-transcripts`
- Dataset description (reviewed directly)

### Official Dataset Identity
- **Name:** YouTube Scam Phone Call Transcripts
- **Maintainer:** rivalcults (Kaggle user)
- **Size:** 243 transcripts

### Content Description
"243 transcripts of the beginning of conversations with scammers. Sourced from YouTube videos. Most are scammers talking to scambaiters, but includes ..."

### Real Human Participation
**PARTIAL** — The scammer side is real. But the "victim" side is typically a scambaiter (someone intentionally wasting the scammer's time), NOT a real victim.

### Conversation Structure
**FAIL** — These are scambaiter interactions, NOT real victim conversations. The dynamic is fundamentally different:
- Scambaiters intentionally prolong calls
- They use fake identities and stories
- They are not genuinely at risk
- The conversation patterns do not represent real victim behavior

### Audio
**FAIL** — Transcripts only. No audio available.

### LUMINA Tactic Relevance
**PARTIAL** — Scammer-side tactics may be present, but the victim-side behavior is not representative of real victims.

### Labels
**FAIL** — No segment-level labels. No tactic annotations. Binary scam/non-scam labels at most.

### Speaker Attribution
**UNKNOWN** — Not documented.

### Timestamps
**UNKNOWN** — Not documented.

### License
**UNKNOWN** — No license specified. The data is derived from YouTube videos, which are subject to YouTube's Terms of Service.

### YouTube Terms of Service
**FAIL** — YouTube's Terms of Service prohibit automated data collection and commercial use of content. Downloading and reusing YouTube video transcripts for commercial ML training is NOT permitted without explicit authorization from the content creators.

### Commercial ML Training
**FAIL** — No verifiable commercial ML training permission. YouTube content cannot be used for commercial ML training.

### Privacy/Consent
**UNKNOWN** — No consent information available. The original video creators may not have consented to their content being used for ML training.

### Classification: **REJECTED**

**Primary Failure:** SCAMBAITER_CONVERSATIONS + NO_AUDIO + NO_LICENSE

**Blocking Reasons:**
1. Scambaiter conversations, not real victim interactions
2. No audio — transcripts only
3. No license specified
4. YouTube Terms of Service prohibit commercial ML training
5. No segment-level tactic labels
6. Very small scale (243 transcripts)

---

## Candidate 4 — Anatomy of a Scam Call

### Authoritative Sources
- arXiv: 2608.24127 (Ethan Traister et al., 25 Aug 2026)
- ResearchGate publication record
- Paper abstract and methodology (reviewed directly)

### Official Dataset Identity
- **Name:** Anatomy of a Scam Call corpus
- **Authors:** Ethan Traister, Ankit Raj, Jiaqi Gan, Xingyu Shen, Tyler Wu, Yuchen Zhou, Tommy Duong, Kidus Zewde, Siying Chen, Simiao Ren
- **Publication:** 25 August 2026
- **Companion data descriptor:** Mentioned but not publicly accessible

### Scale
- **Calls:** 10,211 inbound scam/spam calls
- **Hours:** 913 hours of audio
- **Turns:** 330,956 transcribed turns
- **Distinct numbers:** 5,780
- **Collection period:** 54 days

### Speaker Structure
**CRITICAL LIMITATION:**

- **Scammer side:** Real human callers
- **Recipient side:** AI voice-agent honeypot

The honeypot is an AI system that:
- Answers inbound calls
- Keeps callers talking
- Uses fictitious identities (10 randomized personas)
- Records and transcribes the conversation

**This is NOT a two-human-party conversation.** The recipient side is an AI agent, not a real human victim.

### Real Human Participation
**PARTIAL** — The scammer side is real human behavior. The recipient side is AI-generated.

### Conversation Structure
**PARTIAL** — Real scammer behavior, but the AI recipient creates an artificial dynamic:
- Real scammers talk to an AI
- The AI's responses are scripted/deterministic
- The conversation pattern differs from real victim interactions
- Scammers may behave differently when talking to an AI vs. a real person

### LUMINA Tactic Relevance
**PARTIAL** — The scammer side contains real social-engineering tactics:
- Authority impersonation
- Urgency/time pressure
- Credential requests
- Identity information requests

But the victim side is AI, so victim resistance/compliance patterns are not real.

### Labels
**FAIL** — The paper analyzes patterns (opening clusters, escalation prediction) but does NOT provide segment-level LUMINA tactic annotations. The labels are:
- Binary scam/spam classification
- Turn-level escalation prediction
- NOT LUMINA 11-tactic labels

### Transcript Quality
**PASS** — Transcribed turns with timestamps. Quality depends on ASR but the paper describes 330,956 transcribed turns.

### Speaker Attribution
**PARTIAL** — Caller/recipient turns are distinguishable, but the recipient is AI, not a real person.

### Timestamps
**PASS** — Turn-level timestamps available.

### Data Availability
**FAIL** — The dataset is NOT publicly available as of September 2026:
- The paper mentions a "companion data descriptor" but no download link is provided
- No HuggingFace dataset card
- No GitHub repository with data
- No public data repository
- Access is NOT obtainable without contacting the authors directly

### License
**UNKNOWN** — No license information is publicly available. The paper does not specify a license for the corpus.

### Commercial ML Training
**UNKNOWN** — No commercial ML training permission has been established. The dataset is not publicly available, so no license terms can be verified.

### Privacy/Consent
**PARTIAL** — The honeypot collected inbound calls from real scammers. The scammers did not consent to recording. The fictitious identities used by the honeypot protect real person privacy. But the legal/ethical framework for this collection is not publicly documented.

### AI Recipient Assessment

**Question:** Is AI_RECIPIENT fatal for PRIMARY_TRAINING, or an AUXILIARY_ONLY limitation?

**Scientific Reasoning:**

For LUMINA's behavioral tactic classifier, the training data needs to represent:
1. Real scammer tactics (ATTACKER behavior)
2. Real victim responses (VICTIM behavior)
3. The interaction dynamics between real humans

Anatomy of a Scam Call provides:
1. ✅ Real scammer tactics (genuine human behavior)
2. ❌ AI-generated victim responses (NOT real human behavior)
3. ❌ Artificial interaction dynamics (scammer-to-AI, not human-to-human)

**Why this matters:**
- LUMINA needs to detect tactics in REAL conversations
- AI recipients may respond differently than real humans
- Scammer behavior may differ when talking to an AI vs. a real person
- The interaction patterns (interruptions, emotional responses, compliance) are not representative

**Verdict:** AI_RECIPIENT = REJECTED for PRIMARY_TRAINING

The dataset could serve as AUXILIARY data for understanding scammer-side patterns, but NOT as primary training data for a behavioral classifier that must operate in real human conversations.

### Classification: **REJECTED**

**Primary Failure:** TWO_PARTY_HUMAN (AI recipient) + DATA_ACCESS (not publicly available)

**Blocking Reasons:**
1. Recipient side is AI voice-agent, not real human — fails TWO_PARTY_HUMAN gate
2. Dataset not publicly available — cannot verify access
3. No license information available
4. No segment-level LUMINA tactic labels
5. Commercial ML training rights unknown

---

## Cross-Candidate Comparison Matrix

| Criterion | Open Yap 1K | BYU-PCCL | YouTube Scam Transcripts | Anatomy of a Scam Call |
|-----------|-------------|----------|--------------------------|------------------------|
| **Real Audio** | PASS | UNKNOWN | FAIL (transcripts only) | PASS |
| **Real Conversation** | PASS (general) | PARTIAL (mixed sources) | PARTIAL (scambaiter) | PARTIAL (AI recipient) |
| **Two Human Parties** | PASS | FAIL (aggregated) | FAIL (scambaiter) | FAIL (AI recipient) |
| **Speaker Attribution** | PASS | UNKNOWN | UNKNOWN | PARTIAL |
| **Timestamps** | PASS | UNKNOWN | UNKNOWN | PASS |
| **Segment Labels** | FAIL | FAIL | FAIL | FAIL |
| **LUMINA Tactic Coverage** | FAIL | PARTIAL | PARTIAL | PARTIAL |
| **Label Provenance** | FAIL | FAIL | FAIL | FAIL |
| **English** | PASS | PASS | PASS | PASS |
| **Scale** | PASS (1,000 hrs) | UNKNOWN | FAIL (243 transcripts) | PASS (913 hrs) |
| **License** | PARTIAL (DUA required) | PARTIAL (mixed) | UNKNOWN | UNKNOWN |
| **Commercial ML Training** | UNKNOWN | FAIL | FAIL | UNKNOWN |
| **Privacy/Consent** | PARTIAL | UNKNOWN | UNKNOWN | PARTIAL |
| **Data Access** | PARTIAL (DUA required) | FAIL (no original data) | PASS | FAIL (not available) |
| **Final Classification** | REJECTED | REJECTED | REJECTED | REJECTED |
| **Blocking Reason** | Not scam-relevant; no labels | No original dataset | Scambaiter; no audio; no license | AI recipient; not available |

---

## License/DUA Analysis

### Open Yap 1K
- **Public sample:** CC-BY-4.0 with rider (no speaker ID, no voice cloning)
- **Full corpus:** Open Yap 1K Data Use Agreement (DUA) — NOT reviewed
- **Commercial ML training:** UNKNOWN (DUA not reviewed)
- **Key distinction:** CC-BY-4.0 applies ONLY to the sample, not the full corpus

### BYU-PCCL
- **Code:** MIT License
- **Data:** Aggregated from multiple sources with different licenses
- **YouTube content:** Subject to YouTube Terms of Service (prohibits commercial ML training)
- **Academic datasets:** Typically research-use only
- **Commercial ML training:** FAIL (no unified permission)

### YouTube Scam Transcripts
- **License:** NONE specified
- **Source:** YouTube videos — subject to YouTube Terms of Service
- **YouTube ToS:** Prohibits automated data collection and commercial use
- **Commercial ML training:** FAIL (YouTube ToS violation)

### Anatomy of a Scam Call
- **License:** UNKNOWN (not publicly documented)
- **Data availability:** NOT publicly available
- **Commercial ML training:** UNKNOWN (cannot verify)

---

## Privacy/Consent Analysis

### Open Yap 1K
- Speakers participated voluntarily (self-paired friends/family)
- LICENSE.txt rider: no speaker identification, no voice cloning
- Full privacy terms in unreviewed DUA

### BYU-PCCL
- Mixed sources — each with different privacy provisions
- YouTube content: public but not consented for ML training
- Academic datasets: typically anonymized

### YouTube Scam Transcripts
- No consent information available
- Derived from public YouTube videos
- Original creators may not have consented to ML training use

### Anatomy of a Scam Call
- Honeypot collected inbound calls from real scammers
- Scammers did not consent to recording
- Fictitious identities protect real person privacy
- Legal/ethical framework not publicly documented

---

## Tactic Label Analysis

### LUMINA's 11-Tactic Taxonomy
1. AUTHORITY_CLAIM
2. THREAT_PRESENTATION
3. TIME_PRESSURE
4. ISOLATION_TACTIC
5. CREDENTIAL_REQUEST
6. FINANCIAL_REQUEST
7. REMOTE_ACCESS_REQUEST
8. IDENTITY_REQUEST
9. BENIGN_CONVERSATION
10. USER_RESISTANCE
11. ADVICE_OR_WARNING

### Candidate Label Coverage

**Open Yap 1K:** NO labels — raw conversation audio and transcripts only
**BYU-PCCL:** NO segment-level labels — LLM-derived features, not ground-truth annotations
**YouTube Scam Transcripts:** NO labels — raw transcripts only
**Anatomy of a Scam Call:** NO LUMINA tactic labels — binary scam/spam classification only

**Conclusion:** NONE of the unresolved candidates provide segment-level LUMINA tactic annotations. This is a fundamental blocker that cannot be resolved by any of these datasets.

---

## Final Classifications

| Candidate | Classification | Primary Failure |
|-----------|---------------|-----------------|
| Open Yap 1K | REJECTED | Not scam-relevant; no tactic labels; DUA required |
| BYU-PCCL | REJECTED | No original dataset; aggregated sources; no commercial rights |
| YouTube Scam Transcripts | REJECTED | Scambaiter conversations; no audio; no license; YouTube ToS |
| Anatomy of a Scam Call | REJECTED | AI recipient; not publicly available; no license |

---

## FINAL DATA STATUS: NO_GO

### Rationale
1. All 4 unresolved candidates have been investigated using authoritative sources
2. All 4 are rejected — none satisfy LUMINA's hard training requirements
3. The fundamental blocker remains: NO public dataset provides segment-level human social-engineering tactic annotations on real two-party English conversations
4. No dataset has verified commercial ML training permission
5. The strongest candidate (Anatomy of a Scam Call) has an AI recipient and is not publicly available

### What LUMINA Needs That Public Datasets Do Not Provide

LUMINA requires:
1. **Real two-party human conversations** — not scambaiter interactions, not AI recipients
2. **Social-engineering scam calls** — not general conversations (Open Yap 1K)
3. **Segment-level tactic labels** — not binary scam/non-scam, not LLM-derived features
4. **Human annotation** — not machine-generated, not LLM-generated
5. **Verified commercial ML training rights** — not "open" or "research use"
6. **English language** — for initial deployment
7. **Sufficient scale** — preferably 1,000+ conversations
8. **Proper consent and privacy protections** — for all participants

No existing public dataset satisfies these requirements.

### Next Research Question

**"How can LUMINA obtain a legally usable, real, consented, two-party English conversation corpus with segment-level human social-engineering tactic annotations?"**

Potential paths (for future investigation):
1. **Consented user recordings** — Partner with users who consent to recording real scam calls
2. **Government repositories** — Explore FTC/FCC recordings with proper licensing
3. **Academic partnerships** — Negotiate access to restricted datasets
4. **Professional annotation** — Commission labeled data from annotation services
5. **Pilot dataset** — Start small, validate approach, then scale

---

## What Was NOT Done in This Phase

- No datasets were downloaded
- No models were trained
- No synthetic data was used
- No metrics were fabricated
- No production code was modified
- No production ML code was modified
- No classifier code was modified
- No STT code was modified

---

## Verification

- All 4 unresolved candidates explicitly evaluated ✅
- Every gate uses PASS/PARTIAL/FAIL/UNKNOWN ✅
- UNKNOWN commercial ML rights → no GO ✅
- Paper-only datasets not treated as accessible ✅
- YouTube content not treated as licensed training data ✅
- AI-generated conversations not treated as real human ✅
- AI recipient explicitly recorded ✅
- Absent segment labels remain absent ✅
- Conversation-level scam labels not silently become tactic labels ✅
- Absent privacy/consent evidence remains UNKNOWN ✅
- No candidate receives PRIMARY status ✅
- NO_GO remains valid ✅
- No dataset files added ✅
- No production ML code modified ✅
- No model training occurs ✅
