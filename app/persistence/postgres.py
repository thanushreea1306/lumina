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
"""

# Migrations that a fresh schema already includes; recorded as applied so the
# tracking table is consistent and an import from an older SQLite DB can run
# the same guards.
_FRESH_MIGRATIONS = [
    "transcripts.batch_id",
    "incidents.owner_device_id",
]


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

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        conn = self._connect()
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM incidents WHERE incident_id = %s", (incident_id,))
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
                        "SELECT incident_id, created_at, updated_at, status, priority "
                        "FROM incidents WHERE owner_device_id = %s "
                        "ORDER BY updated_at DESC LIMIT %s",
                        (owner_device_id, max(1, min(int(limit), 500))),
                    )
                else:
                    cur.execute(
                        "SELECT incident_id, created_at, updated_at, status, priority "
                        "FROM incidents ORDER BY updated_at DESC LIMIT %s",
                        (max(1, min(int(limit), 500)),),
                    )
                return list(cur.fetchall())
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
