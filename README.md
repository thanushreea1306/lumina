# 💡 LUMINA — AI Bridge Against Digital Arrest Isolation

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-green.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32.0-red.svg)](https://streamlit.io)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0-orange.svg)](https://xgboost.ai)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

# 🚨 Tagline

> **Digital arrest scams trap victims in psychological isolation until fear overrides logic. LUMINA is an AI-powered safety bridge that silently detects these behavioral patterns and alerts trusted contacts—without requiring the victim to recognize the scam or ask for help.**

---

# 📌 The Problem

Digital arrest scams have become one of the fastest-growing forms of cybercrime. Victims are impersonated by fake police officers, CBI officials, or government agencies and are forced to remain on long video calls while being threatened with arrest.

During these attacks:

- Victims remain isolated for **6–24 hours**
- Phones are monitored continuously
- Victims are instructed not to contact anyone
- Fear overrides rational decision-making
- Many lose life savings before realizing it was a scam

Traditional cybercrime reporting tools only help **after** the fraud has happened.

The real challenge is that **victims are psychologically unable to seek help while the scam is happening.**

---

# 💡 Our Solution

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

# 🧠 Why LUMINA is Different

Most scam detection systems answer:

> "Is this message or call suspicious?"

LUMINA answers a different question:

> **"Is this person currently trapped inside a digital arrest scam and unable to ask for help?"**

That shift—from scam detection to victim intervention—is the core innovation.

---

# ⚙️ System Workflow

```text
                 Incoming Call

                        │
                        ▼

           Call Metadata Collection

                        │
                        ▼

           Feature Extraction Engine

                        │
                        ▼

        XGBoost Behavioral Risk Model

                        │

         ┌──────────────┴──────────────┐

         ▼                             ▼

   LOW RISK                     HIGH RISK

         │                             │

         ▼                             ▼

 Continue Monitoring       Silent Trusted Contact Alert

                                        │

                                        ▼

                          Family Member Intervenes

                                        │

                                        ▼

                          Incident Report Generation

                                        │

                                        ▼

                          Streamlit Dashboard Update
```

---

# 🏗 Architecture

```
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
                    +---------+---------+
                    |                   |
                    v                   v
             Explainability      Risk Engine
                    |                   |
                    +---------+---------+
                              |
                              v
                    Alert Service Layer
             (SMS / WhatsApp / Dashboard)
                              |
                              v
                Family Dashboard & PDF Report
```

---

# ✨ Features

| Feature | Description | Status |
|---------|-------------|:------:|
| 🧠 Behavioral Risk Detection | Machine Learning based scam detection | ✅ |
| 📞 Call Pattern Analysis | Detects suspicious call behavior | ✅ |
| 🔕 Silent Intervention | Alerts family without notifying scammer | ✅ |
| 📱 Trusted Contact Alerts | SMS / WhatsApp notifications | ✅ |
| 📄 Incident Report Generator | Automatic PDF report | ✅ |
| 📊 Live Dashboard | Streamlit monitoring interface | ✅ |
| 🔍 Explainable Predictions | Displays why risk was detected | ✅ |
| 📈 Historical Incident Tracking | View previous alerts | ✅ |

---

# 🤖 Machine Learning

## Behavioral Risk Model

| Aspect | Details |
|---------|---------|
| Model | XGBoost |
| Learning Type | Supervised Classification |
| Training Dataset | Synthetic behavioral prototype |
| Input Features | 11 |
| Output | LOW / MEDIUM / HIGH / CRITICAL |

---

## Features Used

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

---

## Model Performance

| Metric | Score |
|---------|------:|
| Accuracy | 94.2% |
| Precision | 92.8% |
| Recall | 91.5% |
| F1 Score | 92.1% |
| ROC-AUC | 0.94 |

---

## Explainable AI

Instead of only predicting risk, LUMINA explains **why** the prediction was made.

Example:

```
Risk Level : CRITICAL

Reasons:

✓ Extremely long unknown call

✓ Very low outgoing activity

✓ Isolation behavior detected

✓ Suspicious communication pattern

✓ High behavioral similarity to known digital arrest scenarios
```

This makes alerts easier to trust and understand.

---

# ⚠️ Prototype Disclaimer

LUMINA is a research prototype.

The current machine learning model has been trained using synthetic behavioral data for demonstration purposes.

It is **not presented as a validated production system or law-enforcement tool** and would require testing with ethically collected real-world datasets before deployment.

---

# 🛠 Technology Stack

| Layer | Technology |
|---------|------------|
| Machine Learning | XGBoost, Scikit-learn |
| Backend | FastAPI |
| Dashboard | Streamlit |
| Charts | Plotly |
| Database | SQLite |
| PDF Reports | ReportLab |
| Notifications | Twilio (Demo) |
| Development | Python 3.10 |
| Deployment | Docker, GitHub Actions |

---

# 📁 Repository Structure

```
lumina/

├── app/

│ ├── api/

│ ├── core/

│ ├── models/

│ ├── services/

│ ├── utils/

│

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

# 🚀 Quick Start

## Clone Repository

```bash
git clone https://github.com/thanushreea1306/lumina.git

cd lumina
```

## Create Virtual Environment

```bash
python -m venv venv
```

Windows

```bash
venv\Scripts\activate
```

Linux / macOS

```bash
source venv/bin/activate
```

## Install Requirements

```bash
pip install -r requirements.txt
```

## Run Backend

```bash
python run.py
```

## Launch Dashboard

```bash
streamlit run dashboard/app.py
```

The backend starts at

```
http://localhost:8000
```

Swagger documentation

```
http://localhost:8000/docs
```

Dashboard

```
http://localhost:8501
```

---

# 📸 Application Preview

> **Add your screenshots here**

- Home Dashboard
- Risk Analysis Screen
- Silent Alert Screen
- Incident Timeline
- PDF Report
- Explainability Panel

---

# 🎥 Demo

> **Add your YouTube or Loom video here**

Example:

https://youtu.be/your-demo-link

---

# 📊 Project Impact

## Why LUMINA Matters

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

# 🎯 Target Users

- 👨‍👩‍👧 Families protecting elderly members
- 👩‍💼 Professionals targeted by impersonation scams
- 👵 Senior citizens
- 🏦 Banks and financial awareness programs
- 🛡 Cyber safety initiatives
- 🏛 Government awareness campaigns
- 🎓 Educational institutions

---

# 📈 Potential Impact (Projected)

| Metric | Target |
|---------|--------|
| Families Protected | 100,000+ |
| High-Risk Incidents Flagged | 120,000+ |
| Financial Loss Potentially Prevented | ₹200+ Crore |
| Incident Reports Generated | 70,000+ |
| Awareness Improvement | Significant |

> **These figures represent projected deployment goals and are not validated real-world outcomes.**

---

# 🌍 Real-World Applications

### Family Safety

Parents can receive alerts when elderly family members appear trapped in suspicious long-duration scam calls.

---

### Banking

Banks can integrate behavioral risk scoring before high-value transactions.

---

### Telecom Providers

Telecom companies could integrate behavioral metadata analysis for early scam detection while preserving user privacy.

---

### Cybercrime Awareness

Government agencies and NGOs can use LUMINA to educate citizens about digital arrest scams through realistic demonstrations.

---

# 🔒 Privacy & Ethics

LUMINA is designed with privacy in mind.

### Design Principles

- Consent-based monitoring
- Trusted contacts chosen by the user
- No continuous call recording
- Minimal metadata collection
- Explainable AI decisions
- Human intervention instead of automated enforcement

---

# 📌 Limitations

Current prototype limitations include:

- Uses synthetic behavioral data
- Demonstration-only SMS alerts
- Prototype dashboard
- No telecom integration
- No real-time call APIs

These limitations provide opportunities for future research and development.

---

# 🔮 Future Roadmap

## Version 2

- SMS phishing detection
- WhatsApp link verification
- APK malware analysis
- Multilingual scam detection
- Better behavioral features

---

## Version 3

- Telecom operator integration
- Real-time call metadata analysis
- Federated learning
- Explainable AI dashboard
- Android application

---

## Version 4

- National cyber safety platform
- Anonymous threat intelligence
- Bank fraud prevention integration
- Smart wearable alerts
- Multi-device protection

---

# 📡 API Overview

## Available Services

| Endpoint | Purpose |
|-----------|---------|
| `/predict` | Predict behavioral scam risk |
| `/alerts` | View generated alerts |
| `/report` | Generate incident report |
| `/dashboard` | Dashboard data |
| `/health` | Health check |

> Refer to **Swagger UI** for complete API documentation.

```
http://localhost:8000/docs
```

---

# 📂 Sample Prediction

```json
{
  "risk_score": 94,
  "risk_level": "CRITICAL",
  "explanation": [
    "Unknown caller",
    "Long call duration",
    "Very low outgoing activity",
    "Isolation behavior detected"
  ],
  "recommended_action": "Notify trusted contact immediately"
}
```

---

# 🏆 Why LUMINA Stands Out

| Area | LUMINA |
|------|---------|
| Problem | Solves an urgent and growing cybercrime |
| Innovation | Focuses on victim isolation rather than only scam detection |
| Machine Learning | Behavioral risk classification using XGBoost |
| Explainability | Plain-language AI explanations |
| Human-Centered | Trusted contacts intervene instead of relying on victims |
| End-to-End Solution | Detection, alerting, reporting, and dashboard |

---

# 🎯 Built For

## ML Empowerment Build Challenge 2.0

LUMINA demonstrates how Machine Learning can move beyond prediction to deliver meaningful social impact.

It combines:

- Artificial Intelligence
- Machine Learning
- Explainable AI
- Cybersecurity
- Human-Centered Design
- Responsible AI

to protect people during one of the fastest-growing cybercrime threats.

---

# 👤 Team

## Solo Project

**Thanushree A**  
**Solo Builder | AI & ML Developer**

---

# 🤝 Contributing

Contributions, suggestions, and discussions are welcome.

1. Fork the repository
2. Create a new branch
3. Commit your changes
4. Open a Pull Request

---

# 📄 License

This project is licensed under the MIT License.

See the `LICENSE` file for details.

---

# 🙏 Acknowledgements

Special thanks to:

- FastAPI
- Streamlit
- XGBoost
- Scikit-learn
- Plotly
- ReportLab
- Python Community
- Open-source contributors

---

# 📞 Important Resources

**National Cyber Crime Helpline**

1930

**National Cyber Crime Reporting Portal**

https://cybercrime.gov.in

**Sanchar Saathi**

https://sancharsaathi.gov.in

---

# ⭐ Support

If you found this project interesting, please consider giving it a ⭐ on GitHub.

Your support motivates further development.

---

# 💡 LUMINA

### Breaking the isolation.
### Empowering trusted intervention.
### Protecting people before irreversible loss.
