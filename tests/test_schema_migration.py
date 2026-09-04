# tests/test_schema_migration.py
"""CP-09: Non-destructive, versioned, idempotent schema migration.

Regression test covering the CP-08 finding that a live/default database could
carry a `transcripts` table lacking `batch_id`. A real store initialization
must upgrade the schema in place without destroying existing data.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.evidence.schema import applied_migrations
from app.incident.store import IncidentStore


def _older_transcripts_schema(conn: sqlite3.Connection) -> None:
    """Create a legacy transcripts table WITHOUT batch_id (pre-CP-08 shape)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS transcripts (
            transcript_id TEXT PRIMARY KEY,
            incident_id TEXT NOT NULL,
            source TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            segments_json TEXT,
            provenance_json TEXT
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
            confidence REAL
        );
        """
    )


def _seed_older_data(conn: sqlite3.Connection) -> None:
    """Insert representative legacy transcript rows into the older schema."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO transcripts "
        "(transcript_id, incident_id, source, text, created_at, segments_json, provenance_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "legacy-t1",
            "inc-1",
            "USER_TYPED",
            "Give me your OTP",
            now,
            None,
            None,
        ),
    )
    conn.execute(
        "INSERT INTO transcripts "
        "(transcript_id, incident_id, source, text, created_at, segments_json, provenance_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "legacy-t2",
            "inc-1",
            "USER_TYPED",
            "I shared the code",
            now,
            None,
            None,
        ),
    )
    conn.commit()


def _cols(conn: sqlite3.Connection, table: str):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def test_legacy_db_without_batch_id_is_migrated_data_preserved(tmp_path):
    db_path = str(tmp_path / "legacy.db")

    # 1. Build an older-schema database missing batch_id and seed it.
    conn = sqlite3.connect(db_path)
    _older_transcripts_schema(conn)
    _seed_older_data(conn)
    conn.close()

    # 2. Run the normal store initialization / migration.
    store = IncidentStore(db_path)

    # 3. batch_id now exists in the runtime schema.
    check = sqlite3.connect(db_path)
    check.row_factory = sqlite3.Row
    assert "batch_id" in _cols(check, "transcripts")

    # 4. Old transcript data remains.
    old_rows = check.execute(
        "SELECT transcript_id FROM transcripts ORDER BY transcript_id"
    ).fetchall()
    assert [r["transcript_id"] for r in old_rows] == ["legacy-t1", "legacy-t2"]

    # 5. A new transcript WITH batch_id can be written.
    conn2 = sqlite3.connect(db_path)
    conn2.row_factory = sqlite3.Row
    conn2.execute(
        "INSERT INTO transcripts "
        "(transcript_id, incident_id, source, text, created_at, segments_json, provenance_json, batch_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("new-t3", "inc-1", "USER_TYPED", "The bank called", "2026-01-01T00:00:00Z",
         None, None, "batch-99"),
    )
    conn2.commit()
    new_row = conn2.execute(
        "SELECT batch_id FROM transcripts WHERE transcript_id = 'new-t3'"
    ).fetchone()
    assert new_row["batch_id"] == "batch-99"
    conn2.close()

    # 6. Reopen the database (fresh store) and confirm everything remains.
    reopened = IncidentStore(db_path)
    reopened_conn = sqlite3.connect(db_path)
    reopened_conn.row_factory = sqlite3.Row
    all_rows = reopened_conn.execute(
        "SELECT transcript_id, batch_id FROM transcripts ORDER BY transcript_id"
    ).fetchall()
    ids = [r["transcript_id"] for r in all_rows]
    assert ids == ["legacy-t1", "legacy-t2", "new-t3"]
    assert reopened_conn.execute(
        "SELECT batch_id FROM transcripts WHERE transcript_id='legacy-t1'"
    ).fetchone()["batch_id"] is None  # legacy rows keep NULL batch_id, not dropped
    reopened_conn.close()


def test_migration_is_idempotent_across_reopens(tmp_path):
    db_path = str(tmp_path / "idem.db")
    conn = sqlite3.connect(db_path)
    _older_transcripts_schema(conn)
    _seed_older_data(conn)
    conn.close()

    first = IncidentStore(db_path)
    check1 = sqlite3.connect(db_path)
    check1.row_factory = sqlite3.Row
    before = applied_migrations(check1)
    check1.close()

    # Re-running the store init must not repeat destructive work nor duplicate rows.
    second = IncidentStore(db_path)
    check2 = sqlite3.connect(db_path)
    check2.row_factory = sqlite3.Row
    after = applied_migrations(check2)
    rows = check2.execute(
        "SELECT COUNT(*) AS n FROM transcripts"
    ).fetchone()["n"]
    assert rows == 2  # seed rows only; migration added no rows
    check2.close()

    assert set(after) >= set(before)
    # Migration names recorded exactly once (no duplicate application).
    dup = check2_dups(db_path, "transcripts.batch_id")
    assert dup == 1
    # batch_id column present, migration recorded but not re-added.
    opened = sqlite3.connect(db_path)
    opened.row_factory = sqlite3.Row
    assert "batch_id" in _cols(opened, "transcripts")
    opened.close()


def check2_dups(db_path: str, name: str) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM schema_migrations WHERE name = ?", (name,)
    ).fetchone()["n"]
    conn.close()
    return n
