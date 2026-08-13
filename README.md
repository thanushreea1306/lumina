# Lumina

Lumina is a hybrid AI risk engine that detects the **behavioral isolation pattern** associated with "digital-arrest" scams — hours-long calls from unknown callers, video intimidation, and the sudden silence of a phone that has stopped reaching out — and prepares a silent trusted-contact alert while the scam is still in progress.

It works by fusing two independent layers:

1. an **XGBoost classifier** over 11 call-behavior features, and
2. a **deterministic safety-rule layer** over call + telemetry context,

then applying conservative **escalation gates** so the ML model can corroborate evidence but never manufacture a HIGH or CRITICAL risk on its own.

Current scope: this is a research prototype. The model is trained on **synthetic** data, alerts are **simulated by default**, and no live telecom or on-device capture is integrated yet. The system is built to be evaluated honestly and reproduced end-to-end.

---

## Background

Digital-arrest scams impersonate police or government officials. The victim is kept on a long video call, threatened with arrest, and explicitly told not to contact anyone. The decisive feature of the attack is not the content of the deception — it is the **isolation** it imposes:

- prolonged, uncontrolled calls
- unknown callers with no verifiable history
- video calls used for intimidation
- reduced or zero outward communication
- device behavior that locks the user into the interaction

Traditional reporting tools act **after** the victim recognizes the fraud. A victim under active digital arrest is usually unable to seek help at all. Lumina targets an earlier intervention point: recognizing the behavioral pattern while the person is still inside the trap, and reaching a trusted contact on their behalf.

---

## How Lumina Works

```mermaid
flowchart LR
    A[Input telemetry] --> B[Canonical feature extraction]
    B --> C1[11 ML features]
    B --> C2[Telemetry / context]
    C1 --> D[XGBoost classifier]
    C2 --> E[Safety rules]
    D --> F[Gated fusion]
    E --> F
    F --> G[Risk level]
    G --> H[Explanation]
    H --> I[Trusted-contact alert]
    H --> J[SQLite + PDF report]
```

The key architectural decision is the strict **telemetry/ML separation**: telemetry fields never reach the model. They are consumed only by the explicit safety-rule layer, so missing telemetry can never be silently coerced into model input.

---

## Canonical Feature Schema

`app/core/features.py` defines a deterministic, 29-field canonical schema: **11 ML features + 9 telemetry/context fields + 9 missingness indicators**.

### ML features (11)

| # | Feature | Source |
|---|---------|--------|
| 1 | `call_duration_min` | raw |
| 2 | `is_unknown_number` | raw |
| 3 | `is_video_call` | raw |
| 4 | `hour_of_day` | raw |
| 5 | `caller_call_history` | raw |
| 6 | `outgoing_activity_ratio` | raw |
| 7 | `is_weekend` | raw / derived |
| 8 | `call_duration_log` | `log1p(call_duration_min)` |
| 9 | `is_early_morning` | `5 <= hour_of_day <= 8` |
| 10 | `is_late_night` | `hour_of_day >= 22 or hour_of_day <= 4` |
| 11 | `activity_category` | binned `outgoing_activity_ratio` (0.33 / 0.66) |

### Telemetry fields (9, excluded from ML)

`screen_time_on_call_percent`, `num_app_switches`, `num_home_presses`, `has_sms_activity`, `has_social_app_activity`, `location_change`, `screen_brightness`, `screen_on_continuous_hours`, `persistence_hours`.

### Missingness indicators (9)

`is_missing_<field>` for each telemetry field. An absent or explicitly null telemetry value is treated as **missing**, not as an observed `0`/`False` — the safety-rule layer gates every telemetry-dependent signal on its missingness flag, so no behavioral claim is fabricated from missing data.

---

## ML Layer

The deployed classifier is an **XGBoost** `XGBClassifier` (binary, `binary:logistic`) operating on the 11 call-behavior features above. Training is fully scripted in `notebooks/train_simple_model.py`:

- **Data**: 15,000 synthetic call snapshots (scam rate ~15%), generated from class-conditional distributions.
- **Model**: `n_estimators=100`, `max_depth=4`, `learning_rate=0.1`, `subsample=0.8`, `colsample_bytree=0.8`, `random_state=42`.
- **Preprocessing**: `StandardScaler` fitted on the training split.
- **Split**: 80/20 stratified train/test (`random_state=42`).
- **Artifacts**: `models/saved/risk_classifier.pkl`, `scaler.pkl`, `features.pkl`.

Feature importance on the synthetic development data is dominated by `outgoing_activity_ratio` (~60%) and `activity_category` (~20%) — consistent with the isolation thesis: reduced outward communication is the strongest signal the model learns.

> Known small train/serve skew, documented for transparency: the training generator bins `activity_category` with `pd.cut(bins=3)` over the observed data range (`notebooks/train_simple_model.py`), while runtime uses fixed 0.33 / 0.66 thresholds (`app/core/features.py`). It is a minor, deterministic mismatch, not a semantic one.

> The model is deliberately limited to call-behavior evidence. Isolation/telemetry evidence is handled by the rule layer (below), not by ML.

---

## Model Card (Summary)

- **Intended use**: corroborating a behavioral-isolation risk assessment for digital-arrest-style scams during a call, in a research prototype.
- **Out of scope**: general scam/fraud detection, short-call scams (measured recall ~0.5%), content/NLP understanding, autonomous emergency escalation.
- **Data provenance**: 15,000 fully synthetic, class-conditional call snapshots. No real call data was used to train or evaluate the model.
- **Calibration**: raw `predict_proba` output is fused, not calibrated; probabilities should not be read as true frequencies.
- **Known behavior**: near-perfect on the training distribution, degraded under stress shift (AUC 0.824), weak on short calls.
- **Operational guardrails**: telemetry is excluded from the model by construction; missing data never becomes model input; gates keep ML corroborative only.

---

## Safety-Rule Layer

`RiskEngine._safety_rules()` evaluates explicit, explainable signals with fixed weights, including:

- very long calls (>= 60 min, >= 120 min)
- unknown caller / video call
- very low outgoing activity (< 0.2)
- screen locked to the call, no app switching, no home presses
- no SMS / social activity, no location change, high brightness, multi-hour persistence
- a single counter-evidence signal (known caller with active outward communication) that **reduces** the score

Each rule carries a human-readable reason and contributes to a rule score capped at `1.0`. This is the same evidence surfaced to the user as `top_factors` / `safety_rule_contributions`.

---

## Fusion and Escalation Gates

The final score is a weighted blend of ML probability and rule score, expressed on a 0–100 scale:

```
final_score = (0.5 * ML_probability + 0.5 * rule_score) * 100
```

**Risk levels:**

| Score | Level |
|------:|-------|
| >= 75 | CRITICAL |
| >= 50 | HIGH |
| >= 30 | MEDIUM |
| < 30  | LOW |

**Escalation gates** make ML corroborative only:

- If the rule score < 50, the final score is capped at **49.9** — a high ML probability alone cannot reach HIGH.
- If the rule score < 75, the final score is capped at **74.9** — a high ML probability alone cannot reach CRITICAL.

ML contributes in both directions: it can raise or lower the fused score, while the escalation gates prevent ML from independently creating HIGH or CRITICAL risk.

**Fallback:** when the ML artifacts are unavailable or the prediction fails at runtime, scoring falls back to the rule score alone and `ml_probability` is returned as `null`. A fabricated probability (e.g. `0.5`) is never substituted.

**Artifact validation:** on load, `RiskEngine` validates that the model's `n_features_in_` equals the scaler's feature count and the feature list in `features.pkl`, that the feature ordering matches the scaler's training order, and that no telemetry field appears in the model schema. Invalid states set `model_status` to `degraded` and ML is not served.

---

## Intervention

When risk reaches HIGH or CRITICAL, the silent-intervention path constructs a trusted-contact alert (score alone only records `alert_status`).

- **Default (demo) mode**: the alert is built and marked `SIMULATED` / `delivered: false`. No external message is sent.
- **Optional real delivery**: Twilio SMS can be enabled only through explicit configuration — `LUMINA_ALERT_MODE=real` plus valid `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, and `LUMINA_TRUSTED_CONTACTS`.
- **Abuse protection** (`AlertGuard`): per-victim cooldown (default 60 s), rate limit (max 5 alerts / 60 s window), and duplicate-incident suppression. Recipients outside the trusted-contact allowlist are blocked.

There is **no automatic emergency escalation** to police, government, or NGOs. Support endpoints (`/api/ngos`, `/api/government-tools`, `/api/community-alerts`, etc.) return demo data only — static or in-memory — with no live external integration.

---

## Validation

Validation is separated into a controlled development benchmark and an independent stress benchmark. Both are synthetic. Neither is a claim about real-world detection performance.

### Development benchmark

`notebooks/audit_model.py` evaluates the saved model on 15,000 samples drawn from the **same synthetic generator used at training time** (`models/saved/metrics.json`):

| Metric | Result |
|--------|-------:|
| Accuracy | 99.88% |
| Precision (scam) | 99.6% |
| Recall (scam) | 99.6% |
| F1 (scam) | ~99.6% |
| ROC-AUC | 1.00 |

Because the generator uses strongly class-conditional distributions, the classes are almost separable by construction. **These numbers measure internal consistency of the training/inference pipeline — they are not real-world detection accuracy.**

### Independent stress benchmark

`notebooks/stress_eval.py` freezes the **deployed artifacts** (model, scaler, features — tracked artifacts, schema-validated and unchanged; no retraining occurred) and evaluates them on a deliberately harder synthetic distribution of 8,000 samples with:

- overlapping class distributions
- contradictory evidence (scam signals combined with strong counter-evidence)
- threshold-boundary cases
- measurement noise
- distribution shift and out-of-distribution regions

Labels are assigned by an explicit scenario policy computed before any model call; the model was **not retrained** for this evaluation. Derived features are computed with the same runtime formulas used at inference. One caveat is stated plainly: the scenario policy operates on the **same feature space the model consumes** (duration, activity ratio, caller history, hour), so the stress labels are rule-derived from the model's own inputs — not independent ground truth. The benchmark measures how well the model approximates the scenario rule under noise and distribution shift; it is a harder consistency check, not real-world validation. Results are written to `models/saved/stress_metrics.json`:

| Metric | Stress result |
|--------|--------------:|
| Accuracy | 74.98% |
| Precision (scam) | 76.88% |
| Recall (scam) | 68.39% |
| F1 (scam) | 72.39% |
| ROC-AUC | 0.824 |
| Brier score | 0.2232 |

Measured failure modes (from `stress_metrics.json`):

| Slice | n | Metric | Value |
|--------|----:|--------|------:|
| Short calls (0–30 min) | 3,697 | scam recall | 0.53% |
| Threshold-boundary cases | 1,600 | accuracy | 64.6% |
| Threshold-boundary cases | 1,600 | ROC-AUC | 0.705 |
| General stress subset | 5,200 | ROC-AUC | 0.851 |

This is **still synthetic evaluation and does not constitute real-world validation**. The stress test deliberately exposes failure modes — notably the 0.53% scam recall on short calls (the model largely misses brief scams) versus 94.0% recall on 120–481 min calls — and these are reported rather than hidden.

---

## Reproducibility

All evaluation and artifact generation is scripted. Commands run from the repository root:

| Task | Command | Output |
|------|---------|--------|
| Train model | `python notebooks/train_simple_model.py` | `models/saved/*.pkl`, `data/processed/feature_importance.png` |
| Development benchmark | `python notebooks/audit_model.py` | `models/saved/metrics.json` |
| Stress benchmark | `python notebooks/stress_eval.py` | `models/saved/stress_metrics.json` |
| Evidence charts | `python notebooks/generate_ml_visuals.py` | `data/processed/*.png` |
| Run test suite | `python -m pytest tests/ -v` | test report |

The benchmarks use fixed seeds, so the numbers in `metrics.json` and `stress_metrics.json` reproduce deterministically.

---

## Testing

**140 tests pass** (`python -m pytest tests/ -v`). Coverage includes:

- fused risk engine: escalation gating, false-positive guards, missing-telemetry safety
- model-artifact loading and degradation behavior
- API integration and risk-response field contracts
- telemetry-to-ML boundary and isolation-detection payload validation
- alert abuse protection (cooldown, rate limits, duplicate suppression)
- silent-intervention gating
- report generation and report-download path-traversal protection
- dashboard rendering

---

## Dashboard

The Streamlit dashboard (`dashboard/app.py`) calls the live API and renders whatever the engine returns — there is no separate hardcoded scoring path. It provides:

- current risk banner (level + score)
- explainable evidence (`top_factors`, rule contributions)
- scenario runner: scripted **digital-arrest** and **normal-call** simulations driven through the real engine
- behavior timeline and risk-evolution chart
- intervention status (simulated delivery)
- incident history and PDF report generation / download
- a MODEL EVIDENCE panel with the synthetic benchmark summary and the generated charts (feature importance, confusion matrix, ROC)

The scripted demo scenarios use fixed dashboard payloads; the Python device simulator (`python -m app.services.android_simulator`) powers the dashboard's random-snapshot mode. The simulator's `IsolationDetector` heuristic (its own thresholds) is demo-only and separate from the deployed engine — the dashboard score comes exclusively from `/api/score`.

---

## Privacy and Security

**Implemented:**

- telemetry/ML separation (telemetry is excluded from model input by construction)
- report-download path-traversal protection (filename sanitization and path containment)
- alert cooldown, rate limiting, and duplicate suppression
- missing-data handling that never fabricates behavioral signals from absent telemetry
- controlled intervention behavior (simulated by default, no automatic escalation)

**Not implemented (explicit future work):**

- production authentication and authorization
- encrypted database storage (incident records are stored in plain SQLite at `data/incidents.db`)
- automatic retention or deletion of stored records
- live telecom integration
- production on-device (Android) telemetry collection — the Kotlin app under `android_app/` is a skeleton

---

## Limitations

- The model is trained on **synthetic** data; real-world detection performance has **not** been measured.
- SMS alerts are **simulated by default**; real delivery requires explicit configuration and credentials.
- No live telecom / call-metadata integration; Android on-device capture is a skeleton.
- The text-scam scanner (`/api/detect/panic`) is rule-based, not an ML/NLP model.
- Incident storage is plain SQLite without encryption or retention guarantees.
- There is no production authentication and no automated external escalation.

---

## Installation and Usage

Requirements: Python 3.10+ (developed on 3.14). Dependencies are listed in `requirements.txt` (FastAPI, uvicorn, pydantic, scikit-learn, XGBoost, pandas, numpy, Streamlit, ReportLab, Twilio, etc.).

```bash
git clone https://github.com/thanushreea1306/lumina.git
cd lumina
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

**Start the backend:**

```bash
python run.py                    # FastAPI on :8000
```

**Start the dashboard:**

```bash
streamlit run dashboard/app.py   # Streamlit on :8501
```

**Optional telemetry simulator (demo data source):**

```bash
python -m app.services.android_simulator
```

| Interface | URL |
|-----------|-----|
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Dashboard | http://localhost:8501 |

The dashboard and API are wired for local development (CORS allows the Streamlit origin). The API is also reachable directly via `curl` / the interactive docs.

---

## Repository Structure

```
lumina/
├── app/
│   ├── api/                 # FastAPI route modules (detection/panic; scoring lives in main.py)
│   ├── core/                # features.py, risk_engine.py, db.py
│   └── services/            # alerts, reports, simulator, support integrations
├── android_app/             # Kotlin skeleton (future on-device capture)
├── dashboard/               # Streamlit app + assets
├── config/                  # config package
├── data/
│   ├── processed/           # generated evidence charts
│   └── incidents.db         # SQLite incident log
├── reports/                 # generated PDF incident reports
├── models/saved/            # model artifacts + benchmark results
│   ├── risk_classifier.pkl
│   ├── scaler.pkl
│   ├── features.pkl
│   ├── metrics.json         # development benchmark
│   └── stress_metrics.json  # stress benchmark
├── notebooks/
│   ├── train_simple_model.py
│   ├── audit_model.py
│   ├── generate_ml_visuals.py
│   └── stress_eval.py
├── tests/                   # 140 tests
├── archive/ml_pipeline/     # historical, non-active training experiments
├── run.py                   # backend entrypoint
├── requirements.txt
└── LICENSE                  # MIT
```

---

## Design Principles

1. **The model corroborates and can moderate rule evidence; escalation gates prevent ML from forcing HIGH/CRITICAL on its own.**
2. **Missing data is missing.** Null telemetry is never coerced into a behavioral signal, and ML never sees telemetry at all.
3. **Every decision is explainable.** Each risk assessment exposes the contributing signals and their reasons.
4. **Intervention is conservative.** Alerts are simulated by default, abuse-guarded, and aimed at trusted contacts — never at automated escalation.
5. **Honest evaluation.** Synthetic benchmarks are labeled as synthetic, and the harder stress result is reported alongside the development benchmark.

---

## Roadmap

- **V2 — Real-world sensing**: consent-driven on-device Android telemetry wired to the API.
- **V3 — Stronger intelligence**: ethically sourced datasets, probability calibration, session/subject-level validation, NLP-based coercion analysis, robustness to distribution shift.
- **V4 — Intervention network**: trusted-contact workflows, real-time telecom integrations, coordinated support pathways.

---

## Built By

**Thanushree A**

---

## License

MIT — see `LICENSE`.
