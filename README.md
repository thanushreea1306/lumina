# LUMINA

**Digital Incident Protection** — helps a person caught in a high-pressure digital attack understand what happened, what may be exposed, what can still be stopped, and what to do next.

LUMINA is an incident-focused safety system. It turns authorized audio and user-reported signals into structured conversation evidence, applies a deterministic safety engine, and guides the user — and, when asked, a trusted human — through intervention and recovery. It does not pretend to know more than it does: uncertainty is reported as uncertainty, and the human keeps control at every step.

---

## Why LUMINA Exists

A scam call doesn't just trick people. It can isolate them, pressure them, and keep them on the phone until they make an irreversible decision.

High-pressure attacks share a pattern: an authority figure, a manufactured emergency, a demand for secrecy, and a push to act immediately. The person under pressure often cannot think clearly, verify claims, or ask for help independently. Labeling the event a "scam" is not enough — the victim needs to understand the incident itself, see what is at risk, and be supported through the next safest move.

LUMINA is built on a simple principle:

> Don't just detect the threat. Understand the incident. Stop the next mistake.

---

## What LUMINA Does

- **Incident understanding** — records an incident as a first-class object with a timeline, evidence, actions, and exposure state, rather than a one-off "scam score."
- **Conversation analysis** — extracts behavioral signals from transcribed conversation: authority claims, urgency, pressure, extraction attempts, and their progression over time.
- **Pressure / escalation detection** — deterministic analysis of how pressure builds across a conversation, marked as inference rather than fact.
- **Evidence grounding** — every claim in the system carries a source and an epistemic status; nothing is assumed to be certain without a basis.
- **Exposure awareness** — tracks what may have been exposed (money, account, authentication, device, identity, personal information) and keeps exposure honest until confirmed.
- **Next safest action** — the safety engine produces a clear recommendation and a calm intervention, never a verdict.
- **Trusted-human assistance** — a manual "I'm Trapped — Get Help" flow that works independently of what LUMINA did or did not classify.
- **Recovery continuity** — when damage has occurred, a structured recovery plan (contain, secure, preserve, report, recover, monitor) with completion that is never fabricated.
- **Privacy and security** — authenticated, owner-scoped data, temporary handling of raw audio, and no hidden recording.

---

## The Core Experience

Calls and conversations are the center of the product. The pipeline looks like this:

```
Authorized Audio  (user-provided file · browser mic · Android opt-in mic)
      ↓
Speech-to-Text   (local faster-whisper)
      ↓
Conversation Evidence      (deterministic extraction)
      ↓
Pressure / Escalation Analysis   (deterministic)
      ↓
Safety Decision            (deterministic safety engine — authoritative)
      ↓
Intervention               (calm, action-focused guidance)
      ↓
Trusted Human              (manual "I'm Trapped" flow — opt-in, independent)
      ↓
Incident Continuity        (persisted incident + timeline)
      ↓
Recovery                   (stages; completion never fabricated)
```

The transcription step is AI-assisted, but every interpretation downstream is **deterministic** and clearly separated from the AI output. AI output is never treated as fact.

---

## Safety Model

LUMINA keeps every piece of information labeled with how much it can be trusted:

| Label | Meaning |
|-------|---------|
| **FACT** | Directly observed or user-confirmed. |
| **INFERENCE** | Derived by the system from evidence (clearly marked as such). |
| **USER REPORT** | Stated by the user (source `USER`, confirmed by them). |
| **UNKNOWN** | Genuinely undetermined — never converted into 0, false, or a safe-looking default. |
| **ACTION** | A recorded user action (e.g., shared OTP, sent money, hung up). |

Unknown or unavailable signals are represented as missing. The platform's answer to "can you see this signal?" may be `NOT_AVAILABLE`, `NOT_PERMITTED`, or `NOT_VERIFIED` — and that answer is preserved.

The **deterministic safety engine is authoritative**. It maps evidence to safety states (`CLEAR`, `WATCH`, `PAUSE`, `VERIFY`, `PROTECT`, `RECOVERY`) through non-random, explainable rules. ML output, when present, can corroborate but can never override the safety engine or force a risk level. LUMINA avoids pretending uncertainty is certainty; a `CLEAR` state means "no concerning indicators observed or reported", not "this call is safe".

---

## Incident Model

An incident is a structured graph of what happened:

```
INCIDENT
├── CONTACT
│   ├── CALL
│   ├── SMS
│   └── MESSAGE
├── ACTION
│   ├── LOGIN
│   ├── OTP
│   ├── PAYMENT
│   └── ACCESS
└── EVIDENCE
    ├── TRANSCRIPT
    ├── MESSAGE
    └── RECEIPT
```

Everything lives on an append-only timeline and is scoped to the owning device. Each item carries an epistemic status and a sequence, so the model can represent "the transcript says the OTP was shared" (inference) as distinct from "the user confirmed the OTP was shared" (fact). Exposure only escalates to `USER_CONFIRMED_EXPOSED` when the user explicitly confirms the action.

---

## Conversation Intelligence

Conversation intelligence is applied to transcript segments (each attributed to a speaker where the transcript provides it):

- **Transcript processing** — ingestion of full transcripts and incrementally assembled segments, with idempotent, append-only writes.
- **Behavioral extraction** — deterministic identification of authority, pressure, urgency, secrecy, and extraction signals from the text.
- **Speaker attribution** — segments are kept attributed to their speaker based on what the transcription returns.
- **Escalation stages** — deterministic detection of pressure building across a conversation window, reported as `INFERENCE`.
- **Temporal reasoning** — how signals appear and intensify over the timeline.
- **Intervention policy** — deterministic, evidence-grounded intervention decisions with no numeric risk score.

The extraction and analysis layers are **deterministic keyword/rule logic — not machine learning**. There is no trained conversation classifier in production inference today, and LUMINA does not describe rule matching as ML.

---

## Speech & Audio

Implemented paths:

- **User-provided audio recordings** — upload a file for transcription (WAV, MP3, FLAC, OGG, M4A, WebM, WMA; maximum 50 MB).
- **Browser microphone capture** — frontend capture via `MediaRecorder`, streamed to `/stream/*` endpoints.
- **Android opt-in microphone recording** — user starts a visible recording; a system microphone indicator is shown. Mic audio is never mixed with call data.
- **Local faster-whisper transcription** — runs locally on the server (default model size `small`, configurable via `WHISPER_MODEL_SIZE`); no cloud STT dependency.
- **Incremental chunk processing** — audio chunks are processed incrementally; chunks are assembled with duplicate detection before extraction.
- **Temporary raw-audio handling** — raw audio is written to a temp file, transcribed, and immediately deleted. No raw audio is persisted in the metadata store.
- **Idempotency** — retry keys are derived deterministically from file metadata so the same file maps to the same backend batch.

### Current Platform Limitations

- **Ordinary cellular call-audio capture is NOT implemented.** Android exposes no public API for a third-party app to capture both sides of a phone call. LUMINA does not use hidden recording or `AccessibilityService` tricks to obtain call audio.
- `PhoneStateListener` (used for call lifecycle awareness) is deprecated on API 31+ and would need migration to `TelephonyCallback`. It provides **call state/direction/duration only — never the remote caller's audio**.
- A `PhoneStateListener`-based listener does not mean the caller's voice is available. Call lifecycle awareness and call-audio capture are different things; LUMINA implements the former.
- Streaming transcription is **batched chunk processing, not true neural streaming**.
- **Diarization (speaker separation) is not implemented.**
- External SMS/phone/email providers depend on configuration; see Limited Delivery below.

---

## Trusted Human Help

The manual emergency path is **"I'M TRAPPED — GET HELP"**:

- It is **independent of automatic conversation detection** — it works even if LUMINA never classified anything.
- It does not require LUMINA to have been correct about the incident.
- It sends only through **configured/authorized delivery paths**, and delivery state is reported honestly.
- Trusted contacts receive **useful context, not secrets** — OTPs, passwords, PINs, card numbers, and authentication secrets are never placed in the contact message.
- Trusted-contact configuration is owner-bound and stored encrypted; one contact per device.

**Delivery today:** the codebase defines SMS and email delivery providers, but the only fully working provider is a console/stub implementation. Real SMS/email delivery requires configuring an external provider; until then, delivery is `NOT_CONFIGURED` rather than simulated.

---

## Recovery & Incident Continuity

When an incident crosses from "can still be stopped" to "damage may have occurred", LUMINA classifies the phase honestly:

- **BEFORE_DAMAGE** — nothing confirmed exposed.
- **AFTER_DAMAGE** — exposure is confirmed by the user.
- **UNKNOWN** — it is not known whether damage occurred.

Recovery then progresses through stages:

```
CONTAIN → SECURE → PRESERVE → REPORT → RECOVER → MONITOR
```

Each stage and its tasks are deterministic. Task completion is **never fabricated** — if LUMINA cannot observe that a step is done (e.g., "change password at the actual site"), it stays `NOT_VERIFIED`. LUMINA does not claim external reporting or account-recovery integrations that do not exist.

---

## Privacy & Security

Implemented protections (verified in code):

- **HMAC-authenticated API paths** — every protected request is signed with device credentials; auth failures are classified distinctly from network failures.
- **Device ownership** — sessions and incidents are bound to the registering device.
- **Incident ownership checks** — cross-device access to an incident is rejected.
- **Nonce/replay protection** — timestamp window plus nonce tracking.
- **Idempotency** — duplicate inserts and retried uploads are no-ops, never duplicated.
- **Account/device lifecycle** — phone-verified account registration, device binding, emergency consent, and account deletion request/confirm/cancel/delete flows.
- **OTP handling** — verification codes are possession-proven and never stored in the clear in a form reusable after confirmation.
- **Temporary raw-audio cleanup** — raw audio lives only in a temp file and is deleted on every path (success, failure, validation error).
- **No raw audio persistence** — audio is never queued or stored in the metadata store.
- **Persistence architecture** — one repository abstraction over SQLite (local) and PostgreSQL (durable), with append-only history and non-destructive migrations.
- **Deletion/retention behavior** — timelines are append-only for forensic history; deletion requests follow an explicit lifecycle and never silently destroy forensic records.
- **Trusted-contact privacy** — secret-free context only; contacts stored encrypted and owner-bound.
- **Android Keystore** — device secrets encrypted with AES-256-GCM, hardware-backed where the platform provides it.

LUMINA does not claim "full compliance with every privacy standard" and does not perform hidden recording, SMS monitoring, contact harvesting, location tracking, or screen capture.

---

## Architecture

```
Android / Web
      │
      ▼
API / Authentication          (HMAC device auth, rate-limited registration)
      │
      ▼
Incident Layer
      ├── Transcript
      ├── Evidence
      ├── User Actions
      └── Timeline
      │
      ▼
Conversation Intelligence     (deterministic extraction; AI transcription only)
      │
      ▼
Deterministic Safety Engine   (authoritative)
      ├── Intervention
      ├── Trusted Human        (opt-in, independent)
      └── Recovery
      │
      ▼
SQLite / PostgreSQL           (swappable via one backend)
```

A legacy scoring/dashboard surface (`/api/score`, Streamlit dashboard, optional XGBoost artifacts) remains mounted but is subordinate: the deterministic safety engine is the decision authority.

---

## Technology

- **Android / Kotlin** — call lifecycle awareness, opt-in microphone recording, HMAC transport, Keystore-backed secrets.
- **Python / FastAPI** — backend API.
- **SQLite & PostgreSQL** — interchangeable persistence backends.
- **faster-whisper** — local speech-to-text.
- **React / TypeScript / Vite / Vitest** — frontend with custom CSS (no UI framework dependency).
- **HMAC-SHA256 authentication** — device and API request signing.
- **scikit-learn / XGBoost** — optional legacy model artifacts (synthetic-data only, see Limitations).

---

## Repository Structure

```
lumina/
├── android_app/            # Android client (Kotlin, Gradle)
│   └── app/src/            #   main/ + test/ (JVM unit tests)
├── app/                    # FastAPI backend
│   ├── api/                #   panic detection endpoint
│   ├── core/               #   legacy risk/features pipeline
│   ├── evidence/           #   evidence model, deterministic safety engine,
│   │                       #   HMAC auth, session endpoints
│   ├── incident/           #   incidents, conversation intelligence, transcript,
│   │                       #   streaming, trusted contact, help, account, recovery
│   ├── persistence/        #   SQLite / PostgreSQL backends + migration
│   └── services/           #   alert, panic trigger, report generator
├── dashboard/              # Streamlit dashboard (legacy)
├── frontend/               # React + TypeScript + Vite web app
│   ├── src/app/            #   page components
│   ├── src/components/     #   UI primitives
│   ├── src/hooks/          #   state hooks (home, session, incident, streaming)
│   ├── src/lib/api/        #   API clients (sessions, incidents, account, help, …)
│   ├── src/types/          #   domain types
│   └── src/test/           #   Vitest tests
├── models/saved/           # Optional ML artifacts (synthetic-data only)
├── notebooks/              # Model training experiments
├── scripts/                # Small utility scripts
├── tests/                  # Backend pytest suite
├── config/                 # Package marker
├── data/                   # Runtime database files (not for committing)
├── .env.example            # Environment variable contract
├── pytest.ini              # Pytest configuration
├── render.yaml             # Render (backend) deployment config
├── requirements.txt
├── LICENSE                 # MIT
└── README.md
```

---

## Running LUMINA Locally

### Prerequisites

- Python 3.10+ (backend), Node.js 18+ (frontend), JDK 17 + Android SDK (API 34) (Android).

### Backend

```bash
git clone <repo-url> lumina
cd lumina

python -m venv venv
venv\Scripts\activate            # Windows (or: source venv/bin/activate)
pip install -r requirements.txt

# Uses SQLite by default (data/evidence.db). Copy .env.example to .env for overrides.
python run.py                    # or: uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                      # Vite dev server on :5173, proxies /api to :8000
npm run build                    # production build (tsc -b && vite build)
```

### Android

```bash
cd android_app
# create local.properties with: sdk.dir=C:\\android-sdk
.\gradlew.bat :app:assembleDebug        # APK at app/build/outputs/apk/debug/
.\gradlew.bat :app:testDebugUnitTest    # JVM unit tests
```

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LUMINA_DB_BACKEND` | `sqlite` or `postgres` | `sqlite` |
| `LUMINA_DB_PATH` | SQLite file location (SQLite backend only) | `data/evidence.db` |
| `DATABASE_URL` | PostgreSQL/Supabase connection string (Postgres backend only) | none |
| `LUMINA_CORS_ORIGINS` | Allowed CORS origins (comma-separated) | localhost origins |
| `WHISPER_MODEL_SIZE` | Local STT model size | `small` |
| `VITE_API_BASE_URL` | Backend origin for the frontend (no `/api` prefix) | `''` (dev proxy) |
| `LUMINA_API_BASE` | API base for the legacy Streamlit dashboard | `http://localhost:8000` |
| `OPENAI_API_KEY` / `OPENAI_API_BASE` | Optional semantic-provider credentials | none |

See `.env.example` and `frontend/.env.production.example` for the full contract.

---

## Testing

Automated test state (current, verified):

| Surface | Result |
|---------|--------|
| Backend (`pytest -q`) | **1274 passed, 14 skipped** |
| Frontend (`vitest run`) | **359 passed across 16 test files** |
| Android JVM unit tests | **117 passed, 0 failed, 0 skipped** (10 suites) |
| Android build (`assembleDebug`) | **PASS** |

These are automated test-coverage results, **not real-world model performance**. LUMINA makes no claim of field accuracy, precision, or benchmark scores against real conversations.

---

## Deployment

Deployment configuration exists for:

- **Backend — Render** (`render.yaml`): Python 3.11 free-tier web service, `LUMINA_DB_BACKEND=postgres`, `DATABASE_URL` supplied as a deployment secret, health check at `/health`, auto-deploy disabled.
- **Frontend — Vercel** (`frontend/vercel.json`): static SPA with client-side routing and immutable asset caching; production API origin set via `VITE_API_BASE_URL` in `frontend/.env.production`.

Caveats that are documented in config rather than hidden: Render free tier has no persistent disk (PostgreSQL is the durable path), and Supabase free-tier projects can auto-pause after a period of inactivity, leaving data intact but the backend offline until resumed. Live PostgreSQL/Supabase behavior has not been exercised end-to-end from CI.

---

## Limitations

Explicit engineering boundaries, not hidden gaps:

- **Cellular call audio** is not captured (no public Android API for it; no hidden-recording workaround).
- **Conversation ML model** — no trained model in production inference; analysis is deterministic. ML artifacts present in `models/saved/` are trained on **synthetic data only** and are explicitly disclaimed as not real-world validated; they serve only as corroboration and cannot force a safety state.
- **Delivery providers** — SMS/email delivery exists as an abstraction; the working provider is console/stub only. Trusted-contact and help flows send nothing real until an external provider is configured.
- **Streaming STT** is batched chunk processing, not neural streaming; diarization is not implemented.
- **PhoneStateListener** is deprecated on API 31+ (functional; migration to `TelephonyCallback` pending).
- **Persistence/deployment** — SQLite is the local-dev backend; durable production uses PostgreSQL; free-tier Supabase pause and Render ephemeral filesystem are documented in `render.yaml`.
- **External integrations** — NGO/government/community endpoints return `NOT_CONFIGURED`; there are no active third-party integrations.

---

## Roadmap

Realistic, platform-honest directions:

- Legitimate, platform-supported call-audio integration where Android permits it.
- Stronger real-world ML validation using legitimate datasets — only then would ML enter the inference path.
- Improved streaming and long-context transcript handling.
- Richer recovery integrations that are genuinely verifiable.
- Additional trusted-contact delivery providers.
- Broader platform support and `TelephonyCallback` migration.

---

## Engineering Principles

- Evidence before inference.
- Safety engine before AI autonomy.
- Unknown is better than false certainty.
- Human control is preserved.
- Privacy by design.
- No fabricated telemetry.
- No fabricated ML.
- No hidden recording.
- No silent actions.
- No secrets in trusted-contact context.

---

## License

MIT — see [LICENSE](LICENSE).