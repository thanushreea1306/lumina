# LUMINA ML — Data Acquisition Plan

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Legitimate path to obtaining real, legally usable, segment-level training data.  
**Status:** PLAN COMPLETE — AWAITING EXECUTION

---

## Acquisition Strategy Overview

LUMINA requires segment-level, multi-label annotated data for social-engineering tactic classification in phone conversations. No single existing dataset satisfies all requirements. The recommended path combines:

1. **Public domain government data** (FTC robocall recordings)
2. **Licensed academic data** (LDC corpora for baseline training)
3. **Consent-based user data collection** (LUMINA's own user base)
4. **Expert annotation** (professional annotators with domain expertise)

---

## Source Evaluation

### A. Public Datasets

| # | Dataset | Size | License | Commercial Use | Segment Labels | Verdict |
|---|---------|------|---------|----------------|----------------|---------|
| A1 | Robocall Audio Dataset (FTC/PPoNE) | 1,432 calls | **Public Domain** | **YES** | No (transcript-level) | **USABLE** — transcribe + annotate |
| A2 | Kaggle: Call Transcripts | 60 calls | Unknown | Unknown | No | Too small |
| A3 | Kaggle: YouTube Scam Transcripts | 243 | Unknown | Unknown | No | Scam baiting |
| A4 | Zenodo: Multiclass NLP | 624 | Open | Yes | No | Email/SMS, too small |
| A5 | Kaggle: Augmented Scam | Unknown | CC0 | Yes | No | Augmented/synthetic |

### B. Academic Datasets with Explicit Usable Licenses

| # | Dataset | Size | License | Commercial Use | Segment Labels | Verdict |
|---|---------|------|---------|----------------|----------------|---------|
| B1 | LDC Switchboard-1 | 2,400 calls (260hrs) | LDC License | Research-only | No | Baseline only |
| B2 | LDC Fisher | 11,699 calls (1,960hrs) | LDC License | Research-only | No | Baseline only |
| B3 | LDC CALLHOME English | 120 calls (56hrs) | LDC License | Research-only | No | Too small |
| B4 | Derakhshan et al. | 215 calls | Not specified | Unknown | No | Simulated |

### C. Government/Public-Sector Datasets

| # | Dataset | Size | License | Commercial Use | Segment Labels | Verdict |
|---|---------|------|---------|----------------|----------------|---------|
| C1 | FTC Do Not Call Data | Metadata only | Public Domain | Yes | No (complaints, not transcripts) | Not usable |
| C2 | CFPB Consumer Complaints | Text complaints | Public Domain | Yes | No | Not phone transcripts |
| C3 | FCC Consumer Complaints | Metadata | Public Domain | Yes | No | Not usable |
| C4 | FTC Robocall Audio (PPoNE) | 1,432 calls | **Public Domain** | **YES** | No | **PRIMARY SOURCE** |

### D. Research Datasets with Explicit Commercial-Use Permission

| # | Dataset | Size | License | Commercial Use | Segment Labels | Verdict |
|---|---------|------|---------|----------------|----------------|---------|
| D1 | Composite Scam Transcript | 46,982 | CC BY-NC | **NO** | No | Non-commercial |
| D2 | BothBosu Synthetic | Various | Various | Varies | No | LLM-generated |
| D3 | ScamGen | Various | Research only | **NO** | No | Chinese, synthetic |

### E. Licensed Data Providers

| # | Provider | Type | Cost | Suitability | Verdict |
|---|----------|------|------|-------------|---------|
| E1 | LDC (Linguistic Data Consortium) | Academic corpus | $100-$2,500 | Research-only license | Baseline only |
| E2 | Rev.com / TranscribeMe | Transcription service | Per-minute | N/A (transcription only) | Tool, not data |
| E3 | BioCatch | Behavioral biometrics | Enterprise | Different domain | Not suitable |
| E4 | Pindrop | Voice authentication | Enterprise | Different domain | Not suitable |

### F. Public-Domain or Permissively Licensed Transcripts

| # | Source | Size | License | Commercial Use | Verdict |
|---|--------|------|---------|----------------|---------|
| F1 | FTC Robocall Audio transcripts | 1,432 | **Public Domain** | **YES** | **PRIMARY** |
| F2 | Project Gutenberg (fiction) | Large | Public Domain | Yes | Wrong domain |
| F3 | Court records / legal transcripts | Varies | Public Domain | Yes | Different domain |

### G. Expert-Created Real-World Annotation Datasets

| # | Approach | Description | Cost | Timeline | Verdict |
|---|----------|-------------|------|----------|---------|
| G1 | Professional annotation (Scale AI, Labelbox) | Expert annotators label real transcripts | $5,000-$50,000 | 2-4 months | **RECOMMENDED** |
| G2 | Academic collaboration | Partner with researchers | Grant funding | 6-12 months | Possible |
| G3 | Bug bounty / crowdsourcing | Community annotation | $1,000-$5,000 | 1-3 months | Quality risk |

### H. Expert-Created Real-World Annotation Datasets

This overlaps with G. The key distinction is whether the source transcripts are real or created by experts.

| # | Approach | Description | Verdict |
|---|----------|-------------|---------|
| H1 | Expert-written scam scenarios | Domain experts write realistic scam conversations | **Synthetic — PROHIBITED** |
| H2 | Expert-annotated real transcripts | Experts label real phone call transcripts | **RECOMMENDED** |

### I. User-Consented Data Collection

| # | Approach | Description | Privacy Risk | Verdict |
|---|----------|-------------|-------------|---------|
| I1 | LUMINA opt-in recording | Users consent to record and donate calls | Medium | **RECOMMENDED** |
| I2 | Scam baiter recordings | YouTube scam baiters donate transcripts | Low | Supplementary |
| I3 | Call center recordings | Legitimate call centers donate data | Medium | Different domain |

---

## Recommended Acquisition Path

### Phase 1: Immediate (0-3 months) — Public Domain Data

**Primary Source: FTC Robocall Audio Dataset (PPoNE)**

- **URL:** https://github.com/wspr-ncsu/robocall-audio-dataset
- **Size:** 1,432 calls (96.2% English)
- **License:** Public Domain (FTC government data)
- **Commercial Use:** YES
- **Modality:** Audio + transcripts
- **Labels:** None (requires annotation)

**Action Items:**
1. Download the dataset (public domain, no permission needed)
2. Extract transcripts from metadata.csv
3. Segment transcripts into utterances
4. Expert-annotate segments with LUMINA's 11-label taxonomy
5. Quality control and inter-annotator agreement

**Estimated yield:** ~15,000-25,000 labeled segments (after segmentation + annotation)

### Phase 2: Short-term (3-6 months) — Expert Annotation

**Professional Annotation Service**

- **Providers:** Scale AI, Labelbox, Amazon SageMaker Ground Truth
- **Cost:** $0.10-$0.50 per segment annotation
- **Quality:** Expert annotators with domain training
- **Timeline:** 2-4 weeks per batch

**Action Items:**
1. Design annotation protocol (see ANNOTATION_GUIDELINES.md)
2. Create annotation interface
3. Pilot with 500 segments
4. Refine guidelines based on pilot
5. Full annotation run
6. Quality control and adjudication

### Phase 3: Medium-term (6-12 months) — User-Consented Collection

**LUMINA Opt-In Recording Program**

- **Source:** LUMINA's own user base
- **Consent:** Explicit, informed, voluntary
- **Privacy:** PII detection + de-identification
- **Separation:** Training data separate from operational data

**Action Items:**
1. Design consent protocol (see Section 9)
2. Implement opt-in mechanism in app
3. Collect recordings with consent
4. Transcribe using faster-whisper
5. Annotate with expert protocol
6. Quality control

### Phase 4: Long-term (12+ months) — Scale and Diversify

- Expand user consent program
- Partner with telecom providers
- Collaborate with academic researchers
- Continuous dataset improvement

---

## Licensing Summary

| Source | License | Commercial Use | Training Use | Redistribution |
|--------|---------|----------------|--------------|----------------|
| FTC Robocall Audio | Public Domain | YES | YES | YES |
| LDC Corpora | LDC License | Research-only | Research-only | No |
| User-Consented | Custom consent | YES (per consent) | YES (per consent) | Restricted |
| Expert Annotation | Work-for-hire | YES | YES | YES |

---

## Budget Estimate

| Item | Phase 1 | Phase 2 | Phase 3 | Total |
|------|---------|---------|---------|-------|
| Data acquisition | $0 | $0 | $0 | $0 |
| Annotation (10K segments) | $0 | $5,000-$15,000 | $10,000-$30,000 | $15,000-$45,000 |
| Infrastructure | $500 | $1,000 | $2,000 | $3,500 |
| Quality control | $0 | $2,000 | $3,000 | $5,000 |
| **Total** | **$500** | **$18,000** | **$45,000** | **$63,500** |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Insufficient annotation quality | Medium | High | Pilot study + iterative refinement |
| Annotator disagreement | High | Medium | Clear guidelines + adjudication |
| Privacy breach | Low | Critical | PII detection + de-identification |
| License violation | Low | Critical | Legal review of all sources |
| Dataset too small | Medium | High | Multiple source strategy |
| Class imbalance | High | Medium | Targeted annotation of rare classes |
