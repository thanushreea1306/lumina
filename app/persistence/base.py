# app/persistence/base.py
"""Database-agnostic persistence backend abstraction.

LUMINA's single source of truth is a unified set of tables shared by the
incident path and the evidence foundation:

  Device/auth tables:
    devices, device_sessions
  Evidence foundation tables:
    sessions, events, evidence, decisions, outcomes
  Incident tables:
    incidents, incident_timeline, incident_actions, incident_exposure,
    transcripts, transcript_segments, transcript_extractions

A concrete backend (SQLite or PostgreSQL/Supabase) implements every method
below. The rest of the application talks only to this interface, keeping the
domain logic and API contracts independent of the underlying database.

Semantics preserved across every backend:
  - append-only timeline / actions / transcript / extraction / evidence
  - idempotent inserts (no-ops on duplicate unique keys)
  - transactional logical mutations (one transaction per engine mutation)
  - non-destructive, versioned schema migrations
  - owner-scoped reads / no silent fallback to another database
"""
from __future__ import annotations

import contextlib
from typing import Any, ContextManager, Dict, Iterator, List, Optional, Protocol

from app.incident.models import (
    ExposureCategory,
    ExposureState,
    Incident,
    TimelineEntry,
    UserAction,
)
from app.incident.transcript import ExtractionResult, Transcript
from app.evidence.models import Evidence, Session, TimelineEvent


class TransactionCtx:
    """An opaque transaction handle yielded by ``backend.transaction()``.

    Concrete backends carry the underlying (sqlite3 / psycopg) connection
    internally. Callers pass this token to write methods so that all writes of
    one logical mutation share one transaction (commit / atomic rollback).
    """

    __slots__ = ("_connection",)

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    @property
    def connection(self) -> Any:
        return self._connection

    def execute(self, sql: str, params: Optional[tuple] = None) -> Any:
        """Run SQL on the underlying connection (backend-specific return)."""
        raise NotImplementedError

    def executemany(self, sql: str, params: List[tuple]) -> Any:
        raise NotImplementedError

    def fetchall(self, **kwargs) -> List[Dict[str, Any]]:
        raise NotImplementedError


class PersistenceBackend:
    """Abstract persistence backend. Concrete impls: SQLiteBackend, PostgresBackend."""

    # ---- lifecycle ----

    def close(self) -> None:
        raise NotImplementedError

    # ---- transactions ----

    @contextlib.contextmanager
    def transaction(self) -> Iterator[TransactionCtx]:
        """Open a backend transaction. Yields a TransactionCtx token.

        On normal exit the transaction commits; on exception it rolls back.
        """
        raise NotImplementedError

    @contextlib.contextmanager
    def _write_scope(self, txn: Optional[TransactionCtx]) -> Iterator[TransactionCtx]:
        """Reuse `txn` if supplied, otherwise open a standalone write scope."""
        if txn is not None:
            yield txn
            return
        with self.transaction() as t:
            yield t

    # ---- migrations ----

    def migrate(self) -> None:
        """Run idempotent, non-destructive schema migrations."""
        raise NotImplementedError

    # ---- device auth ----

    def register_device(self, device_id: str, device_secret_hash: str) -> None:
        raise NotImplementedError

    def get_device_secret(self, device_id: str) -> Optional[str]:
        raise NotImplementedError

    def device_exists(self, device_id: str) -> bool:
        raise NotImplementedError

    def bind_session_to_device(self, device_id: str, session_id: str) -> None:
        raise NotImplementedError

    def get_session_owner(self, session_id: str) -> Optional[str]:
        raise NotImplementedError

    # ---- evidence foundation ----

    def create_session(self, session_id: str, started_at: str) -> None:
        raise NotImplementedError

    def append_event(self, event: TimelineEvent) -> None:
        raise NotImplementedError

    def add_evidence(self, evidence: Evidence) -> None:
        raise NotImplementedError

    def record_decision(self, session_id: str, decision: Dict) -> None:
        raise NotImplementedError

    def record_outcome(self, session_id: str, outcome: str) -> None:
        raise NotImplementedError

    def get_session(self, session_id: str) -> Optional[Session]:
        raise NotImplementedError

    def get_latest_decision(self, session_id: str) -> Optional[Dict]:
        raise NotImplementedError

    def get_outcomes(self, session_id: str) -> List[str]:
        raise NotImplementedError

    def list_sessions(self, limit: int = 50) -> List[Dict]:
        raise NotImplementedError

    # ---- incident writes ----

    def create_incident(self, incident: Incident, txn: Optional[TransactionCtx] = None) -> None:
        raise NotImplementedError

    def update_incident(self, incident: Incident, txn: Optional[TransactionCtx] = None) -> None:
        raise NotImplementedError

    def append_timeline_entry(
        self, incident_id: str, entry: TimelineEntry, txn: Optional[TransactionCtx] = None
    ) -> None:
        raise NotImplementedError

    def add_user_action(
        self, incident_id: str, action: UserAction, txn: Optional[TransactionCtx] = None
    ) -> None:
        raise NotImplementedError

    def upsert_exposure(
        self, incident_id: str, state: ExposureState, txn: Optional[TransactionCtx] = None
    ) -> None:
        raise NotImplementedError

    def upsert_exposure_batch(
        self,
        incident_id: str,
        exposure: Dict[ExposureCategory, ExposureState],
        txn: Optional[TransactionCtx] = None,
    ) -> None:
        raise NotImplementedError

    def save_transcript(self, transcript: Transcript, txn: Optional[TransactionCtx] = None) -> None:
        raise NotImplementedError

    def save_segments_batch(
        self,
        incident_id: str,
        transcript_id: str,
        segments: List,
        txn: Optional[TransactionCtx] = None,
    ) -> None:
        raise NotImplementedError

    def save_extraction_result(
        self, incident_id: str, result: ExtractionResult, txn: Optional[TransactionCtx] = None
    ) -> None:
        raise NotImplementedError

    # ---- incident reads ----

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        raise NotImplementedError

    def list_incidents(
        self, limit: int = 50, owner_device_id: Optional[str] = None
    ) -> List[Dict]:
        raise NotImplementedError

    def has_batch(self, batch_id: str) -> bool:
        raise NotImplementedError

    def get_segments(self, incident_id: str) -> List[Dict]:
        raise NotImplementedError

    def get_transcripts(self, incident_id: str) -> List[Dict]:
        raise NotImplementedError

    def get_extractions(self, incident_id: str) -> List[Dict]:
        raise NotImplementedError

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
        raise NotImplementedError

    def get_trusted_contact(self, owner_device_id: str) -> Optional[Dict]:
        raise NotImplementedError

    def get_trusted_contact_by_id(self, contact_id: str) -> Optional[Dict]:
        raise NotImplementedError

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
        raise NotImplementedError

    def get_help_request_for_incident(self, incident_id: str) -> Optional[Dict]:
        raise NotImplementedError

    def update_help_request_status(
        self,
        request_id: str,
        status: str,
        failure_reason: Optional[str] = None,
        txn: Optional[TransactionCtx] = None,
    ) -> Optional[Dict]:
        raise NotImplementedError

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
        raise NotImplementedError

    def get_help_policy(self, owner_device_id: str) -> Optional[Dict]:
        raise NotImplementedError
