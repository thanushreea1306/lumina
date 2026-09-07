# app/incident/engine.py
"""Incident engine: the main facade for incident operations.

Combines:
  - Incident models (domain)
  - State calculation (deterministic rules)
  - Persistence (SQLite)

The engine is the single entry point for:
  - Creating incidents
  - Adding evidence (observations)
  - Recording user actions
  - Retrieving incident state
  - Getting next recommended action

It NEVER:
  - Produces numeric risk scores
  - Fabricates conclusions
  - Claims caller identity
  - Converts UNKNOWN to FACT
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from app.evidence.models import UserObservationType
from app.incident.models import (
    EpistemicStatus,
    ExposureCategory,
    Incident,
    IncidentStatus,
    Priority,
    RecommendedAction,
    TimelineEntryType,
    UserAction,
    UserActionType,
)
from app.incident.state import recalculate_incident
from app.incident.store import IncidentStore
from app.persistence.base import TransactionCtx
from app.incident.transcript import (
    Transcript,
    TranscriptSource,
    TextEvidenceExtractor,
    ExtractionResult,
)
from app.incident.transcript_provider import (
    TranscriptBatch,
    TranscriptSegment,
)


class IncidentEngine:
    """The incident intelligence engine.

    Facade over models, state calculation, and persistence.
    All mutation goes through this engine to ensure consistency.
    """

    def __init__(self, store: Optional[IncidentStore] = None):
        self.store = store or IncidentStore()

    def create_incident(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        owner_device_id: Optional[str] = None,
    ) -> Incident:
        """Create a new incident.

        Optionally links to an existing session for backward compatibility.
        owner_device_id is derived from the authenticated request identity and
        persisted with the incident (never trusted from client input).
        """
        incident = Incident(metadata=metadata or {}, owner_device_id=owner_device_id)
        if session_id:
            incident.session_ids.append(session_id)

        # Record creation in timeline
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.INCIDENT_CREATED,
            summary="Incident created",
            epistemic_status=EpistemicStatus.FACT,
        )

        # Persist atomically in a single transaction.
        with self.store.transaction() as conn:
            self.store.create_incident(incident, conn=conn)
            self._save_timeline_entries(incident, start=0, conn=conn)

        return incident

    def add_observation(
        self,
        incident_id: str,
        observation_type: UserObservationType,
        notes: Optional[str] = None,
    ) -> Incident:
        """Add an observation to an incident.

        This represents what the user reported experiencing.
        It is always USER-CONFIRMED (the user explicitly reported it).
        After adding, the incident state is recalculated.
        """
        incident = self._get_incident(incident_id)
        start = len(incident.timeline)

        # Add timeline entry
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.EVIDENCE_ADDED,
            summary=f"User reported: {observation_type.value}",
            epistemic_status=EpistemicStatus.FACT,
            metadata={
                "observation_type": observation_type.value,
                "notes": notes,
                "source": "USER",
            },
        )

        # Recalculate state (may append STATE_CHANGED entries) and persist the
        # entire logical mutation atomically in a single transaction.
        with self.store.transaction() as conn:
            recalculate_incident(incident)
            self._save_timeline_entries(incident, start=start, conn=conn)
            self._save_incident_state(incident, conn=conn)

        return incident

    def record_user_action(
        self,
        incident_id: str,
        action_type: UserActionType,
        description: str,
    ) -> Incident:
        """Record that the user confirmed performing an action.

        Only created by explicit user confirmation.
        NEVER automatically created from a request observation.
        """
        incident = self._get_incident(incident_id)
        start = len(incident.timeline)

        sequence = len(incident.user_actions)
        action = UserAction(
            action_type=action_type,
            description=description,
            timestamp=datetime.now(timezone.utc).isoformat(),
            sequence=sequence,
        )
        incident.user_actions.append(action)

        # Add timeline entry
        incident.add_timeline_entry(
            entry_type=TimelineEntryType.USER_ACTION_RECORDED,
            summary=f"User confirmed: {description}",
            epistemic_status=EpistemicStatus.FACT,
            metadata={
                "action_type": action_type.value,
                "action_id": action.action_id,
            },
        )

        # Recalculate state (may append STATE_CHANGED entries) and persist the
        # whole mutation atomically.
        with self.store.transaction() as conn:
            self.store.add_user_action(incident_id, action, conn=conn)
            recalculate_incident(incident)
            self._save_timeline_entries(incident, start=start, conn=conn)
            self._save_incident_state(incident, conn=conn)

        return incident

    def close_incident(
        self,
        incident_id: str,
        reason: Optional[str] = None,
    ) -> Incident:
        """Server-side incident closure (archive).

        Sets the incident status to CLOSED, appends an append-only
        INCIDENT_CLOSED timeline entry, and refreshes updated_at. Closing is
        explicit and authenticated; automatic heuristics never close an
        incident. Closing never deletes evidence, timeline, exposure, or
        user actions — a closed incident remains readable for history.

        A closed incident stays CLOSED: later state recalculation preserves
        the closed status (reopening is deliberately not supported).
        """
        incident = self._get_incident(incident_id)

        if incident.status == IncidentStatus.CLOSED:
            return incident

        incident.status = IncidentStatus.CLOSED
        summary = "Incident closed"
        metadata: Dict = {"source": "OWNER"}
        if reason and reason.strip():
            # A short, optional, non-personal closure note from the owner.
            metadata["reason"] = reason.strip()

        entry = incident.add_timeline_entry(
            entry_type=TimelineEntryType.INCIDENT_CLOSED,
            summary=summary,
            epistemic_status=EpistemicStatus.FACT,
            metadata=metadata,
        )
        incident.updated_at = entry.timestamp

# Persist status and the append-only closure entry atomically.
        with self.store.transaction() as conn:
            # Refresh the recovery snapshot so the record reflects the closed
            # status honestly ("record kept for your files", never "all safe").
            from app.incident.recovery import set_recovery_snapshot
            set_recovery_snapshot(incident)
            self.store.update_incident(incident, conn=conn)
            self.store.append_timeline_entry(incident_id, entry, conn=conn)

        return incident

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Retrieve an incident with all its state."""
        return self.store.get_incident(incident_id)

    def add_transcript(
        self,
        incident_id: str,
        text: str,
        source: TranscriptSource = TranscriptSource.USER_TYPED,
        batch_id: Optional[str] = None,
    ) -> Tuple[Incident, ExtractionResult]:
        """Add a transcript to an incident and extract evidence.

        Flow:
          1. Create and persist the transcript
          2. Extract observations and user actions from text
          3. Add extracted observations as timeline events
          4. Add extracted user actions
          5. Recalculate incident state
          6. Return updated incident + extraction result

        The transcript is always persisted. The extraction result
        records exactly what was found and why.

        If batch_id is provided and has already been processed,
        the existing result is returned without reprocessing (idempotency).
        """
        incident = self._get_incident(incident_id)
        start = len(incident.timeline)

        # Idempotency check
        if batch_id and self.store.has_batch(batch_id):
            # Return existing state without reprocessing
            recalculate_incident(incident)
            return incident, ExtractionResult(
                transcript_id="",
                observations=[],
                user_actions=[],
                raw_text=text,
            )

        # 1. Create transcript
        transcript = Transcript(
            incident_id=incident_id,
            source=source,
            text=text,
            batch_id=batch_id,
        )

        # 2. Extract evidence (pure, in-memory)
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)

        # 3-6. Persist the ENTIRE logical mutation (transcript, segments,
        # extractions, timeline, incident state) atomically in ONE transaction.
        # If any write fails, nothing is committed — no partial transcript /
        # extraction / timeline / state is left behind.
        with self.store.transaction() as conn:
            self.store.save_transcript(transcript, conn=conn)
            self.store.save_extraction_result(incident_id, result, conn=conn)

            # 4. Add extracted observations as timeline events
            for obs in result.observations:
                incident.add_timeline_entry(
                    entry_type=TimelineEntryType.EVIDENCE_ADDED,
                    summary=f"Transcript evidence: {obs.observation_type.value}",
                    epistemic_status=EpistemicStatus.FACT,
                    metadata={
                        "observation_type": obs.observation_type.value,
                        "source": "TRANSCRIPT",
                        "transcript_id": transcript.transcript_id,
                        "text_span": obs.text_span,
                        "extraction_method": obs.extraction_method,
                        "epistemic_note": obs.epistemic_note,
                        "confidence_in_extraction": obs.confidence_in_extraction,
                    },
                )

            # 5. Record extracted first-person claims as UNCONFIRMED evidence.
            #
            # SAFETY RULE: transcript claim != explicit user confirmation.
            # A first-person phrase ("I shared the OTP") is a candidate claim, NOT
            # proof the user performed the action. It must NEVER automatically
            # create a confirmed UserAction (which would force
            # USER_CONFIRMED_EXPOSED and RECOVERING). Only the explicit
            # confirmation endpoint (record_user_action) may create a confirmed
            # UserAction.
            for action in result.user_actions:
                incident.add_timeline_entry(
                    entry_type=TimelineEntryType.EVIDENCE_ADDED,
                    summary=f"User may have acted: {action.description} (needs confirmation)",
                    epistemic_status=EpistemicStatus.INFERENCE,
                    metadata={
                        "source": "TRANSCRIPT_CLAIM",
                        "claimed_action_type": action.action_type,
                        "claimed_description": action.description,
                        "confirmed": False,
                        "needs_confirmation": True,
                        "transcript_id": transcript.transcript_id,
                        "text_span": action.text_span,
                        "extraction_method": action.extraction_method,
                    },
                )

            # 6. Recalculate incident state
            recalculate_incident(incident)
            self._save_timeline_entries(incident, start=start, conn=conn)
            self._save_incident_state(incident, conn=conn)

        return incident, result

    def add_transcript_batch(
        self,
        incident_id: str,
        batch: TranscriptBatch,
    ) -> Tuple[Incident, ExtractionResult]:
        """Add a batch of transcript segments to an incident.

        This is the segment-aware version of add_transcript.
        Supports:
          - Multiple segments in one batch
          - Speaker metadata on segments
          - Incremental processing (segments added later)
          - Idempotency (same batch_id not processed twice)

        Flow:
          1. Idempotency check (by batch_id)
          2. Create transcript with segments
          3. Extract evidence using speaker metadata
          4. Persist segments and extraction results
          5. Add timeline events
          6. Recalculate incident state
        """
        incident = self._get_incident(incident_id)
        start = len(incident.timeline)

        # 1. Idempotency check
        if batch.batch_id and self.store.has_batch(batch.batch_id):
            recalculate_incident(incident)
            return incident, ExtractionResult(
                transcript_id="",
                observations=[],
                user_actions=[],
                raw_text=batch.full_text,
            )

        # 2. Create transcript with segments
        try:
            source = TranscriptSource(batch.source)
        except ValueError:
            source = TranscriptSource.USER_TYPED

        transcript = Transcript(
            incident_id=incident_id,
            source=source,
            text=batch.full_text,
            segments=list(batch.segments),
            batch_id=batch.batch_id,
        )

        # 3. Extract evidence using speaker metadata (pure, in-memory)
        extractor = TextEvidenceExtractor()
        result = extractor.extract(transcript)

        # 4-7. Persist the ENTIRE logical batch mutation atomically in ONE
        # transaction so a failure never leaves partial batch state.
        with self.store.transaction() as conn:
            self.store.save_transcript(transcript, conn=conn)
            # Also save segments individually for retrieval
            if batch.segments:
                self.store.save_segments_batch(
                    incident_id, transcript.transcript_id, batch.segments, conn=conn
                )
            # Persist extraction results
            self.store.save_extraction_result(incident_id, result, conn=conn)

            # 5. Add timeline events for extracted observations
            for obs in result.observations:
                incident.add_timeline_entry(
                    entry_type=TimelineEntryType.EVIDENCE_ADDED,
                    summary=f"Transcript evidence: {obs.observation_type.value}",
                    epistemic_status=EpistemicStatus.FACT,
                    metadata={
                        "observation_type": obs.observation_type.value,
                        "source": "TRANSCRIPT",
                        "transcript_id": transcript.transcript_id,
                        "text_span": obs.text_span,
                        "extraction_method": obs.extraction_method,
                        "epistemic_note": obs.epistemic_note,
                        "confidence_in_extraction": obs.confidence_in_extraction,
                    },
                )

            # 6. Record extracted first-person claims as UNCONFIRMED evidence.
            #
            # SAFETY RULE: transcript claim != explicit user confirmation.
            # See add_transcript for the rationale. Claims are persisted as
            # INFERENCE timeline entries and never create confirmed UserActions.
            for action in result.user_actions:
                incident.add_timeline_entry(
                    entry_type=TimelineEntryType.EVIDENCE_ADDED,
                    summary=f"User may have acted: {action.description} (needs confirmation)",
                    epistemic_status=EpistemicStatus.INFERENCE,
                    metadata={
                        "source": "TRANSCRIPT_CLAIM",
                        "claimed_action_type": action.action_type,
                        "claimed_description": action.description,
                        "confirmed": False,
                        "needs_confirmation": True,
                        "transcript_id": transcript.transcript_id,
                        "text_span": action.text_span,
                        "extraction_method": action.extraction_method,
                    },
                )

            # 7. Recalculate incident state
            recalculate_incident(incident)
            self._save_timeline_entries(incident, start=start, conn=conn)
            self._save_incident_state(incident, conn=conn)

        return incident, result

    def get_next_action(self, incident_id: str) -> Optional[RecommendedAction]:
        """Get the single most important next action for the user."""
        incident = self.store.get_incident(incident_id)
        if incident is None:
            return None
        return incident.next_action

    def list_incidents(
        self, limit: int = 50, owner_device_id: Optional[str] = None
    ) -> List[Dict]:
        """List recent incidents, optionally scoped to an owner device."""
        return self.store.list_incidents(limit, owner_device_id=owner_device_id)

    # ---- Internal helpers ----

    def _get_incident(self, incident_id: str) -> Incident:
        incident = self.store.get_incident(incident_id)
        if incident is None:
            raise ValueError(f"Incident not found: {incident_id}")
        return incident

    def _save_timeline_entries(
        self, incident: Incident, start: int = 0,
        conn: Optional[TransactionCtx] = None,
    ) -> None:
        """Save new timeline entries to the store (optionally in a transaction)."""
        for entry in incident.timeline[start:]:
            self.store.append_timeline_entry(incident.incident_id, entry, conn=conn)

    def _save_incident_state(
        self, incident: Incident, conn: Optional[TransactionCtx] = None,
    ) -> None:
        """Save updated incident state and exposure to the store."""
        self.store.update_incident(incident, conn=conn)
        self.store.upsert_exposure_batch(incident.incident_id, incident.exposure, conn=conn)

