# LUMINA

## AI Bridge Against Digital Arrest Isolation

> **Digital-arrest scams don't defeat technology. They defeat the victim's ability to ask for help. Lumina is the quiet safety bridge that recognizes when someone is becoming isolated and creates a path back to a trusted person.**

**Detect → Analyze → Alert → Protect → Connect**

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

This is **still synthetic evaluation**, not real-world validation.

And it exposed real weaknesses.

The model performs particularly poorly on some short-call cases and becomes less reliable around ambiguous boundaries.

### We chose to report that.

Because a safety system shouldn't pretend to be perfect.

---

# 🧪 Ground-Truth Stress Testing

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

# 🧪 Engineering Validation

The repository currently passes:

> **140 / 140 automated tests**

The deployed model artifacts were also verified to remain unchanged after the stress evaluation.

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
