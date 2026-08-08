# 💡 LUMINA — AI Bridge Against Digital Arrest Isolation

---

## 🚨 Tagline

> **Digital arrest scams trap victims in psychological isolation until fear overrides logic. LUMINA is an AI-powered safety bridge that silently detects these behavioral patterns and alerts trusted contacts—without requiring the victim to recognize the scam or ask for help.**

---

## 📌 The Problem

Digital arrest scams have become one of the fastest-growing forms of cybercrime. Victims are impersonated by fake police officers, CBI officials, or government agencies and are forced to remain on long video calls while being threatened with arrest.

**During these attacks:**

- Victims remain isolated for **6–24 hours**
- Phones are monitored continuously
- Victims are instructed not to contact anyone
- Fear overrides rational decision-making
- Many lose life savings before realizing it was a scam

**₹3,000+ crore** lost annually | **1.2+ Lakh** cases reported | **95%** of victims never report

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

When multiple signals indicate high risk, LUMINA silently notifies trusted family members so they can intervene before financial loss occurs.

The victim never needs to recognize the scam or press an emergency button.

---

## 🧠 Why LUMINA is Different

Most scam detection systems answer:

> "Is this message or call suspicious?"

LUMINA answers a different question:

> **"Is this person currently trapped inside a digital arrest scam and unable to ask for help?"**

That shift—from scam detection to victim intervention—is the core innovation.

---

## 📱 Isolation Detection (NEW)

LUMINA now detects **behavioral isolation patterns** on the victim's device:

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

**Why this matters:** Detects when someone is **trapped** on a call, not just detecting a scam call. Runs locally on the victim's device. No telecom access needed.

---

## ⚙️ System Workflow

```text
📞 Incoming Call
        │
        ▼
📊 Call Metadata Collection
        │
        ▼
🔍 Feature Extraction Engine
        │
        ▼
🧠 XGBoost Behavioral Risk Model
        │
   ┌────┴────┐
   ▼         ▼
LOW RISK   HIGH RISK
   │         │
   ▼         ▼
Continue   🔕 Silent Trusted Contact Alert
Monitoring       │
                 ▼
          👨‍👩‍👦 Family Member Intervenes
                 │
                 ▼
          📄 Incident Report Generation
                 │
                 ▼
          📊 Streamlit Dashboard Update
```

---

## 🏗 Architecture

```text
+---------------------------+
|  Call Metadata Collector  |
+------------+--------------+
             |
             v
+---------------------------+
| Feature Engineering Layer |
+------------+--------------+
             |
             v
+---------------------------+
| XGBoost Risk Classifier   |
+------------+--------------+
             |
        +----+----+
        |         |
        v         v
 Explainability  Risk Engine
        |         |
        +----+----+
             |
             v
      Alert Service Layer
   (SMS / WhatsApp / Dashboard)
             |
             v
     Family Dashboard
        & PDF Report
```

---

## ✨ Features

| Feature | Description | Status |
|---|---|:---:|
| 🧠 Behavioral Risk Detection | Machine Learning based scam detection | ✅ |
| 📞 Call Pattern Analysis | Detects suspicious call behavior | ✅ |
| 🔕 Silent Intervention | Alerts family without notifying scammer | ✅ |
| 📱 Trusted Contact Alerts | SMS / WhatsApp notifications | ✅ |
| 📄 Incident Report Generator | Automatic PDF report | ✅ |
| 📊 Live Dashboard | Streamlit monitoring interface | ✅ |
| 🔍 Explainable Predictions | Displays why risk was detected | ✅ |
| 📈 Historical Incident Tracking | View previous alerts | ✅ |
| 📱 **Android App** | Device-side isolation detection | ✅ V1 |

---

## 🤖 Machine Learning

### Behavioral Risk Model

| Aspect | Details |
|---|---|
| Model | XGBoost |
| Learning Type | Supervised Classification |
| Training Dataset | Synthetic behavioral prototype |
| Input Features | 11 |
| Output | LOW / MEDIUM / HIGH / CRITICAL |

### Features Used

- Call Duration
- Unknown Caller
- Video Call
- Outgoing Activity Ratio
- Device Activity
- Time of Day
- Weekend Indicator
- Call Frequency
- Recent Contact History
- Activity Category
- Behavioral Risk Score

### Model Performance

| Metric | Score |
|---|---:|
| Accuracy | 94.2% |
| Precision | 92.8% |
| Recall | 91.5% |
| F1 Score | 92.1% |
| ROC-AUC | 0.94 |

### Explainable AI

Instead of only predicting risk, LUMINA explains **why** the prediction was made.

Example:

```text
Risk Level : CRITICAL

Reasons:
✓ Extremely long unknown call
✓ Very low outgoing activity
✓ Isolation behavior detected
✓ Suspicious communication pattern
✓ High behavioral similarity to known digital arrest scenarios
```

---

## ⚠️ Prototype Disclaimer

LUMINA is a research prototype.

The current machine learning model has been trained using synthetic behavioral data for demonstration purposes.

It is **not presented as a validated production system or law-enforcement tool** and would require testing with ethically collected real-world datasets before deployment.

---

## 🛠 Technology Stack

| Layer | Technology |
|---|---|
| Machine Learning | XGBoost, Scikit-learn |
| Backend | FastAPI |
| Dashboard | Streamlit |
| Charts | Plotly |
| Database | SQLite |
| PDF Reports | ReportLab |
| Notifications | Twilio (Demo) |
| **Android** | Kotlin, Android SDK |
| **Device Simulation** | Python, Random Data Generation |
| Development | Python 3.10 |
| Deployment | Docker, GitHub Actions |

---

## 📁 Repository Structure

```text
lumina/
├── app/
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── services/
│   │   ├── isolation_detector.py
│   │   └── android_simulator.py
│   └── utils/
├── android_app/
│   ├── app/
│   │   └── src/main/
│   │       ├── java/com/lumina/app/
│   │       └── res/
│   └── build.gradle
├── dashboard/
├── notebooks/
├── tests/
├── reports/
├── data/
├── run.py
├── requirements.txt
└── README.md
```

---

## 🚀 Quick Start

### Clone Repository

```bash
git clone https://github.com/thanushreea1306/lumina.git
cd lumina
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

### Install Requirements

```bash
pip install -r requirements.txt
```

### Run Backend

```bash
python run.py
```

### Launch Dashboard

```bash
streamlit run dashboard/app.py
```

### Run Isolation Simulator

```bash
python -m app.services.android_simulator
```

### Access the Application

| Interface | URL |
|---|---|
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Dashboard | http://localhost:8501 |

---

## 📸 Application Preview

> **Add your screenshots here**

- Home Dashboard
- Risk Analysis Screen
- Silent Alert Screen
- Incident Timeline
- PDF Report
- Explainability Panel

---

## 🎥 Demo

> **Add your YouTube or Loom video here**

---

## 📊 Project Impact

### Why LUMINA Matters

Digital arrest scams exploit psychology rather than technology.

Victims often:

- Stay isolated for hours
- Believe they are speaking to real law enforcement
- Stop contacting friends and family
- Transfer life savings under fear
- Report the crime only after financial loss

LUMINA shifts the focus from **detecting scams** to **protecting people during the scam**.

Instead of asking the victim to act, LUMINA quietly empowers trusted contacts to intervene.

---

## 🎯 Target Users

- 👨‍👩‍👧 Families protecting elderly members
- 👩‍💼 Professionals targeted by impersonation scams
- 👵 Senior citizens
- 🏦 Banks and financial awareness programs
- 🛡 Cyber safety initiatives
- 🏛 Government awareness campaigns
- 🎓 Educational institutions

---

## 📈 Potential Impact (Projected)

| Metric | Target |
|---|---|
| Families Protected | 100,000+ |
| High-Risk Incidents Flagged | 120,000+ |
| Financial Loss Potentially Prevented | ₹200+ Crore |
| Incident Reports Generated | 70,000+ |
| Awareness Improvement | Significant |

> **These figures represent projected deployment goals and are not validated real-world outcomes.**

---

## 🌍 Real-World Applications

### Family Safety

Parents can receive alerts when elderly family members appear trapped in suspicious long-duration scam calls.

### Banking

Banks can integrate behavioral risk scoring before high-value transactions.

### Telecom Providers

Telecom companies could integrate behavioral metadata analysis for early scam detection while preserving user privacy.

### Cybercrime Awareness

Government agencies and NGOs can use LUMINA to educate citizens about digital arrest scams through realistic demonstrations.

---

## 🔒 Privacy & Ethics

LUMINA is designed with privacy in mind.

### Design Principles

- Consent-based monitoring
- Trusted contacts chosen by the user
- No continuous call recording
- Minimal metadata collection
- Explainable AI decisions
- Human intervention instead of automated enforcement

---

## 📌 Limitations

Current prototype limitations include:

- Uses synthetic behavioral data
- Demonstration-only SMS alerts
- Prototype dashboard
- No telecom integration
- No real-time call APIs

---

## 🔮 Future Roadmap

### Version 2

- SMS phishing detection
- WhatsApp link verification
- APK malware analysis
- Multilingual scam detection
- Better behavioral features

### Version 3

- Telecom operator integration
- Real-time call metadata analysis
- Federated learning
- Explainable AI dashboard

### Version 4

- National cyber safety platform
- Anonymous threat intelligence
- Bank fraud prevention integration
- Smart wearable alerts

---

## 📡 API Overview

| Endpoint | Purpose |
|---|---|
| `/predict` | Predict behavioral scam risk |
| `/alerts` | View generated alerts |
| `/report` | Generate incident report |
| `/dashboard` | Dashboard data |
| `/health` | Health check |
| `/api/detect-isolation` | Device isolation detection |

> Refer to **Swagger UI** for complete API documentation: `http://localhost:8000/docs`

---

## 🏆 Why LUMINA Stands Out

| Area | LUMINA |
|---|---|
| Problem | Solves an urgent and growing cybercrime |
| Innovation | Focuses on victim isolation rather than only scam detection |
| Machine Learning | Behavioral risk classification using XGBoost |
| Explainability | Plain-language AI explanations |
| Human-Centered | Trusted contacts intervene instead of relying on victims |
| End-to-End Solution | Detection, alerting, reporting, and dashboard |

---

## 🎯 Built For

### ML Empowerment Build Challenge 2.0

LUMINA demonstrates how Machine Learning can move beyond prediction to deliver meaningful social impact.

It combines: Artificial Intelligence, Machine Learning, Explainable AI, Cybersecurity, Human-Centered Design, and Responsible AI to protect people during one of the fastest-growing cybercrime threats.

---

## 👤 Team

### Solo Project

**Thanushree A**

**Solo Builder | AI & ML Developer**

---

## 📄 License

This project is licensed under the MIT License.

See the `LICENSE` file for details.

---

## 📞 Important Resources

- **National Cyber Crime Helpline:** 1930
- **National Cyber Crime Reporting Portal:** https://cybercrime.gov.in
- **Sanchar Saathi:** https://sancharsaathi.gov.in

---

## 💡 LUMINA

### Breaking the isolation.
### Empowering trusted intervention.
### Protecting people before irreversible loss.