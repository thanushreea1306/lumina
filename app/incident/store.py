# app/incident/store.py
"""Incident persistence facade.

This is a thin, database-agnostic facade over :class:`PersistenceBackend`. It
preserves the historical ``IncidentStore`` public API (constructor with an
optional SQLite ``path``, ``.path``, ``transaction()``, and write methods that
accept an optional ``conn`` transaction token) so the incident engine and tests
keep working unchanged while the actual database can be SQLite (local/dev) or
PostgreSQL/Supabase (production) via ``LUMINA_DB_BACKEND``.
"""
from __future__ import annotations

import contextlib
from typing import Dict, Iterator, List, Optional

from app.incident.models import (
    ExposureCategory,
    ExposureState,
    Incident,
    TimelineEntry,
    UserAction,
)
from app.incident.transcript import ExtractionResult, Transcript
from app.persistence.base import PersistenceBackend, TransactionCtx
from app.persistence.factory import get_backend


class IncidentStore:
    """Database-agnostic facade for incident persistence."""

    def __init__(self, path: Optional[str] = None):
        self.backend: PersistenceBackend = get_backend(path)
        self.path = path  # SQLite file path when the backend is sqlite (dev/tests)

    # ---- backend delegation ----

    @contextlib.contextmanager
    def transaction(self) -> Iterator[TransactionCtx]:
        """Open a backend transaction. Yields a TransactionCtx token."""
        with self.backend.transaction() as t:
            yield t

    # ---- incident writes ----

    def create_incident(self, incident: Incident, conn: Optional[TransactionCtx] = None) -> None:
        self.backend.create_incident(incident, txn=conn)

    def update_incident(self, incident: Incident, conn: Optional[TransactionCtx] = None) -> None:
        self.backend.update_incident(incident, txn=conn)

    def append_timeline_entry(
        self, incident_id: str, entry: TimelineEntry, conn: Optional[TransactionCtx] = None
    ) -> None:
        self.backend.append_timeline_entry(incident_id, entry, txn=conn)

    def add_user_action(
        self, incident_id: str, action: UserAction, conn: Optional[TransactionCtx] = None
    ) -> None:
        self.backend.add_user_action(incident_id, action, txn=conn)

    def upsert_exposure(
        self, incident_id: str, state: ExposureState, conn: Optional[TransactionCtx] = None
    ) -> None:
        self.backend.upsert_exposure(incident_id, state, txn=conn)

    def upsert_exposure_batch(
        self,
        incident_id: str,
        exposure: Dict[ExposureCategory, ExposureState],
        conn: Optional[TransactionCtx] = None,
    ) -> None:
        self.backend.upsert_exposure_batch(incident_id, exposure, txn=conn)

    def save_transcript(
        self, transcript: Transcript, conn: Optional[TransactionCtx] = None
    ) -> None:
        self.backend.save_transcript(transcript, txn=conn)

    def save_segments_batch(
        self,
        incident_id: str,
        transcript_id: str,
        segments: List,
        conn: Optional[TransactionCtx] = None,
    ) -> None:
        self.backend.save_segments_batch(incident_id, transcript_id, segments, txn=conn)

    def save_extraction_result(
        self, incident_id: str, result: ExtractionResult, conn: Optional[TransactionCtx] = None
    ) -> None:
        self.backend.save_extraction_result(incident_id, result, txn=conn)

    # ---- incident reads ----

    def get_incident(
        self, incident_id: str, owner_device_id: Optional[str] = None
    ) -> Optional[Incident]:
        return self.backend.get_incident(incident_id, owner_device_id=owner_device_id)

    def list_incidents(
        self, limit: int = 50, owner_device_id: Optional[str] = None
    ) -> List[Dict]:
        return self.backend.list_incidents(limit, owner_device_id=owner_device_id)

    def has_batch(self, batch_id: str) -> bool:
        return self.backend.has_batch(batch_id)

    def get_segments(self, incident_id: str) -> List[Dict]:
        return self.backend.get_segments(incident_id)

    def get_transcripts(self, incident_id: str) -> List[Dict]:
        return self.backend.get_transcripts(incident_id)

    def get_extractions(self, incident_id: str) -> List[Dict]:
        return self.backend.get_extractions(incident_id)

    def close(self) -> None:
        self.backend.close()
