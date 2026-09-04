# tests/test_transaction_rollback.py
"""CP-09: Logical incident mutations are atomic (all-or-nothing).

If any write inside a logical mutation fails, the ENTIRE mutation rolls back —
no partial transcript, extraction, timeline, or incident-state is left behind.

Failure is injected by monkeypatching a store write method (the LAST write in
the transaction) to raise. SQLite's single-connection transaction (via
IncidentStore.transaction) must undo every earlier write.
"""
from __future__ import annotations

import sqlite3

import pytest

from app.incident.engine import IncidentEngine
from app.incident.store import IncidentStore


@pytest.fixture
def store(tmp_path):
    return IncidentStore(str(tmp_path / "tx.db"))


@pytest.fixture
def engine(store):
    return IncidentEngine(store)


def _counts(store: IncidentStore) -> dict:
    conn = sqlite3.connect(store.path)
    counts = {
        "transcripts": conn.execute(
            "SELECT COUNT(*) FROM transcripts"
        ).fetchone()[0],
        "extractions": conn.execute(
            "SELECT COUNT(*) FROM transcript_extractions"
        ).fetchone()[0],
        "segments": conn.execute(
            "SELECT COUNT(*) FROM transcript_segments"
        ).fetchone()[0],
        "timeline": conn.execute(
            "SELECT COUNT(*) FROM incident_timeline"
        ).fetchone()[0],
        "incidents": conn.execute(
            "SELECT COUNT(*) FROM incidents"
        ).fetchone()[0],
    }
    conn.close()
    return counts


def test_add_transcript_failure_rolls_back_everything(engine, store, monkeypatch):
    inc = engine.create_incident(owner_device_id="owner-1")
    before = _counts(store)

    # Inject a failure on the LAST write in the add_transcript transaction.
    def boom(incident_id, exposure, conn=None):
        raise RuntimeError("injected failure after transcript saved")

    monkeypatch.setattr(store, "upsert_exposure_batch", boom)

    with pytest.raises(RuntimeError):
        engine.add_transcript(
            inc.incident_id, "They demanded my OTP right now", batch_id="req-123"
        )

    # Every table must be unchanged: full rollback, no partial state.
    assert _counts(store) == before
    assert store.has_batch("req-123") is False  # transcript not committed


def test_add_transcript_batch_failure_rolls_back_everything(engine, store, monkeypatch):
    from app.incident.transcript_provider import TranscriptSegment, TranscriptBatch

    inc = engine.create_incident(owner_device_id="owner-1")
    before = _counts(store)

    segments = [TranscriptSegment(text="Give me the code now", speaker="caller")]
    batch = TranscriptBatch(
        batch_id="batch-xyz", segments=segments, source="USER_TYPED"
    )

    def boom(incident_id, exposure, conn=None):
        raise RuntimeError("injected failure during batch commit")

    monkeypatch.setattr(store, "upsert_exposure_batch", boom)

    with pytest.raises(RuntimeError):
        engine.add_transcript_batch(inc.incident_id, batch)

    assert _counts(store) == before
    assert store.has_batch("batch-xyz") is False


def test_retry_after_rollback_commits_on_second_try(engine, store, monkeypatch):
    inc = engine.create_incident(owner_device_id="owner-1")

    calls = {"n": 0}

    def flaky(incident_id, exposure, conn=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient failure")
        return None

    monkeypatch.setattr(store, "upsert_exposure_batch", flaky)

    with pytest.raises(RuntimeError):
        engine.add_transcript(
            inc.incident_id, "They demanded my OTP right now", batch_id="req-456"
        )

    # No partial state after the failed attempt.
    assert store.has_batch("req-456") is False

    # A retry with the same batch_id now succeeds and persists fully.
    result_engine = IncidentEngine(store)
    result_engine.add_transcript(
        inc.incident_id, "They demanded my OTP right now", batch_id="req-456"
    )
    assert store.has_batch("req-456") is True
