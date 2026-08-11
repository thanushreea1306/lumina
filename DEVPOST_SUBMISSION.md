# 💡 LUMINA — The Quiet Alarm for India's Digital Arrest Victims

> **Tagline:** Digital arrest scams don't defeat technology — they defeat people's ability to ask for help. LUMINA is the quiet alarm that goes off when someone is trapped inside a scam call, alerting the one person the scammer fears most: a trusted family member.

**Target categories:** 🏆 Most Innovative · 🛡 Most Impactful

---

## The Story That Starts Everything

It's 10:00 AM. A retired teacher picks up a call from an unknown number. The caller says he's an officer from the CBI. Her Aadhaar has been used in a money-laundering case. There's a warrant. She must stay on the line — on a **video call** — while they "verify". She must not call anyone. She must not tell her family. She must keep the phone's screen on.

For the next six hours she will sit, terrified, in a chair. She won't message anyone. She won't switch apps. She won't move. The screen will stay bright in front of her face.

At 4:00 PM she transfers her life savings to "verify her account". It was never her account. It was never the CBI.

**The cruelest part:** during those six hours, no machine in the world flags her. Not the bank. Not the telecom operator. Not the cybercrime helpline. Because she never asked for help — and by design, digital arrest scams make *asking for help impossible*. The victim is psychologically isolated until fear overrides logic.

**LUMINA is built to catch her before the transfer.** Not by waiting for her to report a scam — but by reading the *behavioral fingerprint of being trapped*: the hours-long call, the unknown caller, the video intimidation, and the sudden silence of a phone that has stopped doing anything else.

---

## The Core Insight (Creativity & Innovation)

Every scam-detection system on the market answers one question:

> **"Is this call / message / link suspicious?"**

That question has a fatal blind spot: **it requires the victim to interact with the system.** A digital-arrest victim won't. They've been told not to, and they're too frightened to.

LUMINA answers a completely different question:

> **"Is this person currently trapped inside a scam call, and unable to ask for help?"**

This shift — from *detecting the scam* to *detecting the victim's powerlessness* — is the innovation. Three design consequences follow from it:

1. **Zero victim action.** No panic button, no "report this call" screen. The system works on telemetry the phone already has.
2. **Silent intervention.** The alert targets *trusted contacts* (family), not the victim — the scammer is literally on the other end of the victim's phone and must never know an alarm has been raised. In this demo the alert delivery is **simulated**: the endpoint only builds the alert for HIGH/CRITICAL risk and explicitly returns `delivered: false` with a `SIMULATED` status unless a real delivery channel (Twilio + `LUMINA_TRUSTED_CONTACTS`) is configured.
3. **Explainable, human-centered escalation.** The family gets plain-language reasons ("she's stopped using her phone for 3 hours on an unknown video call"), not a black-box probability.

---

## Real-World Impact

- **₹3,000+ crore** reportedly lost to digital-arrest scams annually in India and **1.2+ lakh** cases reported (press-reported figures, not independently verified)
- An estimated **95% of victims never report** — largely because they only realize the scam *after* the money is gone (public estimate, not independently verified)
- Victims are commonly described as isolated **6–24 hours** — a wide window in which every other safety system is silent
- Digital arrest has **no legal standing in India** — no agency arrests over video call or demands money by phone. This is a pure psychological attack, and psychological attacks need a behavioral (not forensic) defense.

**The impact thesis:** every hour of isolation is an hour the scammer uses to erode the victim's judgment. If LUMINA shortens that window from *hours* to *minutes* — by putting a family member on an alternative number before the transfer — it converts unreportable losses into preventable ones. One prevented transfer at ₹10–50 lakh pays for the entire system.

---

## Technical Implementation (30%)

### Architecture

```
Telemetry snapshot (API / simulator)
        │
        ▼
Feature Extraction ──────────────── 29-feature canonical schema, missing-data flags
        │
        ▼
   ┌────┴────────────┐
   │  XGBoost model   │  ← ML probability (11 call-behavior features, synthetic-demo)
   │  (probability)   │
   └────┬────────────┘
        │  +  0.5
   ┌────┴────────────┐
   │  Safety rules    │  ← explicit, explainable isolation signals
   └────┬────────────┘
        │  +  0.5
        ▼
   Fused score 0–100  →  LOW / MEDIUM / HIGH / CRITICAL
        │
        ▼
   top_factors (from safety_rule_contributions)  →  human-readable "WHY" reasons
        │
        ▼
   SQLite incident log  →  PDF report  →  Streamlit dashboard
```

### Exactly where ML contributes (and where it doesn't)

**ML does exactly one job:** it turns an 11-feature call-behavior snapshot into a scam probability using an `XGBClassifier`.

| Component | Role |
|---|---|
| **XGBoost classifier** ✅ | Converts call behavior (duration, unknown caller, video, hour, call history, outgoing activity, weekend, derived features) into scam probability |
| **Fusion** ✅ | `risk_score = 0.5·ML_probability + 0.5·safety_rules` — ML never decides alone; explicit rules form a **hard evidence ceiling**. The fused score is capped below HIGH when the rule score is below 50 and below CRITICAL when the rule score is below 75, so ML corroborates rule evidence but cannot independently manufacture HIGH/CRITICAL risk. |
| **Explainability** ✅ | Every prediction returns `top_factors`, derived from the engine's `safety_rule_contributions` (reason + weight per active signal), so the "why" is never a black box |
| **Text scam scanner** ⚠️ | **Rule-based** phrase engine (authority impersonation, arrest threats, urgency, financial demand, secrecy). Not ML. A transformer is future work. |
| **IsolationDetector service** ⚠️ | Heuristic weighted score, used by the telemetry simulator demo |

The model was deliberately kept small and interpretable: **11 features, 15,000 synthetic samples**. Feature importance on synthetic data shows the isolation thesis directly — `outgoing_activity_ratio` (60%) dominates, i.e., *a person who has stopped reaching out* is the single strongest signal.

> **Synthetic benchmark (honest):** the deployed classifier is an **XGBoost** model trained on **15,000 synthetic call snapshots**; accuracy 99.88% / F1 99.60% / ROC-AUC 1.00 were measured on data from the *same synthetic generator used at training time*. This is **not** real-world validation — real-world detection performance has **not been measured**; see Limitations.

### What this model is / is not

**It is:** an XGBoost binary risk classifier; an 11-feature call-behavior schema; trained on synthetic call snapshots (15,000 generated calls); a prototype/demo component of the behavioral-isolation detection system — it corroborates call-behavior evidence only, while telemetry/isolation evidence comes from the rule layer.

**It is not:** a validated real-world detector (the benchmark measures internal consistency with its synthetic generator); trained or validated on real-world call telemetry; a substitute for the explicit safety-rule layer, which is a **separate safety mechanism**.

The deployed score currently fuses ML and rules at **50/50**, gated so ML can only corroborate the safety-rule evidence (see Fusion above) — a high ML probability alone can never push a case into HIGH or CRITICAL. The synthetic model remains synthetic-only and is not validated on real-world data.

### Verified behavior (tests + live runs)

- **130/130 automated tests pass** (`pytest tests/ -v`): risk escalation, false-positive guards (unknown caller alone ≠ critical), missing-telemetry safety (including explicitly-null telemetry treated as missing), model-artifact loading failure behavior (unavailable/degraded states), alert abuse protection (cooldown, rate limiting, duplicate suppression), silent-intervention gating (never triggered below HIGH risk, no fake delivery), phase-2 scenario cases, API integration.
- **Live scenario runs through the real API:**
  - Digital arrest: **6.4 → 16.1 → 74.9 → 100 → 100** as signals accumulate (unknown → video → authority claim → full isolation)
  - Normal call: **0 → 0 → 0 → 0 → 0** (stays low despite a brief video segment)

### Backend (FastAPI) — real, working endpoints

| Endpoint | Function |
|---|---|
| `POST /api/score` | Score any call snapshot (call fields + `extra_telemetry`) |
| `POST /api/detect-isolation` | Score device isolation telemetry |
| `POST /api/detect/panic` | Rule-based text scan |
| `GET /api/incidents` | SQLite-backed history |
| `POST /api/generate-report` + `GET /api/download-report/{f}` | ReportLab PDF |
| `POST /api/send-alert` / `silent-intervention` | Demo alerting |
| `GET /api/ngos`, `/api/government-tools` | Support resources |

### Alert service with abuse protection

Demo mode returns `SIMULATED DELIVERY` (no message is actually sent). Real Twilio SMS activates only when env vars are set. Either way, an `AlertGuard` enforces cooldown, per-victim rate limits, and duplicate-incident suppression — abuse-protection built in from day one.

---

## Project Design & UX (15%)

The dashboard is a single screen that a worried family member can read in 5 seconds:

- **Top:** a giant, color-coded **CURRENT RISK** banner (level + score).
- **"WHY WAS THIS DETECTED?"** — plain-language bullets from the engine's contributions.
- **"WHAT SHOULD HAPPEN?"** — concrete human actions (call an alternative number, visit, dial 1930), mapped to risk level.
- **Two one-click scenario buttons** — `🚨 RUN DIGITAL ARREST SCENARIO` and `✅ RUN NORMAL CALL SCENARIO` — which drive the *real* engine through scripted telemetry snapshots, so a judge sees risk escalate (or stay low) in real time.
- **Sections:** Behavior Timeline · Risk Evolution chart · Explanation · Alert Status · Incident Report (PDF download) · Historical Incidents (from SQLite).

The UX philosophy mirrors the safety philosophy: **the person in danger does nothing, and the person who can help sees everything.**

---

## Honest Limitations

This is a research prototype, and we say so plainly:

1. **Synthetic model.** Trained on 15,000 generated calls. Real-world detection performance is unmeasured and requires ethically collected datasets. The benchmark numbers are synthetic-only. The real datasets under `data/datasets/` (Hinglish scam texts, FraudZen CDRs) are **not** used by the deployed model — they were explored only in archived experiments.
2. **Simulated alerts.** SMS is simulated by default; real delivery needs Twilio credentials.
3. **No live integration.** No telecom call-metadata API, no real Android on-device capture (the Kotlin app is a skeleton).
4. **Rule-based text scanner.** No NLP model yet.
5. **Plain SQLite storage.** Incident records aren't hashed and there's no retention window (privacy hardening is roadmap work). The repo's earlier "SHA-256 / 24h deletion" claims were removed because they're not implemented.

---

## Run It (judge-friendly, ~2 minutes)

```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python run.py                       # terminal 1 — API on :8000
streamlit run dashboard/app.py      # terminal 2 — dashboard on :8501
```

Then click **🚨 RUN DIGITAL ARREST SCENARIO** and watch the risk banner climb to CRITICAL as each isolation signal stacks up — then **✅ RUN NORMAL CALL SCENARIO** and watch it stay at 0.

---

## Roadmap

- **V2:** real Android sensing, real SMS/WhatsApp delivery, NLP transcript model, privacy hardening (hashing, retention policy, on-device processing)
- **V3:** telecom call-metadata integration, real-time analysis of an ongoing call, federated learning
- **V4:** national cyber-safety platform, anonymous threat-intelligence sharing, bank transfer-fraud blocking

---

## Built For

**ML Empowerment Build Challenge 2.0** — a demonstration that machine learning can move beyond prediction into *human protection*, using Explainable AI and a human-in-the-loop intervention design.

---

## Team

**Thanushree A** — Solo Builder | AI & ML Developer

---

### One line to remember

> **Digital arrest scams win by making the victim silent. LUMINA makes the silence the alarm.**
