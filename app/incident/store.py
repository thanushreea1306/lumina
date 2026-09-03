# app/incident/store.py
"""Incident persistence layer.

Uses the same SQLite infrastructure as the evidence store.
Minimal new tables — no broad database redesign.

Tables:
  - incidents: core incident record
  - incident_timeline: append-only timeline entries
  - incident_actions: user-confirmed actions
  - incident_exposure: exposure state per category

Preserves append-only semantics for timeline and actions.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.evidence.db import DB_PATH
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
from app.incident.transcript import Transcript, TranscriptSource, ExtractionResult

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
"""


class IncidentStore:
    """SQLite-backed store for incidents.

    Uses the same database file as the evidence store.
    All writes are inserts or targeted updates (exposure state can change).
    Timeline and actions are append-only.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = path or DB_PATH
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        conn = self._connect()
        with conn:
            conn.executescript(_INCIDENT_SCHEMA)
            conn.executescript(_TRANSCRIPT_SCHEMA)
        conn.close()

    # ---- Write: incident ----

    def create_incident(self, incident: Incident) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO incidents "
                "(incident_id, created_at, updated_at, status, priority, "
                "next_action_json, unknowns_json, session_ids_json, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    incident.incident_id,
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
        conn.close()

    def update_incident(self, incident: Incident) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
                "UPDATE incidents SET "
                "updated_at = ?, status = ?, priority = ?, "
                "next_action_json = ?, unknowns_json = ?, session_ids_json = ?, metadata_json = ? "
                "WHERE incident_id = ?",
                (
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
        conn.close()

    # ---- Write: timeline (append-only) ----

    def append_timeline_entry(self, incident_id: str, entry: TimelineEntry) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
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
        conn.close()

    # ---- Write: user actions (append-only) ----

    def add_user_action(self, incident_id: str, action: UserAction) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
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
        conn.close()

    # ---- Write: exposure ----

    def upsert_exposure(self, incident_id: str, state: ExposureState) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
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
        conn.close()

    def upsert_exposure_batch(
        self, incident_id: str, exposure: Dict[ExposureCategory, ExposureState]
    ) -> None:
        conn = self._connect()
        with conn:
            for category, state in exposure.items():
                conn.execute(
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
        conn.close()

    # ---- Read: incident ----

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?",
            (incident_id,),
        ).fetchone()
        if row is None:
            conn.close()
            return None

        incident = Incident(
            incident_id=row["incident_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status=IncidentStatus(row["status"]),
            priority=Priority(row["priority"]),
            session_ids=json.loads(row["session_ids_json"] or "[]"),
            metadata=json.loads(row["metadata_json"] or "{}"),
            unknowns=json.loads(row["unknowns_json"] or "[]"),
        )

        # Load next_action
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

        # Load timeline
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

        # Load actions
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

        # Load exposure
        for erow in conn.execute(
            "SELECT * FROM incident_exposure WHERE incident_id = ?",
            (incident_id,),
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

    def list_incidents(self, limit: int = 50) -> List[Dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT incident_id, created_at, updated_at, status, priority "
            "FROM incidents ORDER BY updated_at DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ---- Transcript persistence ----

    def save_transcript(self, transcript: Transcript) -> None:
        conn = self._connect()
        with conn:
            conn.execute(
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
            # Save segments individually for idempotency
            for segment in transcript.segments:
                conn.execute(
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
        conn.close()

    def has_batch(self, batch_id: str) -> bool:
        """Check if a batch has already been processed (idempotency)."""
        if not batch_id:
            return False
        conn = self._connect()
        row = conn.execute(
            "SELECT 1 FROM transcripts WHERE batch_id = ? LIMIT 1",
            (batch_id,),
        ).fetchone()
        conn.close()
        return row is not None

    def get_segments(self, incident_id: str) -> List[Dict]:
        """Get all segments for an incident, ordered by creation time."""
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM transcript_segments WHERE incident_id = ? ORDER BY created_at, id",
            (incident_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def save_segments_batch(
        self, incident_id: str, transcript_id: str, segments: List
    ) -> None:
        """Save multiple segments at once. Idempotent by segment_id."""
        conn = self._connect()
        with conn:
            for segment in segments:
                conn.execute(
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
        conn.close()

    def save_extraction_result(
        self, incident_id: str, result: ExtractionResult
    ) -> None:
        conn = self._connect()
        with conn:
            for obs in result.observations:
                conn.execute(
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
                conn.execute(
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
        conn.close()

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
            "SELECT * FROM transcript_extractions WHERE incident_id = ?",
            (incident_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
