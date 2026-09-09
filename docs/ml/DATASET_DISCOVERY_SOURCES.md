# LUMINA ML — Dataset Discovery Source Trace

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Record the original-source trail for each serious candidate in the real scam conversation discovery pass.  
**Status:** Source record — not a license opinion

---

## 1. FTC / NCSU Robocall Audio Dataset

- Original source: `https://github.com/wspr-ncsu/robocall-audio-dataset`
- Publisher/paper trail: NC State University technical report TR-2023-1; FTC Project Point of No Entry material referenced in the repo
- What we used as evidence: repo README and dataset description page
- Access model: public repository; data described as public domain
- Material shape: real robocall audio recordings, primarily one-sided caller audio with a separate local-side track that is not transcribed

---

## 2. TeleAntiFraud-28k

- Original source: arXiv preprint `https://arxiv.org/html/2503.24115v2`
- Publisher/paper trail: Ma et al.; associated project at `https://github.com/JimmyMa99/TeleAntiFraud`
- What we used as evidence: preprint text
- Access model: described as open-source dataset and benchmark in the paper
- Material shape: audio-text telecom fraud dataset with substantial synthetic/TTS and multi-agent adversarial generation described in the paper

---

## 3. BothBosu synthetic scam datasets

- Original source: Hugging Face collection `https://huggingface.co/collections/BothBosu/synthetic-data-for-scam-detection`
- Specific dataset page: `https://huggingface.co/datasets/BothBosu/multi-agent-scam-conversation`
- Dataset README: `https://huggingface.co/datasets/BothBosu/multi-agent-scam-conversation/resolve/main/README.md`
- What we used as evidence: dataset page and README
- Access model: public Hugging Face dataset
- Material shape: synthetic multi-turn scam/non-scam phone dialogues between AI agents

---

## 4. Zenodo Scam Conversation Corpus

- Original source: Zenodo record `https://zenodo.org/records/15212527`
- Related thesis: `https://repositum.tuwien.at/handle/20.500.12708/216289`
- What we used as evidence: Zenodo record and thesis abstract/record page
- Access model: Zenodo record publicly accessible; files restricted
- Material shape: LLM-facilitated scam conversations across email/Telegram/Instagram with multimedia descriptions

---

## 5. Zenodo Multiclass NLP Dataset for Phishing and Social Engineering Threat Detection

- Original source: Zenodo record `https://zenodo.org/records/15235123`
- What we used as evidence: Zenodo record
- Access model: open Zenodo dataset
- Material shape: 624 English email/SMS-like messages with phishing/social-engineering/benign labels

---

## 6. Shen et al. real-time phone scam detection paper

- Original source: arXiv preprint `https://arxiv.org/html/2502.03964v1`
- What we used as evidence: paper text
- Access model: paper discusses datasets used; not a direct corpus release page
- Material shape: authentic + synthetic transcript evaluation lineage; paper states datasets were in Chinese

---

## 7. D-STAR scam/non-scam transcript work

- Original source: IEEE paper `https://ieeexplore.ieee.org/document/11050370`
- What we used as evidence: IEEE article page and citation trail
- Access model: paper describes a 400 scam / 400 non-scam transcript set from publicly available sources
- Material shape: text transcript classification dataset lineage

---

## 8. Kaggle “Call Transcripts Scam Determinations”

- Original source: Kaggle dataset page `https://www.kaggle.com/datasets/mealss/call-transcripts-scam-determinations`
- What we used as evidence: Kaggle dataset page and downstream project README `https://github.com/sarnsrun/Call-Transcript-Scam-Detection`
- Access model: Kaggle dataset
- Material shape: 60 call transcripts labeled scam/not-scam

---

## 9. Kaggle “Scam and Non-Scam Call Conversation Dataset”

- Original source: Kaggle dataset page `https://www.kaggle.com/datasets/teeconnie/scam-and-non-scam-call-conversation-dataset`
- What we used as evidence: Kaggle dataset page and IEEE citation trail
- Access model: Kaggle dataset
- Material shape: English scam/non-scam call conversation text

---

## 10. Mendeley ASLC-448

- Original source: Mendeley Data record `https://data.mendeley.com/datasets/p384bgyzz3`
- What we used as evidence: Mendeley Data record page
- Access model: Mendeley dataset
- Material shape: 448 Arabic-dialect scam/legitimate conversations with TTS-generated audio

---

## 11. Anatomy of a Scam Call honeypot corpus

- Original source: arXiv preprint `https://arxiv.org/html/2608.24127v1`
- Related companion descriptor: referenced as `[1]` in the paper; exact landing page not conclusively established from materials reviewed
- Related related paper from same environment: `https://arxiv.org/html/2608.01033v1`
- Author affiliation in paper: scam.ai
- What we used as evidence: paper text
- Access model: not clearly open and immediately available from materials reviewed; paper defers to companion descriptor
- Material shape: real inbound scam/spam calls to AI-answered honeypot lines; 10,211 calls, 913 hours audio, 330,956 transcribed turns from 5,780 distinct originating numbers

---

## 12. Government / law-enforcement search trail

- Sources searched conceptually: FTC, FCC, FBI, state attorneys general, consumer-protection complaint portals, court-exhibit reuse ideas
- Result: no clearly reusable, openly licensed, real human two-party scam phone conversation corpus surfaced from these sources in this pass
- Notes: complaint databases, cease-and-desist letters, and robocall recordings do not by themselves constitute the two-party victim behavioral signal LUMINA needs

---

## Source-review caveat

For several candidates we could only inspect enough to reject or mark uncertain. Where that happened, we did not upgrade uncertain fields to YES. If a candidate is revisited later, it must be re-traced from its original source, not assumed usable from aggregator summaries.
