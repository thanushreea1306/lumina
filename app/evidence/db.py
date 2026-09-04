# app/evidence/db.py
"""Evidence persistence facade.

Thin, database-agnostic facade over :class:`PersistenceBackend` that preserves
the historical ``EvidenceStore`` public API (constructor with an optional
SQLite ``path``) plus the module helpers ``DB_PATH``, ``connect_db`` and
``make_session``. The actual database can be SQLite (local/dev) or
PostgreSQL/Supabase (production) via ``LUMINA_DB_BACKEND``.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from app.evidence.models import Evidence, Session, TimelineEvent
from app.persistence.base import PersistenceBackend
from app.persistence.factory import get_backend
from app.persistence.sqlite import DB_PATH, connect_db  # re-exported for compat

__all__ = ["DB_PATH", "connect_db", "EvidenceStore", "make_session"]


def make_session() -> Session:
    """Create a new empty Session with a fresh id and timestamp."""
    return Session(
        session_id=uuid.uuid4().hex,
        started_at=datetime.now().isoformat(),
    )


class EvidenceStore:
    """Database-agnostic facade for evidence + device-auth persistence."""

    def __init__(self, path: Optional[str] = None):
        self.backend: PersistenceBackend = get_backend(path)
        self.path = path  # SQLite file path when the backend is sqlite (dev/tests)

    # ---- device auth ----

    def register_device(self, device_id: str, device_secret_hash: str) -> None:
        self.backend.register_device(device_id, device_secret_hash)

    def get_device_secret(self, device_id: str) -> Optional[str]:
        return self.backend.get_device_secret(device_id)

    def device_exists(self, device_id: str) -> bool:
        return self.backend.device_exists(device_id)

    def bind_session_to_device(self, device_id: str, session_id: str) -> None:
        self.backend.bind_session_to_device(device_id, session_id)

    def get_session_owner(self, session_id: str) -> Optional[str]:
        return self.backend.get_session_owner(session_id)

    # ---- evidence foundation ----

    def create_session(self, session_id: str, started_at: str) -> None:
        self.backend.create_session(session_id, started_at)

    def append_event(self, event: TimelineEvent) -> None:
        self.backend.append_event(event)

    def add_evidence(self, evidence: Evidence) -> None:
        self.backend.add_evidence(evidence)

    def record_decision(self, session_id: str, decision: Dict) -> None:
        self.backend.record_decision(session_id, decision)

    def record_outcome(self, session_id: str, outcome: str) -> None:
        self.backend.record_outcome(session_id, outcome)

    def get_session(self, session_id: str) -> Optional[Session]:
        return self.backend.get_session(session_id)

    def get_latest_decision(self, session_id: str) -> Optional[Dict]:
        return self.backend.get_latest_decision(session_id)

    def get_outcomes(self, session_id: str) -> List[str]:
        return self.backend.get_outcomes(session_id)

    def list_sessions(self, limit: int = 50) -> List[Dict]:
        return self.backend.list_sessions(limit)

    def close(self) -> None:
        self.backend.close()
