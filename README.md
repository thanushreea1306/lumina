# LUMINA

A real-time safety-support system that helps users recognize and resist social-engineering pressure during phone calls — particularly digital-arrest and authority-impersonation scams.

---

## Overview

LUMINA is designed around a specific problem: **a person under active social-engineering pressure may be unable to think clearly, verify claims, or seek help independently.**

The system does not attempt to "detect scams" with certainty. Instead, it:

1. Captures real device signals (call lifecycle) as **honest evidence** — never fabricated.
2. Accepts **user-confirmed observations** (what the person actually experiences).
3. Evaluates evidence through a **deterministic safety engine** — not ML classification.
4. Produces **explainable safety states** with clear recommended actions.
5. Supports the user in **making a safer decision** — not making decisions for them.

LUMINA is a safety-support tool, not an authority. It does not declare guilt, certainty, or scam status. It says: *"Based on what has been reported, here is what to consider."*

---

## Problem

Social-engineering attacks on phone calls share common patterns:

- **Authority impersonation** — the caller claims to be police, a bank, or a government agency.
- **Urgency and threats** — "you must act now or face arrest/consequences."
- **Secrecy** — "do not tell anyone about this call."
- **Financial pressure** — requests for money transfers, OTPs, or gift cards.
- **Credential extraction** — requests for passwords, PINs, or remote access.
- **Isolation** — keeping the victim on a long call, preventing verification.

Simply labeling a call as "scam" is insufficient because:
- The victim may not believe it is a scam while under pressure.
- False positives damage trust.
- The situation is dynamic — risk escalates as pressure intensifies.
- The victim needs actionable guidance, not a binary verdict.

---

## LUMINA's Approach

```
REAL SIGNALS + USER-CONFIRMED OBSERVATIONS
        ↓
    EVIDENCE
        ↓
  DECISION CONTEXT
        ↓
  SAFETY ASSESSMENT
        ↓
EXPLAINABLE INTERVENTION
        ↓
  PROTECTIVE ACTION
        ↓
    OUTCOME
        ↓
FUTURE LEARNING
```

The architecture has a clear separation of concerns:

- **Evidence** is factual: what was observed (by the device) or reported (by the user).
- **Decision Context** aggregates evidence without interpretation.
- **Safety Assessment** applies deterministic rules to produce a safety state.
- **Intervention** provides the user with a clear, honest recommendation.
- **Outcome** records what the user actually did.

The deterministic safety engine is the **authoritative decision layer**. ML models, if present, are subordinate to evidence and safety rules — they can corroborate but never override.

---

## Safety States

| State | Meaning | Recommended Action |
|-------|---------|-------------------|
| **CLEAR** | No concerning indicators reported or observed. | Continue normally. |
| **WATCH** | At least one observation warrants attention. | Stay alert. Verify independently if possible. |
| **PAUSE** | A high-risk action is being requested (e.g., OTP, money transfer). | Do not proceed. Pause and verify. |
| **VERIFY** | Multiple pressure indicators present. | Stop. Verify the caller's identity through an independent channel. |
| **PROTECT** | Coercion pattern detected (authority claim + urgency + financial/credential request). | **STOP AND VERIFY INDEPENDENTLY.** Do not send money, codes, or grant access. |
| **RECOVERY** | The user reports they performed a high-risk action. | Seek help immediately. Contact your bank if financial information was shared. |

These states are deterministic — the same evidence always produces the same state. There is no randomness, no hidden scoring, and no ML-driven state transitions.

---

## Evidence Model

LUMINA uses an explicit evidence model where **missing data is represented as missing**, never converted into `0`, `false`, or empty strings.

### Evidence Sources

| Source | Description |
|--------|-------------|
| `DEVICE` | Genuinely observed by the device (call lifecycle, direction, duration). |
| `USER` | Explicitly reported by the user (observations they select). |
| `SYSTEM` | Derived by the system from existing evidence. |
| `MODEL` | Produced by an ML model (subordinate to safety rules). |
| `RULE` | Produced by the deterministic safety engine. |

### Evidence Statuses

| Status | Meaning |
|--------|---------|
| `OBSERVED` | The signal was actually observed. |
| `USER_CONFIRMED` | The user explicitly confirmed this observation. |
| `UNKNOWN` | The signal could not be determined. |
| `NOT_AVAILABLE` | The platform does not provide this signal. |
| `NOT_PERMITTED` | The user has not granted permission for this signal. |
| `INFERRED` | Derived from other evidence (clearly marked as such). |

Unknown or unavailable evidence is never silently converted into a positive or negative observation.

---

## Android Client

The Android app captures real call lifecycle events and allows users to report observations during a call.

### Implemented Features

- **Real call lifecycle capture** via `TelephonyManager` / `PhoneStateListener`.
- **CallStateMachine** — pure-logic state machine that produces truthful completed-call records.
- **Local event persistence** — events stored on-device before any network call.
- **Offline-first sync queue** — events persist locally; upload happens only when the backend is reachable.
- **Retry with bounded backoff** — transient failures retry with exponential backoff (2s → 60s max).
- **Stale session recovery** — if the backend session expires, a new session is created and pending events are retried.
- **User observations** — 16 observation types (authority claim, urgency, OTP request, etc.) that the user explicitly selects and submits.
- **Decision retrieval** — fetches the safety decision from the backend.
- **User response recording** — records what the user actually did (performed/declined/paused).
- **HMAC-SHA256 authenticated transport** — every request is signed; sessions are bound to devices.
- **Android Keystore-backed secret storage** — device credentials encrypted with AES-256-GCM.

### What the Android Client Does NOT Do

- No microphone recording or audio analysis.
- No SMS monitoring or contact harvesting.
- No location tracking or screen capture.
- No automatic call blocking.
- No ML inference on-device.
- No fabrication of caller identity or scam status.

### Verification Status

| Component | Status |
|-----------|--------|
| Unit tests (71) | Verified |
| Build (assembleDebug) | Verified |
| HMAC interop with backend | Verified |
| Keystore implementation | Verified (static) |
| Physical device runtime | Not yet verified |
| Emulator runtime | Not yet verified |

---

## Backend

The backend is a FastAPI application with SQLite persistence and a deterministic safety engine.

### Architecture

- **FastAPI** — async Python web framework.
- **SQLite** — append-only evidence persistence.
- **Deterministic safety engine** — no randomness, no ML in the decision path.
- **HMAC-SHA256 authentication** — device registration + request signing.
- **Session ownership** — each session is bound to a registered device.

### Implemented Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/devices/register` | Register a new device (returns `device_id` + `device_secret`). |
| `POST` | `/api/sessions` | Create a new session (auth required). |
| `POST` | `/api/sessions/{id}/events` | Append a timeline event (auth required). |
| `POST` | `/api/sessions/{id}/observations` | Add a user-confirmed observation (auth required). |
| `GET` | `/api/sessions/{id}` | Read a session (auth required). |
| `GET` | `/api/sessions/{id}/decision` | Evaluate safety decision (auth required). |
| `POST` | `/api/sessions/{id}/respond` | Record user response (auth required). |
| `POST` | `/api/sessions/{id}/outcome` | Record outcome (auth required). |

All protected endpoints require valid HMAC-SHA256 authentication headers (`X-Device-ID`, `X-Timestamp`, `X-Nonce`, `X-Signature`).

---

## Security

### Implemented

- **HMAC-SHA256 request signing** — every protected request is authenticated.
- **Device registration** — each device receives unique credentials once.
- **Replay prevention** — nonce tracking + timestamp window (±5 minutes).
- **Session ownership** — cross-device access returns HTTP 403.
- **Constant-time signature comparison** — `hmac.compare_digest()`.
- **Generic error messages** — authentication failures do not reveal whether a device exists.
- **HTTPS-only transport** — cleartext HTTP is rejected.
- **Android Keystore** — device secret encrypted with AES-256-GCM, hardware-backed key.
- **No hardcoded secrets** — credentials generated at runtime, never committed.

### Not Yet Implemented

- Credential rotation (currently requires re-registration).
- Rate limiting on the registration endpoint.
- Production TLS certificate pinning.

---

## Privacy

LUMINA is designed with privacy by default:

- **No microphone access** — no audio recording or transcription.
- **No SMS monitoring** — no message content is read.
- **No contact harvesting** — the contact list is never accessed.
- **No location tracking** — GPS is not used.
- **No social media monitoring** — no social graph analysis.
- **No screen capture** — no screenshots or screen recording.
- **No automatic blocking** — the user retains full control.
- **Consent-gated** — data collection requires explicit user consent.
- **Evidence-only** — only facts that were genuinely observed or reported are stored.

Unavailable or unpermitted signals remain unavailable rather than being fabricated.

---

## Project Structure

```
lumina/
├── app/
│   ├── api/                    # FastAPI route modules
│   ├── core/                   # Risk engine, features, transforms, DB
│   ├── evidence/               # Evidence model, safety engine, auth, API
│   │   ├── models.py           # Evidence, Session, TimelineEvent
│   │   ├── safety_state.py     # Deterministic safety state machine
│   │   ├── decision_context.py # Evidence aggregation
│   │   ├── explainability.py   # Human-readable explanations
│   │   ├── pipeline.py         # Safety evaluation pipeline
│   │   ├── actions.py          # Protective action definitions
│   │   ├── auth.py             # HMAC-SHA256 authentication
│   │   ├── db.py               # SQLite persistence
│   │   └── router.py           # FastAPI endpoints
│   └── services/               # Alert, report generation
├── android_app/
│   ├── app/src/main/java/com/lumina/app/
│   │   ├── CallEvent.kt        # Call lifecycle data model
│   │   ├── CallStateMachine.kt # Pure-logic state machine
│   │   ├── CallMonitor.kt      # TelephonyManager integration
│   │   ├── DeviceAuth.kt       # HMAC signing
│   │   ├── SecretStore.kt      # Keystore-backed credential storage
│   │   ├── LuminaTransport.kt  # HTTPS transport with auth
│   │   ├── SyncManager.kt      # Offline-first sync with backoff
│   │   ├── ObservationManager.kt # User observation lifecycle
│   │   └── ...                 # Other components
│   └── app/src/test/           # 71 JVM unit tests
├── frontend/                   # React + TypeScript + Vite
│   ├── src/
│   │   ├── app/                # Page components (Home, Session, Evidence, etc.)
│   │   ├── components/         # Reusable UI primitives (Card, Button, StatusBadge, etc.)
│   │   ├── hooks/              # Custom hooks (useHomeState, useSessionState)
│   │   ├── lib/                # API client, observations, utilities
│   │   ├── types/              # TypeScript domain types
│   │   └── styles/             # Design tokens, CSS modules
│   ├── package.json
│   └── vite.config.ts
├── tests/                      # 339 backend tests
├── dashboard/                  # Streamlit dashboard (legacy)
├── models/saved/               # ML artifacts (subordinate to safety engine)
├── data/                       # Runtime data (not committed)
├── requirements.txt
├── render.yaml                 # Backend deployment config
└── README.md
```

---

## Testing

### Backend

```
350 tests passed
```

Covers: evidence model, safety states, decision context, explainability, API contracts, authentication, idempotency, session lifecycle, device event ingestion, observation flow, E2E integration, HMAC interoperability.

### Android

```
71 tests passed, 0 failed, 0 errors
```

Covers: call state machine, event adapter, sync manager, observation manager, HMAC signing, nonce generation, auth headers, secret storage.

### Frontend (React)

```
265 tests passed
```

Covers: safety states, evidence types, API client, routing, accessibility, component rendering, intervention flows, trusted contact, recovery, privacy, security settings.

### Build

```
Android: BUILD SUCCESSFUL — APK generated
Backend: All tests passing
Frontend: Production build successful
```

---

## Development Setup

### Backend

Requirements: Python 3.10+

```bash
git clone https://github.com/thanushreea1306/lumina.git
cd lumina
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run tests:

```bash
python -m pytest -q         # 350 tests
```

### Frontend

Requirements: Node.js 18+

```bash
cd frontend
npm install
npm run dev                 # Vite dev server on :5173 (proxies to :8000)
```

Run tests:

```bash
npm test                    # 265 tests
npm run build               # Production build to dist/
```

### Android

Requirements: JDK 17, Android SDK (API 34), Gradle 8.6+

```bash
cd android_app
./gradlew assembleDebug     # APK at app/build/outputs/apk/debug/
./gradlew testDebugUnitTest # 71 tests
```

---

## Deployment

### Frontend (Vercel)

The React frontend is deployed on Vercel (free tier):

- Static SPA with client-side routing
- Production API base URL configured via `VITE_API_BASE_URL`
- Vite proxy handles API requests in development

### Backend (Render)

The FastAPI backend is deployed on Render (free tier):

- Python 3.11 runtime
- SQLite persistence (ephemeral on free tier)
- Environment-driven CORS configuration
- Health endpoint at `/health`

### Environment Variables

| Variable | Description | Example |
|----------|-------------|--------|
| `LUMINA_DB_PATH` | SQLite database file path | `/tmp/data/evidence.db` |
| `LUMINA_CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `https://your-frontend.vercel.app` |
| `VITE_API_BASE_URL` | Backend API URL for frontend | `https://your-backend.onrender.com` |

### Local Development

```bash
# Backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend (with API proxy to backend)
cd frontend
npm install
npm run dev
```

---

## Limitations

- **SQLite on free-tier hosting is ephemeral** — Render's free tier has no persistent disk. All data is lost on restart. For production, use a managed database (e.g., Supabase PostgreSQL).
- **No physical-device runtime verification yet** — the Android app has been built and unit-tested, but not yet run on a real device or emulator.
- **No emulator runtime verification yet.**
- **Credential rotation not yet implemented** — if a device secret is compromised, the device must re-register.
- **`PhoneStateListener` is deprecated** (API 31+) — functional on current targets but should migrate to `TelephonyCallback`.
- **No production user accounts** — the HMAC system provides device identity but not user accounts.
- **Single-process backend** — nonce tracking is in-memory; not suitable for multi-worker deployment without shared state.
- **Trusted Contact delivery** — the legacy alert endpoint is in demo mode; no real SMS delivery is configured.

---

## Roadmap

- **Phase 8**: Physical device runtime verification and end-to-end Android → backend testing.
- **Phase 9**: Credential rotation and production authentication design.
- **Phase 10**: Observation UI refinement and decision display polish.

---

## Responsible Claims

LUMINA is a **safety-support tool**, not a scam-detection authority. It:

- Does not claim to identify every scam or social-engineering attempt.
- Does not make legal, financial, or medical recommendations.
- Does not replace law enforcement, financial institutions, or human judgment.
- Provides **information and guidance** based on what has been observed and reported.
- Leaves all final decisions to the user.

The deterministic safety engine produces **advisory states**, not verdicts. A CLEAR state means "no concerning indicators have been reported" — not "this call is safe."

---

## Built By

**Thanushree A**

Solo project.

---

## License

MIT — see `LICENSE`.
