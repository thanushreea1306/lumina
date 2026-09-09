# LUMINA ML — Real Scam Conversation Data Discovery Report

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Report the results of a broad, source-traced discovery pass for a legitimate, real-world scam/fraud conversation dataset that could eventually supply the scam side of LUMINA's ML problem.  
**Status:** Discovery complete — recommendation is NO_GO for training; CONDITIONAL_GO for one promising lead worth further admission work

---

## 1. Search posture

This pass was intentionally broad and skeptical. We searched across:

- web search
- Hugging Face datasets
- Zenodo
- Mendeley Data
- OSF-style academic repositories (via institutional record pages)
- arXiv preprints and associated dataset descriptors
- GitHub repositories
- known scam/robocall paper trails

We traced each serious candidate back toward an original source wherever possible instead of treating aggregator pages as evidence.

We did not treat scam-baiting material as real victim/scammer behavior unless the source explicitly supports that interpretation.

---

## 2. Candidates pulled into the discovery net

2.1. **FTC / NCSU Robocall Audio Dataset** (`wspr-ncsu/robocall-audio-dataset`)

- Source: GitHub repo and FTC Project Point of No Entry material.
- Nature: real robocall audio recordings.
- Important structural fact: this is primarily **one-sided** caller audio plus a separate local-side track that is explicitly **not transcribed**.
- Prior decision: already assessed as useful for robocall/scam-language auxiliary work but **not** the two-party victim behavioral signal LUMINA needs.
- Verdict: real, legitimate provenance, public domain for the data, but not a primary real two-party scam/victim conversation corpus for this task.

2.2. **TeleAntiFraud-28k**

- Source: arXiv preprint `2503.24115v2` and associated project artifacts.
- Nature: audio-text telecom fraud dataset constructed through real-call ASR processing, LLM-based imitation/augmentation, and multi-agent adversarial synthesis, then rendered to audio with TTS.
- Critical issue: the paper itself describes substantial synthetic/TTS generation and adversarial multi-agent synthesis as part of the corpus construction.
- Verdict: reject under the current non-negotiables. Real-source starting material does not rescue a corpus that is materially built from synthetic/TTS generation and simulated dialogs.

2.3. **BothBosu synthetic scam datasets (general collection and `multi-agent-scam-conversation`)**

- Source: Hugging Face BothBosu collection and dataset page.
- Nature: synthetic multi-turn scam/non-scam phone dialogues between AI agents.
- Critical issue: explicitly synthetic; both the collection framing and the dataset README state synthetic generation with agentic personalities.
- Verdict: reject. Violates the no-synthetic, no-LLM-generated conversation rule.

2.4. **Zenodo “Scam Conversation Corpus” (`15212527`)**

- Source: Zenodo record, with related TU Wien thesis `Honeypot LLM : creation of the scam conversation corpus` (Eder, 2025).
- Nature: conversations with scammers facilitated by GPT-4o, across email/Telegram/Instagram, plus multimedia content descriptions.
- Critical issue: the publisher-facing description says the conversations were facilitated by GPT-4o; the thesis abstract says GPT-4o acted as a potential fraud victim talking to genuine fraudsters, but the dataset record itself describes LLM-facilitated conversations, synthetic personal data, and restricted access.
- This is not a clean “real victim on the recording” corpus from the materials we could inspect at source.
- Verdict: reject as currently understood. If its access mechanism ever opens, it would require careful re-evaluation; but from the primary record we reviewed, it is not a straightforward real two-party phone-call victim corpus.

2.5. **Zenodo “Multiclass NLP Dataset for Phishing and Social Engineering Threat Detection” (`15235123`)**

- Source: Zenodo record.
- Nature: 624 English email/SMS-like messages with phishing/social-engineering/benign labels.
- Critical issues: wrong modality for LUMINA’s phone-call task, too small, no real phone audio, no real two-party phone conversation.
- Verdict: reject.

2.6. **“Exploring LLM-based Real-time Detection of Phone Scams” (Shen et al., 2025)**

- Source: CHI LBW paper `2502.03964v1`.
- Nature: proposes an LLM-based real-time detection framework and evaluates on “authentic” and synthetic datasets.
- Critical issue: the paper’s “authentic” dataset is described as real-world transcripts sourced from public video platforms and transcribed from audio; the paper also states the evaluation datasets were in Chinese.
- That does not yield a clearly accessible, licensed, English, real two-party phone audio corpus from the primary materials we reviewed.
- Verdict: reject as a dataset source for LUMINA in its current form.

2.7. **“Classifying Scam Calls Through Content Analysis With Dynamic Sparsity Top-k Attention Regularization” (D-STAR)**

- Source: IEEE paper `11050370` and related citations.
- Nature: text transcript classification work using a balanced 400 scam / 400 non-scam transcript set.
- Critical issue: the dataset is described as collected from publicly available sources such as social media and news; transcripts are not a clearly licensed, auditable, real two-party phone audio corpus from the materials we reviewed.
- Verdict: reject as a primary LUMINA training source in current form.

2.8. **Kaggle “Call Transcripts Scam Determinations” (`mealss`)**

- Source: Kaggle dataset page.
- Nature: 60 call transcripts labeled scam/not-scam.
- Critical issues: far too small, license not clearly established from the primary record we inspected, uncertain provenance and realism at scale, and transcription-derived text rather than a strategic two-party scam audio asset.
- Verdict: reject.

2.9. **Kaggle “Scam and Non-Scam Call Conversation Dataset” (`teeconnie`)**

- Source: Kaggle dataset page and IEEE citation trail.
- Nature: English scam/non-scam call conversation text.
- Critical issues: from what we could inspect at source, this does not clearly resolve into a licensed, auditable, real two-party phone audio corpus with reliable victim-behavior provenance. Kaggle page text was insufficient for a firm realism/licensing decision.
- Verdict: reject due to insufficient source-level certainty.

2.10. **Mendeley “Arabic Scam and Legitimate Call Conversation Dataset (ASLC-448)”**

- Source: Mendeley Data record.
- Nature: 448 Arabic-dialect scam/legitimate conversations with synthesized TTS audio.
- Critical issues: wrong language for LUMINA’s English task and materially TTS-generated audio.
- Verdict: reject.

2.11. **“Anatomy of a Scam Call” honeypot corpus (Traister et al., 2026)**

- Source: arXiv preprint `2608.24127v1` and referenced companion data descriptor.
- Nature: a closed 54-day corpus of real inbound scam and spam calls to dedicated honeypot numbers answered by an AI voice agent; the paper describes 10,211 calls, 913 hours of audio, and 330,956 transcribed turns from 5,780 distinct originating numbers.
- Realism: the corpus is built from real inbound calls to phone numbers that were never shared with real people; the paper is explicit that the collection was via an AI engagement agent.
- That means it captures **real scammer behavior** and **real two-party dialogue**, but the “victim” side is an AI agent, not a real human victim.
- Access: the paper repeatedly defers to the companion data descriptor and does not clearly establish an open, immediate, unrestricted download from the primary materials we reviewed. In the related `CallScreenBench` preprint from the same environment, the field corpus is stated as not released.
- Verdict: the most interesting real-scam lead in this pass, but it is **not** currently a clean public, fully-licensed, human-victim phone conversation corpus. It is a real two-party dialogue corpus with a synthetic AI victim side and an unresolved public access path.

2.12. **Government / law-enforcement sources in general**

- Sources inspected conceptually: FTC, FCC, FBI, state AGs, consumer-protection complaint flows, court exhibits.
- Result: no clearly reusable, openly licensed, real human two-party scam phone conversation corpus surfaced from these sources in this pass. Complaint databases, cease-and-desist letters, and robocall recordings do not, by themselves, provide the two-party victim behavioral signal LUMINA needs.
- Verdict: no usable LEAD from these sources in this pass.

---

## 3. Serious candidates and why they did not become GO

A candidate became “serious” only if it had a plausible path to real scam-relevant conversation data with at least some access and rights trail.

| Candidate | Why serious | Why not GO |
|-----------|-------------|-------------|
| FTC/NCSU Robocall | Real scam audio, public domain | One-sided; not real two-party victim behavior |
| TeleAntiFraud-28k | Telecom fraud topic; audio+text | Material synthetic/TTS/adversarial synthesis |
| BothBosu datasets | Two-party scam/non-scam framing | Explicitly synthetic LLM-generated dialogs |
| Zenodo SCC (`15212527`) | Captures scammer-side behavior | LLM-facilitated conversations; restricted; not clearly real victim audio |
| D-STAR transcript set | Scam/non-scam transcript framing | Insufficient source-level licensing/realism certainty |
| Kaggle mealss | Real-ish call transcript framing | Too small; license unclear |
| Kaggle teeconnie | English scam/non-scam text | Source-level certainty too weak |
| ASLC-448 | Real-scam topic, annotated | Arabic + TTS audio; not English phone victim corpus |
| Anatomy of a Scam Call corpus | Real inbound scam calls at scale | AI-victim side; unresolved public access/rights; not human-victim two-party audio |

No candidate cleared all of:
- real audio,
- real two-party conversation,
- real human victim behavior,
- English,
- legitimate licensing with commercial ML and annotation clarity,
- accessible without triggering the no-download large-corpus rule,
- sufficient scale and segmentability for LUMINA.

---

## 4. Closest thing found

The strongest lead is the **Anatomy of a Scam Call** honeypot corpus.

It is the only candidate in this pass that clearly reports a large closed corpus of **real inbound scam and spam calls to engaged lines**, with real scammer speech and real two-party conversational turns at scale.

But it has three major problems for LUMINA’s current gate:

1. The “recipient” side is an AI voice agent, not a real victim. That means it can inform scammer behavior modeling but does not directly give LUMINA real victim resistance, hesitation, uncertainty, or response behavior in genuine victim encounters.
2. Public access and exact licensing could not be confirmed from the primary materials reviewed. The paper defers to a companion descriptor, and a related corpus from the same group is described as not released.
3. Even if access were granted, the corpus would still need careful privacy, consent, and rights work before LUMINA could use it.

So this lead is **promising but not admissible yet**.

---

## 5. What the field looks like overall

The uncomfortable conclusion of this pass is that publicly available real scam phone conversation data is either:

- one-sided,
- synthetic or heavily augmented,
- scam-baiting rather than real victim behavior,
- restricted or not clearly accessible,
- wrong language,
- wrong modality,
- too small,
- or a mix of several of the above.

The real-two-party real-victim phone conversation corpus LUMINA wants is not obviously sitting in an open, cleanly licensed, immediately usable form.

That matches the broader shape we already saw in the provenance record: real scam data is scarce, and accessible material tends to be either one-sided, simulated, synthetic, restricted, or weakly licensed.

---

## 6. Licensing, annotation, and privacy findings in aggregate

6.1. **Licensing**
Many candidates had one or more of these problems:
- license not stated in the primary source we inspected,
- license stated only at a venue page without clear corpus-level terms,
- research-only or “upon request” access,
- mixed provenance with unclear rights,
- or explicit synthetic-generation framing tied to the data itself.

For LUMINA, we must mark any such gap as **NOT_VERIFIED** rather than assume permission.

6.2. **Annotation rights**
Even where some use is permitted, that does not automatically imply annotation rights, commercial use of derived labels, private storage of annotated derivatives, or training on those derived labels. Those have to be verified separately.

We did not find a candidate where annotation rights for LUMINA were clearly established from primary sources.

6.3. **Privacy**
Several real-scam-relevant sources are likely to contain sensitive voice and conversational content. Even where names or obvious identifiers are removed, audio can be identifying. Government/complaint-derived material can carry additional provenance and privacy constraints. None of the candidates should be described as “privacy safe” merely because obvious identifiers are absent.

---

## 7. Taxonomy coverage assessment

No candidate surfaced in this pass provided realistic coverage of LUMINA’s 11 tactic signals in a real human victim/scammer two-party telephone conversation with admissible rights.

The only candidate that clearly captures scam-relevant conversational dynamics at scale is the honeypot corpus, but its victim side is AI-generated, and its labels are machine-generated silver labels, not human-annotated tactic segments.

So even the best candidate would only partially touch scam relevance, and only after a separate rights/access/annotation path.

---

## 8. Recommended next action

**Recommendation: NO_GO for training, with one conditional next step.**

1. Do not attempt to train on any of the candidates found in this pass.
2. Do not treat the honeypot corpus as if it were a public, licensed, human-victim English phone conversation corpus.
3. If the team wants to pursue the honeypot corpus seriously, the next step is **admission investigation only**:
   - locate the exact companion data descriptor,
   - confirm whether the corpus is actually available and to whom,
   - confirm the exact license and permitted uses,
   - confirm whether the recipient side is treated as real behavior or as AI-generated engagement,
   - confirm privacy and retention constraints,
   - confirm whether annotation is permitted and whether derived labels can be stored and used commercially.
4. If and only if that investigation comes back clearly positive on access, rights, privacy, and realism for LUMINA’s needs, revisit classification as **CONDITIONAL_GO** with the specific condition documented.
5. Until then, the current legitimate benign side remains Open Yap 1K as auxiliary only, and the missing scam/victim side remains unresolved.

---

## 9. Final board

**GO / CONDITIONAL_GO / NO_GO:**

**NO_GO**

Reasoning: we did not find a legitimate, accessible, real two-party, human-victim English scam phone conversation corpus with clearly established commercial ML and annotation rights. The single most promising real-scam lead still fails the victim-behavior and/or access-and-rights conditions for immediate use.

If a future investigation establishes that the honeypot corpus is actually publicly available under terms that permit LUMINA’s planned use and that its victim side is acceptable for LUMINA’s behavioral questions, the board should be revisited as **CONDITIONAL_GO** with the exact unresolved condition written down.

For now: **do not train, do not download large datasets, do not modify product code, do not commit or push, and do not recruit participants.**
