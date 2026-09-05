# app/persistence/sqlite.py
"""SQLite persistence backend (the local development / default backend).

This is the behavioral equivalent of the historical SQLite stores (evidence +
incident) that shared a single database file. It is one unified backend
covering all tables so there is exactly one canonical database regardless of
backend.

Defaults to ``LUMINA_DB_PATH`` (default ``data/evidence.db``). Connections use
production-safe pragmas (timeout, busy_timeout, foreign_keys=ON, WAL where a
real file exists).

Migrations are versioned, idempotent and non-destructive (see
``app.evidence.schema``).
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from app.evidence.models import Evidence, EvidenceSource, EvidenceStatus, Session, TimelineEvent, TimelineEventType
from app.evidence.schema import run_migrations
from app.incident.models import (
    ExposureCategory,
    ExposureLevel,
    ExposureState,
    Incident,
    IncidentStatus,
    Priority,
    RecommendedAction,
    TimelineEntry,
    TimelineEntryType,
    EpistemicStatus,
    UserAction,
    UserActionType,
)
from app.incident.transcript import ExtractionResult, Transcript
from app.persistence.base import PersistenceBackend, TransactionCtx

DB_PATH = os.getenv("LUMINA_DB_PATH", os.path.join("data", "evidence.db"))


def _default_db_path() -> str:
    """Resolve the default database path lazily so test redirection via the
    ``LUMINA_DB_PATH`` environment variable takes effect per call."""
    return os.getenv("LUMINA_DB_PATH", DB_PATH)

logger = logging.getLogger(__name__)

_EVIDENCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    device_secret_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS device_sessions (
    device_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (device_id, session_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload_json TEXT,
    UNIQUE (session_id, sequence)
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    value_json TEXT,
    timestamp TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    confidence REAL,
    metadata_json TEXT,
    UNIQUE (evidence_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    state TEXT NOT NULL,
    reason_codes_json TEXT,
    recommended_action TEXT,
    decision_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_TRANSCRIPT_SCHEMA = """
CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    source TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    segments_json TEXT,
    provenance_json TEXT,
    batch_id TEXT
);

CREATE TABLE IF NOT EXISTS transcript_extractions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    observation_type TEXT,
    action_type TEXT,
    text_span TEXT NOT NULL,
    span_start INTEGER NOT NULL,
    span_end INTEGER NOT NULL,
    extraction_method TEXT NOT NULL,
    epistemic_note TEXT,
    confidence REAL,
    UNIQUE (transcript_id, observation_type, action_type)
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id TEXT NOT NULL UNIQUE,
    transcript_id TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    text TEXT NOT NULL,
    start_time REAL,
    end_time REAL,
    speaker TEXT,
    source_provider TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);
"""

_INCIDENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    owner_device_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    priority TEXT NOT NULL DEFAULT 'NONE',
    next_action_json TEXT,
    unknowns_json TEXT,
    session_ids_json TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS incident_timeline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    summary TEXT NOT NULL,
    epistemic_status TEXT NOT NULL,
    metadata_json TEXT,
    UNIQUE (incident_id, sequence)
);

CREATE TABLE IF NOT EXISTS incident_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    description TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    UNIQUE (incident_id, action_id)
);

CREATE TABLE IF NOT EXISTS incident_exposure (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    category TEXT NOT NULL,
    level TEXT NOT NULL,
    evidence_basis TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (incident_id, category)
);

CREATE TABLE IF NOT EXISTS trusted_contacts (
    contact_id TEXT PRIMARY KEY,
    owner_device_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    delivery_channel TEXT NOT NULL DEFAULT 'NONE',
    destination TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    automatic_help_enabled INTEGER NOT NULL DEFAULT 0,
    configured_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (owner_device_id)
);

CREATE TABLE IF NOT EXISTS help_requests (
    request_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    owner_device_id TEXT NOT NULL,
    contact_id TEXT,
    status TEXT NOT NULL DEFAULT 'REQUESTED',
    delivery_channel TEXT NOT NULL DEFAULT 'NONE',
    reason TEXT,
    provider_request_id TEXT,
    delivered_at TEXT,
    failed_at TEXT,
    failure_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (incident_id)
);

CREATE TABLE IF NOT EXISTS help_policies (
    owner_device_id TEXT PRIMARY KEY,
    automatic_detection_enabled INTEGER NOT NULL DEFAULT 0,
    automatic_help_request_enabled INTEGER NOT NULL DEFAULT 0,
    auto_help_threshold TEXT NOT NULL DEFAULT 'EXTRACTION',
    updated_at TEXT NOT NULL
);
"""

_IDENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS lumina_users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    phone_number TEXT NOT NULL DEFAULT '',
    phone_verified INTEGER NOT NULL DEFAULT 0,
    emergency_consent TEXT NOT NULL DEFAULT 'NOT_GIVEN',
    account_status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lumina_user_devices (
    device_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    bound_at TEXT NOT NULL,
    revoked_at TEXT,
    device_label TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS lumina_phone_verifications (
    verification_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    otp_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'NOT_STARTED',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    verified_at TEXT,
    last_sent_at TEXT,
    device_id TEXT
);
"""


def connect_db(path: Optional[str] = None) -> sqlite3.Connection:
    """Open a SQLite connection with explicit production-safe pragmas.

    Same behavior as the historical ``app.evidence.db.connect_db``.
    """
    target = path or _default_db_path()
    conn = sqlite3.connect(target, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        if not target.startswith(":memory:"):
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError as e:
                logger.warning(
                    "Could not enable SQLite WAL journal at %s (continuing with default): %s",
                    target, e,
                )
    except sqlite3.OperationalError:
        logger.warning("Could not apply safe SQLite pragmas at %s", target)
    return conn


class SQLiteTransactionCtx(TransactionCtx):
    def execute(self, sql: str, params: Optional[tuple] = None) -> sqlite3.Cursor:
        return self.connection.execute(sql, params or ())

    def executemany(self, sql: str, params: List[tuple]) -> sqlite3.Cursor:
        return self.connection.executemany(sql, params)


class SQLiteBackend(PersistenceBackend):
    """Unified SQLite backend for evidence + incident persistence."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or _default_db_path()
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self.migrate()

    def _connect(self) -> sqlite3.Connection:
        return connect_db(self.path)

    def close(self) -> None:
        pass

    # ---- transactions ----

    @contextlib.contextmanager
    def transaction(self) -> Iterator[TransactionCtx]:
        conn = self._connect()
        try:
            with conn:
                yield SQLiteTransactionCtx(conn)
        finally:
            conn.close()

    @contextlib.contextmanager
    def _write_scope(self, txn: Optional[TransactionCtx]) -> Iterator[sqlite3.Connection]:
        """Provide a transaction-scoped connection.

        If `txn` is supplied (caller is inside a broader transaction), use its
        underlying connection without opening/committing/closing. Otherwise
        open a dedicated connection and commit on success / close on exit.
        """
        if txn is not None:
            yield txn.connection
            return
        own = self._connect()
        try:
            with own:
                yield own
        finally:
            own.close()

    # ---- migrations ----

    def migrate(self) -> None:
        conn = self._connect()
        try:
            with conn:
                conn.executescript(_EVIDENCE_SCHEMA)
                conn.executescript(_INCIDENT_SCHEMA)
                conn.executescript(_TRANSCRIPT_SCHEMA)
                conn.executescript(_IDENTITY_SCHEMA)
                run_migrations(conn)
        finally:
            conn.close()

    # ---- device auth ----

    def register_device(self, device_id: str, device_secret_hash: str) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO devices (device_id, device_secret_hash, created_at) "
                "VALUES (?, ?, ?)",
                (device_id, device_secret_hash, datetime.now().isoformat()),
            )
        conn.close()

    def get_device_secret(self, device_id: str) -> Optional[str]:
        conn = self._connect()
        row = conn.execute(
            "SELECT device_secret_hash FROM devices WHERE device_id = ?", (device_id,)
        ).fetchone()
        conn.close()
        return None if row is None else row["device_secret_hash"]

    def device_exists(self, device_id: str) -> bool:
        conn = self._connect()
        row = conn.execute(
            "SELECT 1 FROM devices WHERE device_id = ?", (device_id,)
        ).fetchone()
        conn.close()
        return row is not None

    def bind_session_to_device(self, device_id: str, session_id: str) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO device_sessions (device_id, session_id, created_at) "
                "VALUES (?, ?, ?)",
                (device_id, session_id, datetime.now().isoformat()),
            )
        conn.close()

    def get_session_owner(self, session_id: str) -> Optional[str]:
        conn = self._connect()
        row = conn.execute(
            "SELECT device_id FROM device_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        conn.close()
        return None if row is None else row["device_id"]

    # ---- evidence foundation ----

    def create_session(self, session_id: str, started_at: str) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (session_id, started_at, created_at) "
                "VALUES (?, ?, ?)",
                (session_id, started_at, datetime.now().isoformat()),
            )
        conn.close()

    def append_event(self, event: TimelineEvent) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO events "
                "(session_id, sequence, event_type, timestamp, payload_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (event.session_id, event.sequence, event.event_type.value,
                 event.timestamp, json.dumps(event.payload)),
            )
        conn.close()

    def add_evidence(self, evidence: Evidence) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO evidence "
                "(evidence_id, session_id, type, status, source, value_json, timestamp, "
                " sequence, confidence, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (evidence.evidence_id, evidence.session_id, evidence.type,
                 evidence.status.value, evidence.source.value,
                 json.dumps(evidence.value) if evidence.value is not None else None,
                 evidence.timestamp, evidence.sequence, evidence.confidence,
                 json.dumps(evidence.metadata or {})),
            )
        conn.close()

    def record_decision(self, session_id: str, decision: Dict) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT INTO decisions "
                "(session_id, state, reason_codes_json, recommended_action, decision_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, decision.get("state", ""),
                 json.dumps(decision.get("reason_codes", [])),
                 decision.get("recommended_action", ""),
                 json.dumps(decision),
                 datetime.now().isoformat()),
            )
        conn.close()

    def record_outcome(self, session_id: str, outcome: str) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT INTO outcomes (session_id, outcome, created_at) VALUES (?, ?, ?)",
                (session_id, outcome, datetime.now().isoformat()),
            )
        conn.close()

    def get_session(self, session_id: str) -> Optional[Session]:
        conn = self._connect()
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            conn.close()
            return None
        session = Session(session_id=row["session_id"], started_at=row["started_at"])
        for erow in conn.execute(
            "SELECT * FROM events WHERE session_id = ? ORDER BY sequence", (session_id,)
        ).fetchall():
            session.events.append(
                TimelineEvent(
                    session_id=session_id,
                    event_type=TimelineEventType(erow["event_type"]),
                    sequence=erow["sequence"],
                    timestamp=erow["timestamp"],
                    payload=json.loads(erow["payload_json"] or "{}"),
                )
            )
        for vrow in conn.execute(
            "SELECT * FROM evidence WHERE session_id = ? ORDER BY sequence", (session_id,)
        ).fetchall():
            session.evidence.append(
                Evidence(
                    session_id=session_id,
                    type=vrow["type"],
                    value=json.loads(vrow["value_json"]) if vrow["value_json"] else None,
                    status=EvidenceStatus(vrow["status"]),
                    source=EvidenceSource(vrow["source"]),
                    timestamp=vrow["timestamp"],
                    sequence=vrow["sequence"],
                    confidence=vrow["confidence"],
                    evidence_id=vrow["evidence_id"],
                    metadata=json.loads(vrow["metadata_json"] or "{}"),
                )
            )
        conn.close()
        return session

    def get_latest_decision(self, session_id: str) -> Optional[Dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT decision_json FROM decisions WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        try:
            return json.loads(row["decision_json"])
        except (ValueError, TypeError):
            return None

    def get_outcomes(self, session_id: str) -> List[str]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT outcome FROM outcomes WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
        conn.close()
        return [r["outcome"] for r in rows]

    def list_sessions(self, limit: int = 50) -> List[Dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT session_id, started_at FROM sessions ORDER BY started_at DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ---- incident writes (txn-aware) ----

    def create_incident(self, incident: Incident, txn: Optional[TransactionCtx] = None) -> None:
        with self._write_scope(txn) as c:
            c.execute(
                "INSERT OR IGNORE INTO incidents "
                "(incident_id, owner_device_id, created_at, updated_at, status, priority, "
                "next_action_json, unknowns_json, session_ids_json, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    incident.incident_id,
                    incident.owner_device_id,
                    incident.created_at,
                    incident.updated_at,
                    incident.status.value,
                    incident.priority.value,
                    json.dumps(incident.next_action.to_dict()) if incident.next_action else None,
                    json.dumps(incident.unknowns),
                    json.dumps(incident.session_ids),
                    json.dumps(incident.metadata),
                ),
            )

    def update_incident(self, incident: Incident, txn: Optional[TransactionCtx] = None) -> None:
        with self._write_scope(txn) as c:
            c.execute(
                "UPDATE incidents SET "
                "owner_device_id = ?, updated_at = ?, status = ?, priority = ?, "
                "next_action_json = ?, unknowns_json = ?, session_ids_json = ?, metadata_json = ? "
                "WHERE incident_id = ?",
                (
                    incident.owner_device_id,
                    incident.updated_at,
                    incident.status.value,
                    incident.priority.value,
                    json.dumps(incident.next_action.to_dict()) if incident.next_action else None,
                    json.dumps(incident.unknowns),
                    json.dumps(incident.session_ids),
                    json.dumps(incident.metadata),
                    incident.incident_id,
                ),
            )

    def append_timeline_entry(
        self, incident_id: str, entry: TimelineEntry, txn: Optional[TransactionCtx] = None
    ) -> None:
        with self._write_scope(txn) as c:
            c.execute(
                "INSERT OR IGNORE INTO incident_timeline "
                "(incident_id, entry_id, entry_type, sequence, timestamp, "
                "summary, epistemic_status, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    incident_id,
                    entry.entry_id,
                    entry.entry_type.value,
                    entry.sequence,
                    entry.timestamp,
                    entry.summary,
                    entry.epistemic_status.value,
                    json.dumps(entry.metadata),
                ),
            )

    def add_user_action(
        self, incident_id: str, action: UserAction, txn: Optional[TransactionCtx] = None
    ) -> None:
        with self._write_scope(txn) as c:
            c.execute(
                "INSERT OR IGNORE INTO incident_actions "
                "(incident_id, action_id, action_type, description, timestamp, sequence) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    incident_id,
                    action.action_id,
                    action.action_type.value,
                    action.description,
                    action.timestamp,
                    action.sequence,
                ),
            )

    def upsert_exposure(
        self, incident_id: str, state: ExposureState, txn: Optional[TransactionCtx] = None
    ) -> None:
        with self._write_scope(txn) as c:
            c.execute(
                "INSERT OR REPLACE INTO incident_exposure "
                "(incident_id, category, level, evidence_basis, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    incident_id,
                    state.category.value,
                    state.level.value,
                    state.evidence_basis,
                    state.updated_at,
                ),
            )

    def upsert_exposure_batch(
        self,
        incident_id: str,
        exposure: Dict[ExposureCategory, ExposureState],
        txn: Optional[TransactionCtx] = None,
    ) -> None:
        with self._write_scope(txn) as c:
            for category, state in exposure.items():
                c.execute(
                    "INSERT OR REPLACE INTO incident_exposure "
                    "(incident_id, category, level, evidence_basis, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        incident_id,
                        category.value,
                        state.level.value,
                        state.evidence_basis,
                        state.updated_at,
                    ),
                )

    def save_transcript(self, transcript: Transcript, txn: Optional[TransactionCtx] = None) -> None:
        with self._write_scope(txn) as c:
            c.execute(
                "INSERT OR IGNORE INTO transcripts "
                "(transcript_id, incident_id, source, text, created_at, segments_json, provenance_json, batch_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    transcript.transcript_id,
                    transcript.incident_id,
                    transcript.source.value,
                    transcript.text,
                    transcript.created_at,
                    json.dumps([s.to_dict() for s in transcript.segments]),
                    json.dumps(transcript.provenance),
                    transcript.batch_id,
                ),
            )
            for segment in transcript.segments:
                c.execute(
                    "INSERT OR IGNORE INTO transcript_segments "
                    "(segment_id, transcript_id, incident_id, text, start_time, end_time, "
                    "speaker, source_provider, created_at, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        segment.segment_id,
                        transcript.transcript_id,
                        transcript.incident_id,
                        segment.text,
                        segment.start_time,
                        segment.end_time,
                        segment.speaker,
                        segment.source_provider,
                        segment.created_at,
                        json.dumps(segment.metadata),
                    ),
                )

    def save_segments_batch(
        self,
        incident_id: str,
        transcript_id: str,
        segments: List,
        txn: Optional[TransactionCtx] = None,
    ) -> None:
        with self._write_scope(txn) as c:
            for segment in segments:
                c.execute(
                    "INSERT OR IGNORE INTO transcript_segments "
                    "(segment_id, transcript_id, incident_id, text, start_time, end_time, "
                    "speaker, source_provider, created_at, metadata_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        segment.segment_id,
                        transcript_id,
                        incident_id,
                        segment.text,
                        segment.start_time,
                        segment.end_time,
                        segment.speaker,
                        segment.source_provider,
                        segment.created_at,
                        json.dumps(segment.metadata),
                    ),
                )

    def save_extraction_result(
        self, incident_id: str, result: ExtractionResult, txn: Optional[TransactionCtx] = None
    ) -> None:
        with self._write_scope(txn) as c:
            for obs in result.observations:
                c.execute(
                    "INSERT OR IGNORE INTO transcript_extractions "
                    "(transcript_id, incident_id, observation_type, action_type, "
                    "text_span, span_start, span_end, extraction_method, epistemic_note, confidence) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        result.transcript_id,
                        incident_id,
                        obs.observation_type.value,
                        None,
                        obs.text_span,
                        obs.span_start,
                        obs.span_end,
                        obs.extraction_method,
                        obs.epistemic_note,
                        obs.confidence_in_extraction,
                    ),
                )
            for action in result.user_actions:
                c.execute(
                    "INSERT OR IGNORE INTO transcript_extractions "
                    "(transcript_id, incident_id, observation_type, action_type, "
                    "text_span, span_start, span_end, extraction_method, epistemic_note, confidence) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        result.transcript_id,
                        incident_id,
                        None,
                        action.action_type,
                        action.text_span,
                        action.span_start,
                        action.span_end,
                        action.extraction_method,
                        action.description,
                        0.85,
                    ),
                )

    # ---- incident reads ----

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        conn = self._connect()
        row = conn.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)).fetchone()
        if row is None:
            conn.close()
            return None
        incident = Incident(
            incident_id=row["incident_id"],
            owner_device_id=row["owner_device_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status=IncidentStatus(row["status"]),
            priority=Priority(row["priority"]),
            session_ids=json.loads(row["session_ids_json"] or "[]"),
            metadata=json.loads(row["metadata_json"] or "{}"),
            unknowns=json.loads(row["unknowns_json"] or "[]"),
        )
        na_json = row["next_action_json"]
        if na_json:
            na = json.loads(na_json)
            incident.next_action = RecommendedAction(
                action=na["action"],
                reason=na["reason"],
                evidence_basis=na.get("evidence_basis", []),
                urgency=Priority(na["urgency"]),
                official_channel_guidance=na.get("official_channel_guidance"),
            )
        for trow in conn.execute(
            "SELECT * FROM incident_timeline WHERE incident_id = ? ORDER BY sequence",
            (incident_id,),
        ).fetchall():
            incident.timeline.append(TimelineEntry(
                entry_id=trow["entry_id"],
                entry_type=TimelineEntryType(trow["entry_type"]),
                sequence=trow["sequence"],
                timestamp=trow["timestamp"],
                summary=trow["summary"],
                epistemic_status=EpistemicStatus(trow["epistemic_status"]),
                metadata=json.loads(trow["metadata_json"] or "{}"),
            ))
        for arow in conn.execute(
            "SELECT * FROM incident_actions WHERE incident_id = ? ORDER BY sequence",
            (incident_id,),
        ).fetchall():
            incident.user_actions.append(UserAction(
                action_id=arow["action_id"],
                action_type=UserActionType(arow["action_type"]),
                description=arow["description"],
                timestamp=arow["timestamp"],
                sequence=arow["sequence"],
            ))
        for erow in conn.execute(
            "SELECT * FROM incident_exposure WHERE incident_id = ?", (incident_id,)
        ).fetchall():
            cat = ExposureCategory(erow["category"])
            incident.exposure[cat] = ExposureState(
                category=cat,
                level=ExposureLevel(erow["level"]),
                evidence_basis=erow["evidence_basis"],
                updated_at=erow["updated_at"],
            )
        conn.close()
        return incident

    def list_incidents(self, limit: int = 50, owner_device_id: Optional[str] = None) -> List[Dict]:
        conn = self._connect()
        if owner_device_id is not None:
            rows = conn.execute(
                "SELECT incident_id, created_at, updated_at, status, priority "
                "FROM incidents WHERE owner_device_id = ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (owner_device_id, max(1, min(int(limit), 500))),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT incident_id, created_at, updated_at, status, priority "
                "FROM incidents ORDER BY updated_at DESC LIMIT ?",
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def has_batch(self, batch_id: str) -> bool:
        if not batch_id:
            return False
        conn = self._connect()
        row = conn.execute("SELECT 1 FROM transcripts WHERE batch_id = ? LIMIT 1", (batch_id,)).fetchone()
        conn.close()
        return row is not None

    def get_segments(self, incident_id: str) -> List[Dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM transcript_segments WHERE incident_id = ? ORDER BY created_at, id",
            (incident_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_transcripts(self, incident_id: str) -> List[Dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM transcripts WHERE incident_id = ? ORDER BY created_at",
            (incident_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_extractions(self, incident_id: str) -> List[Dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM transcript_extractions WHERE incident_id = ?", (incident_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ---- trusted contacts ----

    def save_trusted_contact(
        self,
        contact_id: str,
        owner_device_id: str,
        display_name: str,
        delivery_channel: str,
        destination: str,
        enabled: bool,
        automatic_help_enabled: bool,
        configured_at: str,
        updated_at: str,
        created_at: str,
        txn: Optional[TransactionCtx] = None,
    ) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT OR REPLACE INTO trusted_contacts "
                "(contact_id, owner_device_id, display_name, delivery_channel, "
                "destination, enabled, automatic_help_enabled, configured_at, "
                "updated_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    contact_id, owner_device_id, display_name, delivery_channel,
                    destination, int(enabled), int(automatic_help_enabled),
                    configured_at, updated_at, created_at,
                ),
            )
        if txn is not None:
            _do(txn.connection)
        else:
            conn = self._connect()
            try:
                _do(conn)
                conn.commit()
            finally:
                conn.close()

    def get_trusted_contact(self, owner_device_id: str) -> Optional[Dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM trusted_contacts WHERE owner_device_id = ?",
            (owner_device_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_trusted_contact_by_id(self, contact_id: str) -> Optional[Dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM trusted_contacts WHERE contact_id = ?",
            (contact_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    # ---- help requests ----

    def save_help_request(
        self,
        request_id: str,
        incident_id: str,
        owner_device_id: str,
        contact_id: Optional[str],
        status: str,
        delivery_channel: str,
        reason: Optional[str],
        provider_request_id: Optional[str],
        delivered_at: Optional[str],
        failed_at: Optional[str],
        failure_reason: Optional[str],
        created_at: str,
        updated_at: str,
        txn: Optional[TransactionCtx] = None,
    ) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT OR REPLACE INTO help_requests "
                "(request_id, incident_id, owner_device_id, contact_id, "
                "status, delivery_channel, reason, provider_request_id, "
                "delivered_at, failed_at, failure_reason, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    request_id, incident_id, owner_device_id, contact_id,
                    status, delivery_channel, reason, provider_request_id,
                    delivered_at, failed_at, failure_reason, created_at, updated_at,
                ),
            )
        if txn is not None:
            _do(txn.connection)
        else:
            conn = self._connect()
            try:
                _do(conn)
                conn.commit()
            finally:
                conn.close()

    def get_help_request_for_incident(self, incident_id: str) -> Optional[Dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM help_requests WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_help_request_status(
        self,
        request_id: str,
        status: str,
        failure_reason: Optional[str] = None,
        txn: Optional[TransactionCtx] = None,
    ) -> Optional[Dict]:
        def _do(conn: sqlite3.Connection) -> Optional[Dict]:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            updates = ["status = ?", "updated_at = ?"]
            params: list = [status, now]
            if status == "DELIVERED":
                updates.append("delivered_at = ?")
                params.append(now)
            if status == "FAILED":
                updates.append("failed_at = ?")
                params.append(now)
                if failure_reason:
                    updates.append("failure_reason = ?")
                    params.append(failure_reason)
            params.append(request_id)
            conn.execute(
                f"UPDATE help_requests SET {', '.join(updates)} WHERE request_id = ?",
                params,
            )
            row = conn.execute(
                "SELECT * FROM help_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            return dict(row) if row else None
        if txn is not None:
            return _do(txn.connection)
        conn = self._connect()
        try:
            result = _do(conn)
            conn.commit()
            return result
        finally:
            conn.close()

    # ---- help policies ----

    def save_help_policy(
        self,
        owner_device_id: str,
        automatic_detection_enabled: bool,
        automatic_help_request_enabled: bool,
        auto_help_threshold: str,
        updated_at: str,
        txn: Optional[TransactionCtx] = None,
    ) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT OR REPLACE INTO help_policies "
                "(owner_device_id, automatic_detection_enabled, "
                "automatic_help_request_enabled, auto_help_threshold, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    owner_device_id, int(automatic_detection_enabled),
                    int(automatic_help_request_enabled), auto_help_threshold,
                    updated_at,
                ),
            )
        if txn is not None:
            _do(txn.connection)
        else:
            conn = self._connect()
            try:
                _do(conn)
                conn.commit()
            finally:
                conn.close()

    def get_help_policy(self, owner_device_id: str) -> Optional[Dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM help_policies WHERE owner_device_id = ?",
            (owner_device_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    # ---- identity (CP-25) ----

    def save_user(
        self,
        user_id: str,
        display_name: str,
        phone_number: str,
        phone_verified: bool,
        emergency_consent: str,
        account_status: str = "ACTIVE",
        created_at: str = "",
        updated_at: str = "",
        txn: Optional[TransactionCtx] = None,
    ) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO lumina_users "
                "(user_id, display_name, phone_number, phone_verified, "
                "emergency_consent, account_status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "display_name = excluded.display_name, "
                "phone_number = excluded.phone_number, "
                "phone_verified = excluded.phone_verified, "
                "emergency_consent = excluded.emergency_consent, "
                "account_status = excluded.account_status, "
                "updated_at = excluded.updated_at",
                (user_id, display_name, phone_number, int(phone_verified),
                 emergency_consent, account_status, created_at, updated_at),
            )
        if txn is not None:
            _do(txn.connection)
        else:
            conn = self._connect()
            try:
                _do(conn)
                conn.commit()
            finally:
                conn.close()

    def get_user(self, user_id: str) -> Optional[Dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM lumina_users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_user_by_phone(self, phone_number: str) -> Optional[Dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM lumina_users WHERE phone_number = ?",
            (phone_number,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_user(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        phone_verified: Optional[bool] = None,
        emergency_consent: Optional[str] = None,
        account_status: Optional[str] = None,
        updated_at: Optional[str] = None,
        txn: Optional[TransactionCtx] = None,
    ) -> Optional[Dict]:
        conn = self._connect()
        updates = []
        params: list = []
        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name)
        if phone_verified is not None:
            updates.append("phone_verified = ?")
            params.append(int(phone_verified))
        if emergency_consent is not None:
            updates.append("emergency_consent = ?")
            params.append(emergency_consent)
        if account_status is not None:
            updates.append("account_status = ?")
            params.append(account_status)
        if updated_at is not None:
            updates.append("updated_at = ?")
            params.append(updated_at)
        if not updates:
            conn.close()
            return self.get_user(user_id)
        params.append(user_id)
        with conn:
            conn.execute(
                f"UPDATE lumina_users SET {', '.join(updates)} WHERE user_id = ?",
                tuple(params),
            )
        conn.close()
        return self.get_user(user_id)

    def save_user_device(
        self,
        device_id: str,
        user_id: str,
        status: str,
        bound_at: str,
        revoked_at: Optional[str],
        device_label: str,
        txn: Optional[TransactionCtx] = None,
    ) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO lumina_user_devices "
                "(device_id, user_id, status, bound_at, revoked_at, device_label) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (device_id) DO UPDATE SET "
                "status = excluded.status, "
                "bound_at = excluded.bound_at, "
                "revoked_at = excluded.revoked_at, "
                "device_label = excluded.device_label",
                (device_id, user_id, status, bound_at, revoked_at, device_label),
            )
        if txn is not None:
            _do(txn.connection)
        else:
            conn = self._connect()
            try:
                _do(conn)
                conn.commit()
            finally:
                conn.close()

    def get_user_device(self, device_id: str) -> Optional[Dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM lumina_user_devices WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def revoke_user_device(
        self,
        device_id: str,
        revoked_at: str,
        txn: Optional[TransactionCtx] = None,
    ) -> Optional[Dict]:
        conn = self._connect()
        with conn:
            cur = conn.execute(
                "UPDATE lumina_user_devices SET status = 'REVOKED', revoked_at = ? "
                "WHERE device_id = ?",
                (revoked_at, device_id),
            )
        if cur.rowcount == 0:
            row = None
        else:
            row = conn.execute(
                "SELECT * FROM lumina_user_devices WHERE device_id = ?", (device_id,)
            ).fetchone()
        conn.close()
        return dict(row) if row else None

    def save_phone_verification(
        self,
        verification_id: str,
        user_id: str,
        phone_number: str,
        otp_hash: str,
        status: str,
        attempts: int,
        max_attempts: int,
        created_at: str,
        expires_at: str,
        verified_at: Optional[str],
        last_sent_at: Optional[str],
        device_id: Optional[str] = None,
        txn: Optional[TransactionCtx] = None,
    ) -> None:
        def _do(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO lumina_phone_verifications "
                "(verification_id, user_id, phone_number, otp_hash, status, "
                "attempts, max_attempts, created_at, expires_at, verified_at, "
                "last_sent_at, device_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (verification_id) DO UPDATE SET "
                "status = excluded.status, "
                "attempts = excluded.attempts, "
                "verified_at = excluded.verified_at, "
                "device_id = excluded.device_id",
                (verification_id, user_id, phone_number, otp_hash, status,
                 attempts, max_attempts, created_at, expires_at, verified_at,
                 last_sent_at, device_id),
            )
        if txn is not None:
            _do(txn.connection)
        else:
            conn = self._connect()
            try:
                _do(conn)
                conn.commit()
            finally:
                conn.close()

    def get_phone_verification(self, verification_id: str) -> Optional[Dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM lumina_phone_verifications WHERE verification_id = ?",
            (verification_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_latest_phone_verification(
        self, user_id: str, phone_number: str
    ) -> Optional[Dict]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM lumina_phone_verifications "
                "WHERE user_id = ? AND phone_number = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id, phone_number),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_phone_verification(
        self,
        verification_id: str,
        status: Optional[str] = None,
        attempts: Optional[int] = None,
        verified_at: Optional[str] = None,
        txn: Optional[TransactionCtx] = None,
    ) -> Optional[Dict]:
        conn = self._connect()
        updates = []
        params: list = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if attempts is not None:
            updates.append("attempts = ?")
            params.append(attempts)
        if verified_at is not None:
            updates.append("verified_at = ?")
            params.append(verified_at)
        if not updates:
            conn.close()
            return self.get_phone_verification(verification_id)
        params.append(verification_id)
        with conn:
            conn.execute(
                f"UPDATE lumina_phone_verifications SET {', '.join(updates)} "
                "WHERE verification_id = ?",
                tuple(params),
            )
        conn.close()
        return self.get_phone_verification(verification_id)

    def consume_phone_verification_attempt(
        self, verification_id: str, now_iso: str
    ) -> Optional[Dict]:
        """Atomically increment the attempt counter for a live verification.

        Returns the refreshed row ONLY when an attempt slot was actually
        consumed; returns None when the verification is not live (missing,
        already LOCKED/FAILED/EXPIRED/VERIFIED, past max_attempts, or past
        expires_at). The guarded single UPDATE makes the check race-safe.
        """
        conn = self._connect()
        try:
            with conn:
                cur = conn.execute(
                    "UPDATE lumina_phone_verifications SET "
                    "attempts = attempts + 1, "
                    "status = CASE "
                    "  WHEN attempts + 1 >= max_attempts THEN 'LOCKED' "
                    "  ELSE status END "
                    "WHERE verification_id = ? "
                    "AND status = 'CODE_SENT' "
                    "AND attempts < max_attempts "
                    "AND (expires_at IS NULL OR expires_at > ?)",
                    (verification_id, now_iso),
                )
                if cur.rowcount == 0:
                    return None
            row = conn.execute(
                "SELECT * FROM lumina_phone_verifications WHERE verification_id = ?",
                (verification_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_user_account(self, user_id: str) -> bool:
        """Permanently delete all account identity data for a user (atomic).

        Device bindings are REVOKED and kept as tombstones so account-bound
        device authorization stops (a deleted account's device credential
        can no longer act as that account), while the registered HMAC device
        credential that safety features depend on stays intact.
        """
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    "UPDATE lumina_user_devices SET status = 'REVOKED', revoked_at = ? "
                    "WHERE user_id = ?",
                    (datetime.now().isoformat(), user_id),
                )
                conn.execute(
                    "DELETE FROM lumina_phone_verifications WHERE user_id = ?",
                    (user_id,),
                )
                conn.execute(
                    "DELETE FROM trusted_contacts WHERE owner_device_id IN "
                    "(SELECT device_id FROM lumina_user_devices WHERE user_id = ?)",
                    (user_id,),
                )
                conn.execute(
                    "DELETE FROM help_policies WHERE owner_device_id IN "
                    "(SELECT device_id FROM lumina_user_devices WHERE user_id = ?)",
                    (user_id,),
                )
                conn.execute(
                    "UPDATE incidents SET owner_device_id = NULL "
                    "WHERE owner_device_id IN "
                    "(SELECT device_id FROM lumina_user_devices WHERE user_id = ?)",
                    (user_id,),
                )
                cur = conn.execute(
                    "DELETE FROM lumina_users WHERE user_id = ?",
                    (user_id,),
                )
            return cur.rowcount > 0
        except sqlite3.Error:
            return False
        finally:
            conn.close()
