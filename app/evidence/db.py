# app/evidence/db.py
"""Append-only persistence for sessions, events, evidence, decisions, outcomes.

Scope:
  - sessions
  - events (timeline)
  - evidence / observations
  - decisions
  - outcomes

Deliberately does NOT store: raw audio, conversation transcripts, SMS content,
social-media content, or unnecessary sensitive fields. The evidence table stores
typed values only (the same values that exist in the in-memory model).
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from app.evidence.models import (
    Evidence,
    EvidenceSource,
    EvidenceStatus,
    Session,
    TimelineEvent,
    TimelineEventType,
)

DB_PATH = os.path.join("data", "evidence.db")

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


class EvidenceStore:
    """Append-only store for the evidence foundation.

    All writes are inserts. There are no UPDATE paths in this phase, preserving
    the append-only evidence philosophy.
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
            conn.executescript(_SCHEMA)
        conn.close()

    # ---- writes (append-only) ----

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

    # ---- reads ----

    def get_session(self, session_id: str) -> Optional[Session]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
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

    # ---- Device authentication ----

    def register_device(self, device_id: str, device_secret_hash: str) -> None:
        """Register a new device with a hashed secret."""
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO devices (device_id, device_secret_hash, created_at) "
                "VALUES (?, ?, ?)",
                (device_id, device_secret_hash, datetime.now().isoformat()),
            )
        conn.close()

    def get_device_secret(self, device_id: str) -> Optional[str]:
        """Retrieve the secret for a device. Returns None if not found."""
        conn = self._connect()
        row = conn.execute(
            "SELECT device_secret_hash FROM devices WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return row["device_secret_hash"]

    def bind_session_to_device(self, device_id: str, session_id: str) -> None:
        """Bind a session to a device for ownership verification."""
        conn = self._connect()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO device_sessions (device_id, session_id, created_at) "
                "VALUES (?, ?, ?)",
                (device_id, session_id, datetime.now().isoformat()),
            )
        conn.close()

    def get_session_owner(self, session_id: str) -> Optional[str]:
        """Get the device_id that owns a session. Returns None if unbound."""
        conn = self._connect()
        row = conn.execute(
            "SELECT device_id FROM device_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return row["device_id"]

    def device_exists(self, device_id: str) -> bool:
        """Check if a device is registered."""
        conn = self._connect()
        row = conn.execute(
            "SELECT 1 FROM devices WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        conn.close()
        return row is not None

    def list_sessions(self, limit: int = 50) -> List[Dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT session_id, started_at FROM sessions ORDER BY started_at DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


def make_session() -> Session:
    """Create a new empty Session with a fresh id and timestamp."""
    return Session(
        session_id=uuid.uuid4().hex,
        started_at=datetime.now().isoformat(),
    )