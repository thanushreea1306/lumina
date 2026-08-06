# 💡 LUMINA — AI Bridge Against Digital Arrest Isolation

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-green.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32.0-red.svg)](https://streamlit.io)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0.0-orange.svg)](https://xgboost.ai)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🚨 Tagline

> **Digital arrest scams trap victims alone for hours until fear overrides logic. Lumina is the calm second brain outside the trap — sensing the pattern and quietly bringing help in, without needing the victim to ask.**

---

## 🎯 The Problem

India lost over **₹22,495 crore** to cyber fraud in 2025, with **digital arrest scams** alone accounting for:

* **₹3,000+ crore** lost annually
* **1.2+ Lakh** cases reported in 2025–26
* **Supreme Court of India** took *suo motu* notice in Jan 2026
* Victims are kept isolated on video calls for **6–24 hours**
* **95%** of victims never report the crime

### Why Existing Solutions Fail

* **Google Pixel detection** only works on Pixel phones.
* **Government portals (Chakshu)** are strictly after-the-fact reporting.
* **Honeypot bots** target incoming spam calls, not active ongoing traps.
* **All existing tools require the victim to act** — but victims under psychological arrest never will.

---

## 💡 Our Solution

**Lumina is a consent-based, family-linked monitoring system that uses a machine learning risk classifier to detect the behavioral signature of a digital arrest scam in progress.**

When risk crosses a threshold, Lumina silently alerts pre-registered trusted contacts with a plain-language explanation, so someone outside the psychological trap can intervene — without ever requiring the victim to recognize the scam themselves.

---

## 🔄 How It Works

```text
📞 CALL                        💡 LUMINA DETECTS                  👨‍👩‍👦 FAMILY RESPONDS
 │                                    │                                    │
 ▼                                    ▼                                    ▼
Victim gets trapped            AI analyzes call pattern            Silent alert sent:
in digital arrest              • Long duration                     "Amma on unknown
scam (6-24 hours)              • Unknown number                    video call for 47
Isolated. Terrified.           • Video call                        min. LUMINA Risk:
Unable to call.                • Low outgoing activity             CRITICAL. Call now."
 │                                    │                                    │
 ▼                                    ▼                                    ▼
Victim can't act               LUMINA stays silent                 Family breaks the
because they believe           on victim's phone                   isolation — calls
they're under arrest.          (doesn't alert scammer)             landline, visits home,
                                                                   dials 1930
```

---

## ✨ Key Features

| Feature                       | Description                                 | Impact                            |
| ----------------------------- | ------------------------------------------- | --------------------------------- |
| 🧠 **Risk Classifier**        | ML model trained on call-log data (XGBoost) | Detects suspicious long calls     |
| 🎤 **Stress Signal Model**    | Librosa + RAVDESS dataset                   | Detects distress in voice         |
| 🔇 **Silent Bridge Alerts**   | SMS/WhatsApp notifications                  | Alerts without victim action      |
| 📊 **Explainability Panel**   | Shows why a call was flagged                | Builds trust, avoids false alarms |
| 📄 **Auto FIR Generator**     | ReportLab PDF with call metadata            | Ready for police submission       |
| 📱 **Family Dashboard**       | Streamlit UI                                | Alerts, risk history, FIRs        |
| 🔗 **Government Integration** | Sanchar Saathi, CHAKSHU, 1930               | Ecosystem approach                |

---

## 🧠 ML Model Details

| Metric               | Score                    |
| -------------------- | ------------------------ |
| **Algorithm**        | XGBoost                  |
| **Features**         | 11 call pattern features |
| **Training Data**    | 15,000 synthetic records |
| **Accuracy**         | ~99.9%                   |
| **Precision (Scam)** | ~99.6%                   |
| **Recall (Scam)**    | ~99.8%                   |

### Feature Importance

| Feature                     | Importance |
| --------------------------- | ---------: |
| **Outgoing Activity Ratio** |      60.2% |
| **Activity Category**       |      19.6% |
| **Call Duration Log**       |       8.4% |
| **Call Duration**           |       6.3% |

> **Note:** Model trained on synthetic data replicating real scam patterns. Real dataset available for fine-tuning.

---

## 🏗️ Technology Stack

| Layer               | Technology                            |
| ------------------- | ------------------------------------- |
| **ML Model**        | XGBoost, scikit-learn, Librosa        |
| **Backend**         | FastAPI                               |
| **Frontend**        | Streamlit, Plotly                     |
| **PDF Generation**  | ReportLab                             |
| **Data Processing** | Pandas, NumPy                         |
| **Database**        | SQLite                                |
| **Alerts**          | Twilio, Fast2SMS (simulated for demo) |
| **Deployment**      | Docker, GitHub Actions                |

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/thanushreea1306/lumina.git
cd lumina

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run the Application

**Terminal 1: Start Backend**

```bash
uvicorn main:app --reload
```

**Terminal 2: Start Dashboard**

```bash
streamlit run dashboard.py
```

### Access the Application

| Interface       | URL                          |
| --------------- | ---------------------------- |
| **Backend API** | `http://localhost:8000`      |
| **Swagger UI**  | `http://localhost:8000/docs` |
| **Dashboard**   | `http://localhost:8501`      |

---

## 🎥 Demo Flow

1. Simulate a suspicious long video call.
2. Risk classifier flags it.
3. Silent alert sent to family contact.
4. FIR PDF auto-generated.
5. Dashboard shows risk history.

---

## 📊 Architecture Diagram

```text
Call logs
    │
    ▼
Risk Classifier
    │
    ▼
Alert
    │
    ▼
FIR PDF
    │
    ▼
Dashboard
```

---

## 📸 Screenshots

*Add images here:*

* Dashboard
* Alert SMS
* FIR PDF
* Explainability panel

---

## 🔗 Links

| Resource              | Link                               |
| --------------------- | ---------------------------------- |
| **Dashboard (local)** | `http://localhost:8501`            |
| **Backend API**       | `http://localhost:8000`            |
| **Swagger UI**        | `http://localhost:8000/docs`       |
| **GitHub Repo**       | Lumina                             |
| **Demo Video**        | (YouTube/Vimeo link once recorded) |

---

## 🏆 Why Lumina Wins

### Innovation

First tool targeting the isolation mechanic of digital arrest scams.

### Impact

Breaks scam cycle externally, saves victims mid-scam.

### Feasibility

Buildable in 10 days with existing APIs.

### Judge Appeal

Memorable hook — **"We break the isolation, not just the call."**

---

## 👤 Author

**Thanushree A — Solo Builder & ML Engineer**

---

## 📞 Contact & Helplines

* **National Cyber Crime Helpline:** 1930
* **Emergency Portal:** cybercrime.gov.in

---

# 💡 LUMINA — Breaking the isolation. Saving lives.

⭐ **Star this repo if you found it useful!**
