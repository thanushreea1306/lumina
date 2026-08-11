# 💡 LUMINA — AI Bridge Against Digital Arrest Isolation

> **Digital arrest scams trap victims in psychological isolation until fear overrides logic. LUMINA is an AI-powered safety bridge that silently detects these behavioral patterns and alerts trusted contacts—without requiring the victim to recognize the scam or ask for help.**

---

## 🚦 Status Legend

Every feature in this README is honestly labelled:

| Label | Meaning |
|:---:|---|
| ✅ **IMPLEMENTED** | Working, tested code in this repository today |
| 🟡 **SIMULATED** | Functional demo / simulation of the real-world mechanism (no live integration) |
| 📝 **FUTURE** | Planned, designed, or skeleton-only — not working yet |

---

## 📌 The Problem

Digital arrest scams have become one of the fastest-growing forms of cybercrime. Victims are impersonated by fake police officers, CBI officials, or government agencies and are forced to remain on long video calls while being threatened with arrest.

**During these attacks:**

- Victims are commonly reported to remain isolated for **6–24 hours**
- Phones are monitored continuously
- Victims are instructed not to contact anyone
- Fear overrides rational decision-making
- Many lose life savings before realizing it was a scam

₹3,000+ crore lost annually · 1.2+ lakh cases reported · an estimated 95% of victims never report — press-reported figures, not independently verified

Traditional cybercrime reporting tools only help **after** the fraud has happened.

The real challenge is that **victims are psychologically unable to seek help while the scam is happening.**

---

## 💡 Our Solution

LUMINA is an **AI-powered digital safety system** that detects the behavioral signature of an ongoing digital arrest scam.

Instead of waiting for victims to report fraud, LUMINA analyzes behavioral indicators such as:

- unusually long calls
- repeated unknown callers
- isolation patterns
- reduced outgoing activity
- suspicious communication behavior

When multiple signals indicate high risk, LUMINA silently builds a trusted-contact alert so family can intervene before financial loss occurs. In demo mode the alert is **built but not delivered** — the API explicitly marks it `SIMULATED` / `delivered: false` unless a real delivery channel is configured (`LUMINA_ALERT_MODE=real` + Twilio credentials + `LUMINA_TRUSTED_CONTACTS`). The victim never needs to recognize the scam or press an emergency button.

---

## 🧠 Why LUMINA is Different

Most scam detection systems answer:

> "Is this message or call suspicious?"

LUMINA answers a different question:

> **"Is this person currently trapped inside a digital arrest scam and unable to ask for help?"**

That shift—from scam detection to victim intervention—is the core innovation.

---

## ✨ What is REAL Today (Feature Status)

| Feature | Description | Status |
|---|---|---|
| 🧠 Behavioral Risk Engine | Fused XGBoost probability + explicit safety-rule signals | ✅ IMPLEMENTED |
| 🔍 Explainable Risk | Every high-risk call returns the exact reasons (bullet list) | ✅ IMPLEMENTED |
| 📞 Call Scoring API | `POST /api/score` risk score + level for any call snapshot | ✅ IMPLEMENTED |
| 📱 Isolation Detection API | `POST /api/detect-isolation` scores device telemetry | ✅ IMPLEMENTED |
| 🗂 Incident History | Every scored call logged to SQLite (`/api/incidents`) | ✅ IMPLEMENTED |
| 📄 Incident Report (PDF) | ReportLab-generated FIR-style PDF (`/api/generate-report`) | ✅ IMPLEMENTED |
| 🔕 Silent Intervention | Builds a ready-to-send silent alert for HIGH/CRITICAL risk only; demo mode never claims delivery | ✅ IMPLEMENTED (message only, simulated) |
| 📱 Trusted Contact Alerts | Demo-mode SMS simulation with cooldown/rate-limit abuse protection | 🟡 SIMULATED (Twilio optional) |
| 📝 Text Scam Scanner | Rule-based phrase engine (not ML) | ✅ IMPLEMENTED (rule-based) |
| 📊 Streamlit Dashboard | Risk header, WHY/WHAT sections, scenario runner, charts, history | ✅ IMPLEMENTED |
| 🎬 Scenario Simulator | Scripted digital-arrest + normal-call snapshots that drive the real engine | 🟡 SIMULATED (scripted data) |
| 🤖 Android Device Simulator | Python-generated telemetry for scam/normal device states | 🟡 SIMULATED |
| 📱 Android App (on-device) | Kotlin skeleton (`MainActivity` demo UI, `CallReceiver`, `LuminaService`); its "Simulate Scam Call" button is a UI simulation and does not prove alert delivery | 📝 FUTURE (skeleton) |
| 📡 Telecom / call-metadata integration | Live call capture from a phone/network | 📝 FUTURE |
| 🗣 NLP (BERT/RoBERTa) transcript model | Currently rule-based phrase matching | 📝 FUTURE |

### Dashboard & dashboard of record

- The **dashboard** runs real calls against the real risk engine — the scenario buttons POST telemetry to the live backend API and render whatever the engine returns.
- The **isolation score** shown in the dashboard comes from the canonical risk engine, not a canned number.

---

## 📱 Isolation Detection Signals

LUMINA detects **behavioral isolation patterns** that mark a person trapped inside a call:

| Signal | What It Detects |
|---|---|
| Call duration | Long calls (60+ min) |
| Unknown caller | Scammer characteristic |
| Video call | Intimidation tactic |
| Screen time on call | Isolated behavior |
| No app switches | Trapped behavior |
| No home presses | Frozen state |
| No SMS activity | Isolation signal |
| No social app activity | Silenced victim |
| Static location | Not moving |
| High brightness | Hyper-vigilant |
| Persistence hours | Interaction that will not end |

**Why this matters:** detects when someone is **trapped** on a call, not just a suspicious call. 🟡 Device telemetry is currently fed by a **simulator**; real on-device capture is the Android app (📝 FUTURE).

---

## ⚙️ System Workflow

```text
📞 Call / device telemetry snapshot
        │  (✅ live via API · 🟡 simulator · 📝 real device future)
        ▼
🔍 Feature Extraction Engine            ✅ app/core/features.py
        │
        ▼
🧠 XGBoost Risk Classifier (synthetic-demo)   ✅ app/core/risk_engine.py
        │                                        (ML probability)
        ▼
📏 Explicit Safety-Rule Signals        ✅ (duration, unknown, video,
        │                                 isolation telemetry)
        ▼
🎯 Fused Score + Risk Level             ✅ 0–100 → LOW/MEDIUM/HIGH/CRITICAL
        │
        ▼
💬 Human-readable reasons              ✅ top_factors (from safety_rule_contributions)
        │
        ▼
🗂 Incident logged to SQLite            ✅ data/incidents.db
        │
        ▼
🔕 Family Alert                          🟡 simulated SMS · 📝 real delivery
        │
        ▼
📄 PDF Incident Report                   ✅ ReportLab
        │
        ▼
📊 Streamlit Dashboard                   ✅ dashboard/app.py
```

---

## 🏗 Architecture

```text
+----------------------------+
|  Telemetry sources         |   ✅ API · 🟡 simulator · 📝 Android app
+-------------+--------------+
              |
              v
+----------------------------+
|  Feature Extraction Layer  |   ✅ app/core/features.py (canonical 29-feature schema)
+-------------+--------------+
              |
              v
+----------------------------+
|  XGBoost Risk Classifier (synthetic-demo) | ✅ 11 call-behavior features
+-------------+--------------+
              |  probability
              v
+----------------------------+
|  Safety-Rule Layer         |   ✅ explicit, explainable, non-ML signals
+-------------+--------------+
              |
              v
+----------------------------+
|  Fused Risk Engine         |   ✅ score = 0.5·ML + 0.5·rules, gated to the safety-rule evidence ceiling |
+-------------+--------------+
              |
      +-------+--------+
      |                |
      v                v
 Explainability      Alert Service       ✅ both
      |                |
      +-------+--------+
              |
              v
      Incident Store    PDF Report        ✅ SQLite · ReportLab
              |
              v
      Streamlit Dashboard                 ✅ app.py
```

---

## 🤖 Machine Learning — Exactly Where ML Contributes

**ML is used in exactly one place:** converting the *call-behavior snapshot* into a scam probability.

| Aspect | Details |
|---|---|
| Model | XGBoost (`XGBClassifier`) |
| Learning Type | Supervised binary classification |
| Feature schema | 11 call-behavior features (duration, unknown caller, video, hour, call history, outgoing activity, weekend, derived log/early/late/activity category) |
| Output | Scam probability 0–1 |
| Fusion | `risk_score = 0.5 · ML_probability + 0.5 · safety_rules`, gated so ML can only corroborate rule evidence — it cannot escalate the risk level beyond what the safety rules substantiate |
| Level mapping | ≥75 CRITICAL · ≥50 HIGH · ≥30 MEDIUM · else LOW |

### Where ML does NOT contribute (by design)

- **Text scam scanner** (`/api/detect/panic`) is a **rule-based phrase engine** — no transformer model. 📝 BERT/RoBERTa is future work.
- **`IsolationDetector`** service is a **heuristic weighted score** used by the Android simulator demo.
- The **decision to alert** is a threshold on the fused score, not a black-box classifier output.

### Model performance — honest numbers

The deployed classifier is an **XGBoost** model trained on **15,000 synthetic call snapshots** (≈15% scam rate). The benchmark below (`models/saved/metrics.json`, generated by `notebooks/audit_model.py`) is measured on data drawn from the **same synthetic generator used at training time** — it shows how consistently the model reproduces that generator's structure, **not** how it would perform on real calls.

| Metric | Synthetic benchmark |
|---|---:|
| Accuracy | 99.88% |
| Precision | 99.60% |
| Recall | 99.60% |
| F1 | 99.60% |
| ROC-AUC | 1.00 |

⚠️ **This is NOT real-world validation.** Real-world detection performance against live digital-arrest calls has **not been measured** and would require ethically collected real-world datasets.

### What this model is / is not

**It is:**
- An XGBoost binary risk classifier (`XGBClassifier`).
- Built on an 11-feature call-behavior schema.
- Trained on synthetic call snapshots (15,000 generated calls — no real call telemetry in the training set).
- A prototype/demo component of the behavioral-isolation detection system: the ML corroborates call-behavior evidence only, while telemetry/isolation evidence comes from the rule layer.

**It is not:**
- A validated real-world detector — its benchmark only measures internal consistency with the synthetic generator it was trained on.
- Trained or validated on real-world call telemetry.
- A substitute for the safety-rule layer — the explicit, explainable safety rules are a **separate safety mechanism** that operates independently of the model.

The deployed score currently fuses ML and rules at **50/50** (`risk_score = 0.5 · ML_probability + 0.5 · safety_rules`).

That fusion is **gated by the safety-rule evidence**: if the rule contribution is below the HIGH threshold (50), the fused score is capped below HIGH (49.9); if the rule contribution is below the CRITICAL threshold (75), the fused score is capped below CRITICAL (74.9). ML is therefore **corroborative only** — a high ML probability alone can never manufacture HIGH or CRITICAL risk. A counter-evidence signal also discounts sustained calls from known callers with normal outgoing activity and observed social-app use. When ML is unavailable or degraded, scoring falls back to the safety rules alone.

> Note: The datasets under `data/datasets/` (e.g. Hinglish scam texts, FraudZen CDRs) are **not** used by this model. They were explored only in archived experiments under `archive/ml_pipeline/`.

### Feature importance (synthetic)

1. `outgoing_activity_ratio` — 60.2%
2. `activity_category` — 19.6%
3. `call_duration_log` — 8.4%
4. `call_duration_min` — 6.3%

The dominant feature being *outgoing activity* is exactly the isolation signal the project is built around.

### Explainable AI ✅

Instead of only predicting risk, LUMINA returns the **exact reasons** for every prediction as `top_factors`, derived from the engine's `safety_rule_contributions`:

```text
Risk Level : CRITICAL   Risk Score: 100/100

WHY WAS THIS DETECTED?
• Very long call (165 min) is a sustained isolation signal.
• Unknown caller with no verification history is a common scam tactic.
• Video call is often used to intimidate and monitor the victim.
• No SMS activity during the call.
• No social-app activity — user is not reaching out normally.
```

---

## 🔌 API Overview (real, working endpoints)

| Endpoint | Purpose |
|---|---|
| `GET /health` | Health + model loaded status |
| `POST /api/score` | Score a call snapshot (call fields + `extra_telemetry`) |
| `POST /api/detect-isolation` | Score device isolation telemetry |
| `POST /api/detect/panic` | Rule-based text scam scan |
| `GET /api/incidents` | Historical incidents from SQLite |
| `POST /api/generate-report` | Generate PDF incident report |
| `GET /api/download-report/{filename}` | Download generated PDF |
| `POST /api/send-alert` | Demo family alert (simulated) |
| `POST /api/silent-intervention` | Build silent-intervention alert |
| `GET /api/ngos` · `GET /api/government-tools` · `GET /api/community-alerts` | Support resources |

Interactive docs at `http://localhost:8000/docs`.

---

## 🧪 Testing ✅

```bash
python -m pytest tests/ -v
```

**Result: 130 passed.** Coverage includes the risk engine (escalation, false-positive guards, missing-telemetry safety including explicitly-null telemetry treated as missing), model-artifact loading failure behavior (unavailable/degraded states), phase-2 scenario cases, alert abuse protection (cooldown / rate-limit / duplicate suppression), silent-intervention gating (never triggered below HIGH risk, no fake delivery), panic-phrase detection, and API endpoint integration.

---

## 🚀 Quick Start

```bash
git clone https://github.com/thanushreea1306/lumina.git
cd lumina
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

```bash
python run.py                    # backend on :8000
streamlit run dashboard/app.py   # dashboard on :8501
python -m app.services.android_simulator   # 🟡 telemetry demo
```

| Interface | URL |
|---|---|
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Dashboard | http://localhost:8501 |

---

## 🔒 Privacy & Ethics

### Design principles

- Consent-based monitoring
- Trusted contacts configured via the `LUMINA_TRUSTED_CONTACTS` environment variable
- No continuous call recording
- Minimal metadata collection
- Explainable AI decisions
- Human intervention instead of automated enforcement

### Honest note

This prototype stores incident metadata in a **plain SQLite database** (`data/incidents.db`). No hashing/encryption of stored records and no automatic retention/deletion window are implemented yet — 📝 both are future work before any real deployment. The dashboard previously claimed "SHA-256" and "24h deletion"; those claims have been removed because they are **not implemented**.

---

## 📌 Limitations (honest)

- Model trained on **synthetic** data — real-world detection performance is unmeasured
- The real datasets under `data/datasets/` (Hinglish scam texts, FraudZen CDRs) are **not** used by the deployed model — they appear only in archived experiments (`archive/ml_pipeline/`)
- **Simulated** SMS alerts (real delivery needs `LUMINA_ALERT_MODE=real` + Twilio credentials + `LUMINA_TRUSTED_CONTACTS`)
- No live telecom / call-metadata integration
- No real Android on-device capture (skeleton only)
- Text scanner is **rule-based**, not an NLP model
- Incident store is plain SQLite without retention guarantees
- Community "threat radar" feed in the earlier dashboard used hardcoded demo data

---

## 🔮 Roadmap (labeled)

### Version 2 — 📝
- Real Android on-device sensing (`CallReceiver` + `LuminaService` wiring to the API)
- Twilio real SMS delivery (+ WhatsApp gateway)
- NLP transformer (BERT/RoBERTa) transcript classifier
- Privacy: hashing, retention policy, on-device-only processing

### Version 3 — 📝
- Telecom operator call-metadata integration
- Real-time streaming analysis of an ongoing call
- Federated learning across consented devices

### Version 4 — 📝
- National cyber safety platform
- Anonymous threat-intelligence sharing
- Bank fraud-prevention integration (block high-risk transfers)

---

## 🏆 Why LUMINA Stands Out

| Area | LUMINA |
|---|---|
| Problem | Solves an urgent and growing cybercrime |
| Innovation | Focuses on victim isolation rather than only scam detection |
| Machine Learning | Behavioral risk classification with XGBoost (exactly one, clearly-scoped role) |
| Explainability | Plain-language reasons returned for every prediction |
| Human-Centered | Trusted contacts intervene instead of relying on victims |
| End-to-End | Detection → alert → PDF report → dashboard, all wired to one engine |

---

## 👤 Team

**Thanushree A** — Solo Builder | AI & ML Developer

Built for **ML Empowerment Build Challenge 2.0**.

---

## 📞 Important Resources

- **National Cyber Crime Helpline:** 1930
- **National Cyber Crime Reporting Portal:** https://cybercrime.gov.in
- **Sanchar Saathi:** https://sancharsaathi.gov.in

---

## 📄 License

MIT License — see `LICENSE`.

---

## 💡 LUMINA

### Breaking the isolation.
### Empowering trusted intervention.
### Protecting people before irreversible loss.
