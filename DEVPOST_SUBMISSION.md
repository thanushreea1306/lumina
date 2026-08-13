# LUMINA

## AI Bridge Against Digital Arrest Isolation

> **Digital-arrest scams don't defeat technology. They defeat the victim's ability to ask for help. Lumina is the quiet safety bridge that recognizes when someone is becoming isolated and creates a path back to a trusted person.**

**Detect → Analyze → Alert → Protect → Connect**

**Built for the ML Empowerment Build Challenge 2.0**

| Judging criterion | Where Lumina delivers it |
| --- | --- |
| Technical Implementation (30%) | Real FastAPI + XGBoost pipeline, gated hybrid fusion, 140/140 passing tests, frozen-artifact stress benchmark |
| Creativity & Innovation (20%) | Behavioral-isolation detection with a silent trusted-contact bridge — not content-based scam filtering |
| Real-World Impact (20%) | In-progress intervention for digital-arrest victims who can no longer ask for help |
| Design & UX (15%) | Live dashboard driving the real engine, one-click scenarios, explainable evidence |
| Presentation & Documentation (15%) | Honest benchmarks (including measured failure modes), end-to-end reproducibility, 2-minute demo |

---

# 🚨 The Problem

Imagine receiving a call from someone claiming to be a police officer.

They tell you that your identity is connected to a serious crime.

You must stay on the call.

You must not contact your family.

You must follow their instructions immediately.

The call continues for hours.

The victim isn't simply being deceived.

**They are being isolated.**

That isolation is one of the scammer's most powerful tools.

Traditional fraud reporting systems are usually useful **after** money has been transferred or the victim recognizes the fraud.

But during a digital-arrest scam, the victim may be psychologically unable to ask anyone for help.

### We asked:

> **What if the phone could recognize the behavioral pattern of isolation before the victim recognizes the scam?**

That question became **Lumina**.

---

# 💡 Our Core Insight

The scam isn't only visible in the scammer's words.

It can also appear in the victim's behavior.

For example:

* unusually prolonged calls
* unknown callers
* unexpected video calls
* unusual calling hours
* reduced normal communication activity
* limited caller history
* isolation-related telemetry

Individually, these signals may mean nothing.

Together, they can form a behavioral pattern.

### Lumina turns that pattern into an early-warning signal.

The victim doesn't need to:

* identify the scam
* press a panic button
* admit they're being scammed
* remember a reporting number

**The system can recognize the pattern and prepare a bridge to someone outside the trap.**

---

# 🛡️ What We Built

Lumina is a hybrid AI safety system combining:

### 🤖 Machine Learning

An XGBoost classifier analyzes 11 structured call-behavior features.

### 🧠 Safety Rules

Additional telemetry and isolation signals are evaluated through deterministic rules.

### ⚖️ Conservative Fusion

ML and rules contribute equally to the base risk score.

### 🚦 Safety Gates

ML cannot independently force HIGH or CRITICAL escalation without sufficient deterministic evidence.

### 🔍 Explanation

The system exposes contributing factors rather than returning an unexplained score.

### 📲 Intervention

A trusted-contact alert can be constructed when risk becomes sufficiently high.

### 📋 Incident Evidence

Assessments can be persisted and exported as incident reports.

---

# 🧠 How It Works

```text
                  CALL / CONTEXT DATA
                          │
                          ▼
                 CANONICAL FEATURES
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
       11 ML FEATURES          TELEMETRY /
              │                ISOLATION SIGNALS
              ▼                       │
           XGBoost                    ▼
              │                 SAFETY RULES
              │                       │
              └───────────┬───────────┘
                          ▼
                     50/50 FUSION
                          │
                          ▼
                    SAFETY GATES
                          │
                          ▼
                RISK + EXPLANATION
                          │
                ┌─────────┴─────────┐
                ▼                   ▼
          INCIDENT LOG       TRUSTED CONTACT
                                  ALERT
```

---

# 🔬 The ML Layer

The deployed model is an XGBoost classifier operating on 11 behavioral features:

* call duration
* unknown caller
* video call
* hour of day
* caller history
* outgoing activity ratio
* weekend
* log call duration
* early-morning indicator
* late-night indicator
* activity category

Telemetry fields are deliberately excluded from the ML vector and remain available to the deterministic safety layer.

This separation lets Lumina distinguish between:

> **what the model learns**

and

> **what the safety system explicitly enforces.**

---

# ⚖️ Why Hybrid ML + Rules?

We deliberately did not make the ML model the sole decision-maker.

A safety system has asymmetric consequences.

A false negative can mean missing an ongoing scam.

A false positive can unnecessarily alarm a family.

Lumina therefore combines:

```text
50% ML probability
+
50% deterministic safety evidence
```

and then applies conservative escalation gates.

### Risk levels

**CRITICAL:** ≥75
**HIGH:** ≥50
**MEDIUM:** ≥30
**LOW:** <30

The ML layer cannot independently manufacture a HIGH or CRITICAL state when the deterministic evidence does not meet the required threshold.

If the ML artifact is unavailable, Lumina explicitly falls back to rules instead of fabricating a model probability.

---

# 📊 What Did the Model Actually Achieve?

We intentionally separate **development validation** from **stress validation**.

## Controlled synthetic benchmark

On 15,000 controlled synthetic call snapshots:

**99.88% accuracy**
**1.00 ROC-AUC**

However, the generator used strongly class-conditional distributions.

Therefore:

> **We do not claim these numbers represent real-world detection accuracy.**

They validate that the training and inference pipeline learns the controlled development distribution.

---

# 🧪 We Then Tried to Break It

Instead of stopping at the impressive benchmark, we froze the deployed model and created a harder synthetic stress evaluation.

The stress distribution introduced:

* overlapping behavioral distributions
* contradictory evidence
* threshold-boundary cases
* measurement noise
* distribution shift
* out-of-distribution regions

The model was not retrained for this test.

### Stress results

| Metric      |     Result |
| ----------- | ---------: |
| Accuracy    | **74.98%** |
| Precision   | **76.88%** |
| Recall      | **68.39%** |
| F1          | **72.39%** |
| ROC-AUC     |  **0.824** |
| Brier score | **0.2232** |

### Known failure modes (measured, not hidden)

| Slice | n | Metric | Value |
| --- | ---: | --- | ---: |
| Short calls (0–30 min) | 3,697 | scam recall | **0.53%** |
| Boundary cases (threshold-adjacent) | 1,600 | accuracy | 64.6% |
| Boundary cases (threshold-adjacent) | 1,600 | ROC-AUC | 0.705 |
| General stress subset | 5,200 | ROC-AUC | 0.851 |

The honest headline: on short calls the model largely misses scams (0.53% recall), while on long calls it is strong (120–481 min: 94.0% recall). Lumina is designed around the long, isolating digital-arrest call — it is not a general call-scam detector, and we do not present it as one.

This is **still synthetic evaluation**, not real-world validation.

And it exposed real weaknesses.

The model performs particularly poorly on some short-call cases and becomes less reliable around ambiguous boundaries.

### We chose to report that.

Because a safety system shouldn't pretend to be perfect.

---

# 🧪 Scenario-Policy Stress Testing

For the stress evaluation, labels were generated through an explicit scenario-level policy rather than from model predictions.

The policy uses behavioral indicators such as:

* unknown caller
* video call
* prolonged duration
* low outgoing activity
* limited caller history
* unusual calling hours

Boundary cases were deliberately generated around the decision threshold, while contradictory cases combined scam-like signals with strong counter-evidence.

The model was evaluated **after** the labels were established.

This prevents the evaluation from simply measuring the model against its own predictions.

It remains synthetic, but it provides a substantially harder test than the original development benchmark.

One caveat we deliberately state: the scenario policy operates on the **same feature space the model consumes** (duration, activity ratio, caller history, hour). The stress labels are therefore rule-derived from the model's own inputs — not independent real-world ground truth. The benchmark measures whether the model can approximate the scenario rule under noise, distribution shift, and contradictory evidence. It is a harder, honest consistency check, not a claim about real-world detection.

---

# ▶️ See It Run

Every number below was produced by the **real engine through the real `/api/score` endpoint** using the dashboard's own scenario payloads — there is no mock scoring path.

**Digital-arrest scenario** (unknown caller → video pressure → authority claim → isolation → maximum escalation):

| t (min) | Risk score | Risk level |
| ---: | ---: | --- |
| 2 | 6.4 | LOW |
| 20 | 16.1 | LOW |
| 50 | **74.9** | HIGH |
| 90 | 100.0 | CRITICAL |
| 150 | 100.0 | CRITICAL |

Stage 3 is the design's key moment: the ML alone reaches ~99.9% scam probability, but the escalation gate caps the fused score at **74.9 (HIGH)** until the deterministic safety rules independently clear 75.

**Normal-call scenario** (known family number, normal app and message use): the score stays at **0.0** across all five snapshots — no alert.

One click in the demo: in the dashboard, press **RUN DIGITAL ARREST SIMULATION** and watch the score climb 6.4 → 16.1 → 74.9 → 100 → 100, then **RUN NORMAL CALL** and watch it stay at 0.

---

# 🚨 Intervention

When risk reaches a sufficiently high level, Lumina can construct a trusted-contact alert.

### Demo mode

The default system:

* builds the alert
* marks it as simulated
* does not send an external message

### Optional delivery

Twilio integration can be enabled separately.

This gives us a safe demonstration environment while keeping the architecture ready for future real-world integration.

### Design principle

> **Detect quietly. Escalate carefully. Keep a human in the loop.**

> Demo note: the separate `IsolationDetector` heuristic inside the Python telemetry simulator uses its own thresholds and is demo-only. It is not the deployed engine — the dashboard score comes exclusively from `/api/score`.

---

# 🔍 Explainability

Lumina doesn't stop at a number.

The engine produces contributing factors that can be surfaced to the user/operator.

For example, a high-risk assessment can be explained through behavioral evidence such as:

> prolonged call + unknown caller + unusual timing + reduced normal activity

This makes the system easier to inspect and reduces dependence on an unexplained black-box score.

---

# 🔐 Safety & Privacy

Lumina was designed with a conservative intervention philosophy.

Current implementation includes:

* ML/telemetry separation
* alert cooldown and rate limiting
* duplicate suppression
* download path-traversal protection
* local incident logging
* simulated intervention by default
* no automatic escalation by default

### What isn't implemented yet

We explicitly do **not** claim:

* production authentication
* encrypted database storage
* formal retention/deletion enforcement
* live telecom integration
* production Android telemetry collection

These are future engineering requirements, not hidden functionality.

---

# 💻 Technology

**Backend**

* Python
* FastAPI
* Pydantic
* SQLite

**Machine Learning**

* XGBoost
* scikit-learn
* NumPy
* Pandas

**Dashboard**

* Streamlit

**Reports**

* ReportLab / PDF

**Integration**

* Twilio-ready alert layer

**Mobile**

* Kotlin Android skeleton for future telemetry integration

---

# 🛠️ Run It Yourself (~2 minutes)

```bash
pip install -r requirements.txt
python run.py                    # FastAPI backend on :8000
streamlit run dashboard/app.py   # dashboard on :8501
```

Score any call directly:

```bash
curl -s -X POST http://localhost:8000/api/score \
  -H "Content-Type: application/json" \
  -d '{"call_duration_min":165,"is_unknown_number":1,"is_video_call":1,"hour_of_day":10,"caller_call_history":0,"outgoing_activity_ratio":0.03,"day_of_week":2}'
```

That call returns a **HIGH (74.9) gated assessment** — the ML says ~100%, but the deterministic rule evidence alone stays below the CRITICAL gate.

**Key endpoints**

| Endpoint | Purpose |
| --- | --- |
| `POST /api/score` | Fusion risk score + explanation + factors |
| `POST /api/silent-intervention` | Trusted-contact alert (simulated by default) |
| `POST /api/detect/panic` | Rule-based text scanner (not ML) |
| `GET /api/incidents` | Incident history |
| `GET /health` | Model/artifact status |
| `POST /api/generate-report` | PDF incident report |

---

# 🧪 Engineering Validation

The repository currently passes:

> **140 / 140 automated tests**

The stress benchmark used the same frozen, schema-validated artifacts served by the app; no retraining occurred.

This matters because the stress benchmark evaluates the **same frozen model used by the application**, rather than a newly retrained model.

---

# 🌍 Impact

Lumina is designed around a simple intervention hypothesis:

> **If a scammer's strongest weapon is isolation, then the strongest countermeasure may be restoring connection.**

The system doesn't attempt to replace cybersecurity awareness.

It adds another layer:

### Before the victim recognizes the scam.

### Before money is transferred.

### Before isolation becomes irreversible.

---

# 🚀 Future Roadmap

### V2 — Consent-driven Android sensing

Move from simulated telemetry to privacy-preserving, on-device signals.

### V3 — Stronger ML

Build ethically sourced and consented datasets, improve calibration, evaluate subject/session-level generalization, and test robustness across demographic and behavioral variation.

### V4 — Intervention network

Explore trusted-contact workflows, telecom integrations and coordinated cybercrime-support pathways.

---

# 🏆 Why Lumina Is Different

Most fraud systems ask:

> **"Can we identify fraudulent content?"**

Lumina asks:

> **"Can we recognize when a person is becoming isolated while the scam is still happening?"**

That changes the intervention point.

The goal isn't simply to classify a call.

It is to create a **safety bridge around a person who may no longer be able to ask for help themselves.**

---

# Built By

**Thanushree A**

Solo project.

Built around the idea that technology should not only detect threats —

**it should help people reconnect with the people who can protect them.**

---

# Final Message

> **Digital-arrest scams win by making the victim silent.**
>
> **Lumina makes that silence the alarm.**
