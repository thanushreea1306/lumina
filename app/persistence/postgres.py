# app/persistence/postgres.py
"""PostgreSQL (Supabase) persistence backend for LUMINA production.

This backend persists the SAME unified set of tables as the SQLite backend,
so a deployment can move between backends without changing domain logic or
API contracts. It runs against any PostgreSQL database (a Supabase free-tier
project is the intended production target).

Design notes:
  - JSON columns are stored as TEXT (same as SQLite) to keep the domain
    serialization identical and the migration/import path trivial.
  - Idempotent inserts use ``ON CONFLICT DO NOTHING``.
  - Exposure upserts use ``ON CONFLICT ... DO UPDATE``.
  - Transactions map to psycopg connection transactions.
  - ``?`` placeholders become ``%s`` (psycopg).
  - AUTOINCREMENT surrogate keys become ``BIGSERIAL``.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import psycopg
from psycopg.rows import dict_row

from app.evidence.models import Evidence, EvidenceSource, EvidenceStatus, Session, TimelineEvent, TimelineEventType
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

logger = logging.getLogger(__name__)

DEFAULT_URL_ENV = "DATABASE_URL"


def _dsn() -> str:
    url = os.getenv(DEFAULT_URL_ENV)
    if not url:
        url = os.getenv("LUMINA_DB_URL")
    if not url:
        raise RuntimeError(
            "Postgres backend selected (LUMINA_DB_BACKEND=postgres) but neither "
            "DATABASE_URL nor LUMINA_DB_URL is set. Refusing to start silently with "
            "an unconfigured production database."
        )
    return url


# ---- DDL ----

_SCHEMA = """
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

CREATE TABLE IF NOT EXISTS used_nonces (
    device_id TEXT NOT NULL,
    nonce TEXT NOT NULL,
    used_at TEXT NOT NULL,
    PRIMARY KEY (device_id, nonce)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    sequence BIGINT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload_json TEXT,
    UNIQUE (session_id, sequence)
);

CREATE TABLE IF NOT EXISTS evidence (
    id BIGSERIAL PRIMARY KEY,
    evidence_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    value_json TEXT,
    timestamp TEXT NOT NULL,
    sequence BIGINT NOT NULL,
    confidence DOUBLE PRECISION,
    metadata_json TEXT,
    UNIQUE (evidence_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    state TEXT NOT NULL,
    reason_codes_json TEXT,
    recommended_action TEXT,
    decision_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcomes (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

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
    id BIGSERIAL PRIMARY KEY,
    incident_id TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    sequence BIGINT NOT NULL,
    timestamp TEXT NOT NULL,
    summary TEXT NOT NULL,
    epistemic_status TEXT NOT NULL,
    metadata_json TEXT,
    UNIQUE (incident_id, sequence)
);

CREATE TABLE IF NOT EXISTS incident_actions (
    id BIGSERIAL PRIMARY KEY,
    incident_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    description TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    sequence BIGINT NOT NULL,
    UNIQUE (incident_id, action_id)
);

CREATE TABLE IF NOT EXISTS incident_exposure (
    id BIGSERIAL PRIMARY KEY,
    incident_id TEXT NOT NULL,
    category TEXT NOT NULL,
    level TEXT NOT NULL,
    evidence_basis TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (incident_id, category)
);

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
    id BIGSERIAL PRIMARY KEY,
    transcript_id TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    observation_type TEXT,
    action_type TEXT,
    text_span TEXT NOT NULL,
    span_start BIGINT NOT NULL,
    span_end BIGINT NOT NULL,
    extraction_method TEXT NOT NULL,
    epistemic_note TEXT,
    confidence DOUBLE PRECISION,
    UNIQUE (transcript_id, observation_type, action_type)
);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id BIGSERIAL PRIMARY KEY,
    segment_id TEXT NOT NULL UNIQUE,
    transcript_id TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    text TEXT NOT NULL,
    start_time DOUBLE PRECISION,
    end_time DOUBLE PRECISION,
    speaker TEXT,
    source_provider TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
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

# Migrations that a fresh schema already includes; recorded as applied so the
# tracking table is consistent and an import from an older SQLite DB can run
# the same guards.
_FRESH_MIGRATIONS = [
    "transcripts.batch_id",
    "incidents.owner_device_id",
    "identity.lumina_phone_verifications.device_id",
    "identity.lumina_users.phone_number_unique",
    "auth.used_nonces_table",
]


def _migrate_identity(conn: Any) -> None:
    """Idempotent, non-destructive identity migrations for Postgres.

    Mirrors the SQLite identity migrations (app/evidence/schema.py). Safe to
    run on every startup: ADD COLUMN IF NOT EXISTS, a dedupe that only touches
    duplicate phone rows, and a CREATE UNIQUE INDEX IF NOT EXISTS.
    """
    conn.execute(
        "ALTER TABLE lumina_phone_verifications ADD COLUMN IF NOT EXISTS device_id TEXT"
    )
    conn.execute(
        "ALTER TABLE lumina_users ADD COLUMN IF NOT EXISTS "
        "account_status TEXT NOT NULL DEFAULT 'ACTIVE'"
    )
    # De-duplicate any pre-existing duplicate phone rows, keeping the most
    # recently updated account per phone. Only rows with a non-empty phone
    # are candidates; unique phones are untouched.
    conn.execute(
        """
        DELETE FROM lumina_users
        WHERE phone_number <> ''
          AND user_id NOT IN (
              SELECT user_id FROM (
                  SELECT user_id,
                         ROW_NUMBER() OVER (
                           PARTITION BY phone_number
                           ORDER BY updated_at DESC, created_at DESC
                         ) AS rn
                  FROM lumina_users
              ) ranked
              WHERE rn = 1
          )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_lumina_users_phone_unique "
        "ON lumina_users (phone_number)"
    )


class PostgresTransactionCtx(TransactionCtx):
    def execute(self, sql: str, params: Optional[tuple] = None) -> Any:
        return self.connection.execute(sql, params or ())

    def executemany(self, sql: str, params: List[tuple]) -> Any:
        return self.connection.executemany(sql, params)

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params or ())
            return list(cur.fetchall())


class PostgresBackend(PersistenceBackend):
    """PostgreSQL backend for evidence + incident persistence."""

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or _dsn()
        self.migrate()

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def close(self) -> None:
        pass

    # ---- transactions ----

    @contextlib.contextmanager
    def transaction(self) -> Iterator[TransactionCtx]:
        conn = self._connect()
        try:
            with conn:  # psycopg: commits on clean exit, rolls back on error
                yield PostgresTransactionCtx(conn)
        finally:
            conn.close()

    @contextlib.contextmanager
    def _write_scope(self, txn: Optional[TransactionCtx]) -> Iterator[Any]:
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
                conn.execute(_SCHEMA)
                _migrate_identity(conn)
                now = datetime.now().astimezone().isoformat()
                for name in _FRESH_MIGRATIONS:
                    conn.execute(
                        "INSERT INTO schema_migrations (name, applied_at) "
                        "VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
                        (name, now),
                    )
        finally:
            conn.close()

    # ---- device auth ----

    def register_device(self, device_id: str, device_secret_hash: str) -> None:
        with self._write_scope(None) as c:
            c.execute(
                "INSERT INTO devices (device_id, device_secret_hash, created_at) "
                "VALUES (%s, %s, %s) ON CONFLICT (device_id) DO NOTHING",
                (device_id, device_secret_hash, datetime.now().isoformat()),
            )

    def get_device_secret(self, device_id: str) -> Optional[str]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT device_secret_hash FROM devices WHERE device_id = %s", (device_id,)
                )
                row = cur.fetchone()
        finally:
            conn.close()
        return None if row is None else row["device_secret_hash"]

    def device_exists(self, device_id: str) -> bool:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT 1 AS x FROM devices WHERE device_id = %s", (device_id,))
                return cur.fetchone() is not None
        finally:
            conn.close()

    def bind_session_to_device(self, device_id: str, session_id: str) -> None:
        with self._write_scope(None) as c:
            c.execute(
                "INSERT INTO device_sessions (device_id, session_id, created_at) "
                "VALUES (%s, %s, %s) ON CONFLICT (device_id, session_id) DO NOTHING",
                (device_id, session_id, datetime.now().isoformat()),
            )

    def get_session_owner(self, session_id: str) -> Optional[str]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT device_id FROM device_sessions WHERE session_id = %s", (session_id,)
                )
                row = cur.fetchone()
        finally:
            conn.close()
        return None if row is None else row["device_id"]

    # ---- durable nonce replay protection ----

    def use_nonce(self, device_id: str, nonce: str) -> bool:
        conn = self._connect()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO used_nonces (device_id, nonce, used_at) "
                        "VALUES (%s, %s, %s) ON CONFLICT (device_id, nonce) DO NOTHING",
                        (device_id, nonce, datetime.now().isoformat()),
                    )
                    inserted = cur.rowcount == 1
        finally:
            conn.close()
        return inserted

    def is_nonce_used(self, device_id: str, nonce: str) -> bool:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT 1 FROM used_nonces WHERE device_id = %s AND nonce = %s",
                    (device_id, nonce),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        return row is not None

    def prune_nonces(self, older_than: Optional[str] = None) -> int:
        conn = self._connect()
        try:
            with conn:
                with conn.cursor() as cur:
                    if older_than is None:
                        cur.execute("DELETE FROM used_nonces")
                    else:
                        cur.execute(
                            "DELETE FROM used_nonces WHERE used_at < %s", (older_than,)
                        )
                return cur.rowcount
        finally:
            conn.close()

    # ---- evidence foundation ----

    def create_session(self, session_id: str, started_at: str) -> None:
        with self._write_scope(None) as c:
            c.execute(
                "INSERT INTO sessions (session_id, started_at, created_at) "
                "VALUES (%s, %s, %s) ON CONFLICT (session_id) DO NOTHING",
                (session_id, started_at, datetime.now().isoformat()),
            )

    def append_event(self, event: TimelineEvent) -> None:
        with self._write_scope(None) as c:
            c.execute(
                "INSERT INTO events "
                "(session_id, sequence, event_type, timestamp, payload_json) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (session_id, sequence) DO NOTHING",
                (event.session_id, event.sequence, event.event_type.value,
                 event.timestamp, json.dumps(event.payload)),
            )

    def add_evidence(self, evidence: Evidence) -> None:
        with self._write_scope(None) as c:
            c.execute(
                "INSERT INTO evidence "
                "(evidence_id, session_id, type, status, source, value_json, timestamp, "
                " sequence, confidence, metadata_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (evidence_id) DO NOTHING",
                (evidence.evidence_id, evidence.session_id, evidence.type,
                 evidence.status.value, evidence.source.value,
                 json.dumps(evidence.value) if evidence.value is not None else None,
                 evidence.timestamp, evidence.sequence, evidence.confidence,
                 json.dumps(evidence.metadata or {})),
            )

    def record_decision(self, session_id: str, decision: Dict) -> None:
        with self._write_scope(None) as c:
            c.execute(
                "INSERT INTO decisions "
                "(session_id, state, reason_codes_json, recommended_action, decision_json, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (session_id, decision.get("state", ""),
                 json.dumps(decision.get("reason_codes", [])),
                 decision.get("recommended_action", ""),
                 json.dumps(decision),
                 datetime.now().isoformat()),
            )

    def record_outcome(self, session_id: str, outcome: str) -> None:
        with self._write_scope(None) as c:
            c.execute(
                "INSERT INTO outcomes (session_id, outcome, created_at) VALUES (%s, %s, %s)",
                (session_id, outcome, datetime.now().isoformat()),
            )

    def get_session(self, session_id: str) -> Optional[Session]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM sessions WHERE session_id = %s", (session_id,))
                row = cur.fetchone()
                if row is None:
                    return None
                session = Session(session_id=row["session_id"], started_at=row["started_at"])
                cur.execute("SELECT * FROM events WHERE session_id = %s ORDER BY sequence", (session_id,))
                for erow in cur.fetchall():
                    session.events.append(
                        TimelineEvent(
                            session_id=session_id,
                            event_type=TimelineEventType(erow["event_type"]),
                            sequence=erow["sequence"],
                            timestamp=erow["timestamp"],
                            payload=json.loads(erow["payload_json"] or "{}"),
                        )
                    )
                cur.execute("SELECT * FROM evidence WHERE session_id = %s ORDER BY sequence", (session_id,))
                for vrow in cur.fetchall():
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
                return session
        finally:
            conn.close()

    def get_latest_decision(self, session_id: str) -> Optional[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT decision_json FROM decisions WHERE session_id = %s ORDER BY id DESC LIMIT 1",
                    (session_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        try:
            return json.loads(row["decision_json"])
        except (ValueError, TypeError):
            return None

    def get_outcomes(self, session_id: str) -> List[str]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT outcome FROM outcomes WHERE session_id = %s ORDER BY id", (session_id,)
                )
                return [r["outcome"] for r in cur.fetchall()]
        finally:
            conn.close()

    def list_sessions(self, limit: int = 50) -> List[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT session_id, started_at FROM sessions ORDER BY started_at DESC LIMIT %s",
                    (max(1, min(int(limit), 500)),),
                )
                return list(cur.fetchall())
        finally:
            conn.close()

    # ---- incident writes (txn-aware) ----

    def create_incident(self, incident: Incident, txn: Optional[TransactionCtx] = None) -> None:
        with self._write_scope(txn) as c:
            c.execute(
                "INSERT INTO incidents "
                "(incident_id, owner_device_id, created_at, updated_at, status, priority, "
                "next_action_json, unknowns_json, session_ids_json, metadata_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (incident_id) DO NOTHING",
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
                "owner_device_id = %s, updated_at = %s, status = %s, priority = %s, "
                "next_action_json = %s, unknowns_json = %s, session_ids_json = %s, metadata_json = %s "
                "WHERE incident_id = %s",
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
                "INSERT INTO incident_timeline "
                "(incident_id, entry_id, entry_type, sequence, timestamp, "
                "summary, epistemic_status, metadata_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (incident_id, sequence) DO NOTHING",
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
                "INSERT INTO incident_actions "
                "(incident_id, action_id, action_type, description, timestamp, sequence) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (incident_id, action_id) DO NOTHING",
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
                "INSERT INTO incident_exposure "
                "(incident_id, category, level, evidence_basis, updated_at) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (incident_id, category) DO UPDATE SET "
                "level = EXCLUDED.level, evidence_basis = EXCLUDED.evidence_basis, "
                "updated_at = EXCLUDED.updated_at",
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
                    "INSERT INTO incident_exposure "
                    "(incident_id, category, level, evidence_basis, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (incident_id, category) DO UPDATE SET "
                    "level = EXCLUDED.level, evidence_basis = EXCLUDED.evidence_basis, "
                    "updated_at = EXCLUDED.updated_at",
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
                "INSERT INTO transcripts "
                "(transcript_id, incident_id, source, text, created_at, segments_json, provenance_json, batch_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (transcript_id) DO NOTHING",
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
                    "INSERT INTO transcript_segments "
                    "(segment_id, transcript_id, incident_id, text, start_time, end_time, "
                    "speaker, source_provider, created_at, metadata_json) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (segment_id) DO NOTHING",
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
                    "INSERT INTO transcript_segments "
                    "(segment_id, transcript_id, incident_id, text, start_time, end_time, "
                    "speaker, source_provider, created_at, metadata_json) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (segment_id) DO NOTHING",
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
                    "INSERT INTO transcript_extractions "
                    "(transcript_id, incident_id, observation_type, action_type, "
                    "text_span, span_start, span_end, extraction_method, epistemic_note, confidence) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (transcript_id, observation_type, action_type) DO NOTHING",
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
                    "INSERT INTO transcript_extractions "
                    "(transcript_id, incident_id, observation_type, action_type, "
                    "text_span, span_start, span_end, extraction_method, epistemic_note, confidence) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (transcript_id, observation_type, action_type) DO NOTHING",
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

    def get_incident(
        self, incident_id: str, owner_device_id: Optional[str] = None
    ) -> Optional[Incident]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                if owner_device_id is not None:
                    cur.execute(
                        "SELECT * FROM incidents "
                        "WHERE incident_id = %s AND owner_device_id = %s",
                        (incident_id, owner_device_id),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM incidents WHERE incident_id = %s", (incident_id,)
                    )
                row = cur.fetchone()
                if row is None:
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
                cur.execute(
                    "SELECT * FROM incident_timeline WHERE incident_id = %s ORDER BY sequence",
                    (incident_id,),
                )
                for trow in cur.fetchall():
                    incident.timeline.append(TimelineEntry(
                        entry_id=trow["entry_id"],
                        entry_type=TimelineEntryType(trow["entry_type"]),
                        sequence=trow["sequence"],
                        timestamp=trow["timestamp"],
                        summary=trow["summary"],
                        epistemic_status=EpistemicStatus(trow["epistemic_status"]),
                        metadata=json.loads(trow["metadata_json"] or "{}"),
                    ))
                cur.execute(
                    "SELECT * FROM incident_actions WHERE incident_id = %s ORDER BY sequence",
                    (incident_id,),
                )
                for arow in cur.fetchall():
                    incident.user_actions.append(UserAction(
                        action_id=arow["action_id"],
                        action_type=UserActionType(arow["action_type"]),
                        description=arow["description"],
                        timestamp=arow["timestamp"],
                        sequence=arow["sequence"],
                    ))
                cur.execute(
                    "SELECT * FROM incident_exposure WHERE incident_id = %s", (incident_id,)
                )
                for erow in cur.fetchall():
                    cat = ExposureCategory(erow["category"])
                    incident.exposure[cat] = ExposureState(
                        category=cat,
                        level=ExposureLevel(erow["level"]),
                        evidence_basis=erow["evidence_basis"],
                        updated_at=erow["updated_at"],
                    )
                return incident
        finally:
            conn.close()

    def list_incidents(self, limit: int = 50, owner_device_id: Optional[str] = None) -> List[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                if owner_device_id is not None:
                    cur.execute(
                        "SELECT incident_id, created_at, updated_at, status, "
                        "priority, metadata_json "
                        "FROM incidents WHERE owner_device_id = %s "
                        "ORDER BY updated_at DESC LIMIT %s",
                        (owner_device_id, max(1, min(int(limit), 500))),
                    )
                else:
                    cur.execute(
                        "SELECT incident_id, created_at, updated_at, status, "
                        "priority, metadata_json "
                        "FROM incidents ORDER BY updated_at DESC LIMIT %s",
                        (max(1, min(int(limit), 500)),),
                    )
                rows = list(cur.fetchall())
                result = []
                for r in rows:
                    row = dict(r)
                    raw_meta = row.pop("metadata_json", None) or "{}"
                    try:
                        row["metadata"] = (
                            json.loads(raw_meta) if isinstance(raw_meta, str) else raw_meta
                        )
                    except (ValueError, TypeError):
                        row["metadata"] = {}
                    result.append(row)
                return result
        finally:
            conn.close()

    def has_batch(self, batch_id: str) -> bool:
        if not batch_id:
            return False
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT 1 AS x FROM transcripts WHERE batch_id = %s LIMIT 1", (batch_id,))
                return cur.fetchone() is not None
        finally:
            conn.close()

    def get_segments(self, incident_id: str) -> List[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM transcript_segments WHERE incident_id = %s "
                    "ORDER BY created_at, id",
                    (incident_id,),
                )
                return list(cur.fetchall())
        finally:
            conn.close()

    def get_transcripts(self, incident_id: str) -> List[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM transcripts WHERE incident_id = %s ORDER BY created_at",
                    (incident_id,),
                )
                return list(cur.fetchall())
        finally:
            conn.close()

    def get_extractions(self, incident_id: str) -> List[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM transcript_extractions WHERE incident_id = %s", (incident_id,)
                )
                return list(cur.fetchall())
        finally:
            conn.close()

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
        def _do(cur) -> None:
            cur.execute(
                "INSERT INTO trusted_contacts "
                "(contact_id, owner_device_id, display_name, delivery_channel, "
                "destination, enabled, automatic_help_enabled, configured_at, "
                "updated_at, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (owner_device_id) DO UPDATE SET "
                "contact_id=EXCLUDED.contact_id, display_name=EXCLUDED.display_name, "
                "delivery_channel=EXCLUDED.delivery_channel, destination=EXCLUDED.destination, "
                "enabled=EXCLUDED.enabled, automatic_help_enabled=EXCLUDED.automatic_help_enabled, "
                "configured_at=EXCLUDED.configured_at, updated_at=EXCLUDED.updated_at",
                (
                    contact_id, owner_device_id, display_name, delivery_channel,
                    destination, int(enabled), int(automatic_help_enabled),
                    configured_at, updated_at, created_at,
                ),
            )
        if txn is not None:
            _do(txn.connection.cursor())
        else:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    _do(cur)
                conn.commit()
            finally:
                conn.close()

    def get_trusted_contact(self, owner_device_id: str) -> Optional[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM trusted_contacts WHERE owner_device_id = %s",
                    (owner_device_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def get_trusted_contact_by_id(self, contact_id: str) -> Optional[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM trusted_contacts WHERE contact_id = %s",
                    (contact_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

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
        def _do(cur) -> None:
            cur.execute(
                "INSERT INTO help_requests "
                "(request_id, incident_id, owner_device_id, contact_id, "
                "status, delivery_channel, reason, provider_request_id, "
                "delivered_at, failed_at, failure_reason, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (incident_id) DO UPDATE SET "
                "request_id=EXCLUDED.request_id, status=EXCLUDED.status, "
                "updated_at=EXCLUDED.updated_at",
                (
                    request_id, incident_id, owner_device_id, contact_id,
                    status, delivery_channel, reason, provider_request_id,
                    delivered_at, failed_at, failure_reason, created_at, updated_at,
                ),
            )
        if txn is not None:
            _do(txn.connection.cursor())
        else:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    _do(cur)
                conn.commit()
            finally:
                conn.close()

    def get_help_request_for_incident(self, incident_id: str) -> Optional[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM help_requests WHERE incident_id = %s",
                    (incident_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def update_help_request_status(
        self,
        request_id: str,
        status: str,
        failure_reason: Optional[str] = None,
        txn: Optional[TransactionCtx] = None,
    ) -> Optional[Dict]:
        def _do(cur) -> Optional[Dict]:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            updates = ["status = %s", "updated_at = %s"]
            params: list = [status, now]
            if status == "DELIVERED":
                updates.append("delivered_at = %s")
                params.append(now)
            if status == "FAILED":
                updates.append("failed_at = %s")
                params.append(now)
                if failure_reason:
                    updates.append("failure_reason = %s")
                    params.append(failure_reason)
            params.append(request_id)
            cur.execute(
                f"UPDATE help_requests SET {', '.join(updates)} WHERE request_id = %s",
                params,
            )
            cur.execute(
                "SELECT * FROM help_requests WHERE request_id = %s",
                (request_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        if txn is not None:
            return _do(txn.connection.cursor())
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                result = _do(cur)
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
        def _do(cur) -> None:
            cur.execute(
                "INSERT INTO help_policies "
                "(owner_device_id, automatic_detection_enabled, "
                "automatic_help_request_enabled, auto_help_threshold, updated_at) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (owner_device_id) DO UPDATE SET "
                "automatic_detection_enabled=EXCLUDED.automatic_detection_enabled, "
                "automatic_help_request_enabled=EXCLUDED.automatic_help_request_enabled, "
                "auto_help_threshold=EXCLUDED.auto_help_threshold, updated_at=EXCLUDED.updated_at",
                (
                    owner_device_id, int(automatic_detection_enabled),
                    int(automatic_help_request_enabled), auto_help_threshold,
                    updated_at,
                ),
            )
        if txn is not None:
            _do(txn.connection.cursor())
        else:
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    _do(cur)
                conn.commit()
            finally:
                conn.close()

    def get_help_policy(self, owner_device_id: str) -> Optional[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM help_policies WHERE owner_device_id = %s",
                    (owner_device_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

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
        with self._write_scope(txn) as c:
            c.execute(
                "INSERT INTO lumina_users "
                "(user_id, display_name, phone_number, phone_verified, "
                "emergency_consent, account_status, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "display_name = EXCLUDED.display_name, "
                "phone_number = EXCLUDED.phone_number, "
                "phone_verified = EXCLUDED.phone_verified, "
                "emergency_consent = EXCLUDED.emergency_consent, "
                "account_status = EXCLUDED.account_status, "
                "updated_at = EXCLUDED.updated_at",
                (user_id, display_name, phone_number, int(phone_verified),
                 emergency_consent, account_status, created_at, updated_at),
            )

    def get_user(self, user_id: str) -> Optional[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM lumina_users WHERE user_id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def get_user_by_phone(self, phone_number: str) -> Optional[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM lumina_users WHERE phone_number = %s",
                    (phone_number,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

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
        updates = []
        params: list = []
        if display_name is not None:
            updates.append("display_name = %s")
            params.append(display_name)
        if phone_verified is not None:
            updates.append("phone_verified = %s")
            params.append(int(phone_verified))
        if emergency_consent is not None:
            updates.append("emergency_consent = %s")
            params.append(emergency_consent)
        if account_status is not None:
            updates.append("account_status = %s")
            params.append(account_status)
        if updated_at is not None:
            updates.append("updated_at = %s")
            params.append(updated_at)
        if not updates:
            return self.get_user(user_id)
        params.append(user_id)
        with self._write_scope(txn) as c:
            c.execute(
                f"UPDATE lumina_users SET {', '.join(updates)} WHERE user_id = %s",
                tuple(params),
            )
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
        with self._write_scope(txn) as c:
            c.execute(
                "INSERT INTO lumina_user_devices "
                "(device_id, user_id, status, bound_at, revoked_at, device_label) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (device_id) DO UPDATE SET "
                "status = EXCLUDED.status, "
                "bound_at = EXCLUDED.bound_at, "
                "revoked_at = EXCLUDED.revoked_at, "
                "device_label = EXCLUDED.device_label",
                (device_id, user_id, status, bound_at, revoked_at, device_label),
            )

    def get_user_device(self, device_id: str) -> Optional[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM lumina_user_devices WHERE device_id = %s",
                    (device_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def revoke_user_device(
        self,
        device_id: str,
        revoked_at: str,
        txn: Optional[TransactionCtx] = None,
    ) -> Optional[Dict]:
        with self._write_scope(txn) as c:
            c.execute(
                "UPDATE lumina_user_devices SET status = 'REVOKED', revoked_at = %s "
                "WHERE device_id = %s",
                (revoked_at, device_id),
            )
            updated = c.rowcount > 0 if hasattr(c, "rowcount") else True
        if not updated:
            return None
        return self.get_user_device(device_id)

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
        with self._write_scope(txn) as c:
            c.execute(
                "INSERT INTO lumina_phone_verifications "
                "(verification_id, user_id, phone_number, otp_hash, status, "
                "attempts, max_attempts, created_at, expires_at, verified_at, "
                "last_sent_at, device_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (verification_id) DO UPDATE SET "
                "status = EXCLUDED.status, "
                "attempts = EXCLUDED.attempts, "
                "verified_at = EXCLUDED.verified_at, "
                "device_id = EXCLUDED.device_id",
                (verification_id, user_id, phone_number, otp_hash, status,
                 attempts, max_attempts, created_at, expires_at, verified_at,
                 last_sent_at, device_id),
            )

    def get_phone_verification(self, verification_id: str) -> Optional[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM lumina_phone_verifications WHERE verification_id = %s",
                    (verification_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def get_latest_phone_verification(
        self, user_id: str, phone_number: str
    ) -> Optional[Dict]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM lumina_phone_verifications "
                    "WHERE user_id = %s AND phone_number = %s "
                    "ORDER BY created_at DESC LIMIT 1",
                    (user_id, phone_number),
                )
                row = cur.fetchone()
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
        updates = []
        params: list = []
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        if attempts is not None:
            updates.append("attempts = %s")
            params.append(attempts)
        if verified_at is not None:
            updates.append("verified_at = %s")
            params.append(verified_at)
        if not updates:
            return self.get_phone_verification(verification_id)
        params.append(verification_id)
        with self._write_scope(txn) as c:
            c.execute(
                f"UPDATE lumina_phone_verifications SET {', '.join(updates)} "
                "WHERE verification_id = %s",
                tuple(params),
            )
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
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE lumina_phone_verifications SET "
                        "attempts = attempts + 1, "
                        "status = CASE "
                        "  WHEN attempts + 1 >= max_attempts THEN 'LOCKED' "
                        "  ELSE status END "
                        "WHERE verification_id = %s "
                        "AND status = 'CODE_SENT' "
                        "AND attempts < max_attempts "
                        "AND (expires_at IS NULL OR expires_at > %s)",
                        (verification_id, now_iso),
                    )
                    consumed = cur.rowcount > 0
            if not consumed:
                return None
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM lumina_phone_verifications "
                    "WHERE verification_id = %s",
                    (verification_id,),
                )
                row = cur.fetchone()
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
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE lumina_user_devices SET status = 'REVOKED', revoked_at = %s "
                        "WHERE user_id = %s",
                        (datetime.now().isoformat(), user_id),
                    )
                    cur.execute(
                        "DELETE FROM lumina_phone_verifications WHERE user_id = %s",
                        (user_id,),
                    )
                    cur.execute(
                        "DELETE FROM trusted_contacts WHERE owner_device_id IN "
                        "(SELECT device_id FROM lumina_user_devices WHERE user_id = %s)",
                        (user_id,),
                    )
                    cur.execute(
                        "DELETE FROM help_policies WHERE owner_device_id IN "
                        "(SELECT device_id FROM lumina_user_devices WHERE user_id = %s)",
                        (user_id,),
                    )
                    cur.execute(
                        "UPDATE incidents SET owner_device_id = NULL "
                        "WHERE owner_device_id IN "
                        "(SELECT device_id FROM lumina_user_devices WHERE user_id = %s)",
                        (user_id,),
                    )
                    cur.execute(
                        "DELETE FROM lumina_users WHERE user_id = %s",
                        (user_id,),
                    )
                    deleted = cur.rowcount > 0
            return deleted
        except Exception:
            return False
        finally:
            conn.close()
