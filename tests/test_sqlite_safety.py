# tests/test_sqlite_safety.py
"""CP-09: SQLite production-safety pragmas.

Verifies connect_db applies explicit, production-safe connection settings
(timeout, busy_timeout, foreign_keys, and WAL where possible) without breaking
the single-process architecture or existing behavior.
"""
from __future__ import annotations

import sqlite3

from app.evidence.db import connect_db


def test_connect_db_sets_foreign_keys_and_busy_timeout(tmp_path):
    db_path = str(tmp_path / "safety.db")
    with connect_db(db_path) as conn:
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert fk == 1          # foreign_keys ON
        assert busy == 30000    # busy_timeout set
        assert timeout == 30000


def test_connect_db_wal_on_real_file(tmp_path):
    db_path = str(tmp_path / "wal.db")
    with connect_db(db_path) as conn:
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    # WAL is deliberately enabled for single-process file-backed stores.
    assert journal.lower() == "wal"


def test_connect_db_uses_declared_row_factory(tmp_path):
    db_path = str(tmp_path / "rows.db")
    con = connect_db(db_path)
    try:
        con.execute("CREATE TABLE t (a INTEGER)")
        con.execute("INSERT INTO t (a) VALUES (42)")
        row = con.execute("SELECT a FROM t").fetchone()
        assert row["a"] == 42  # sqlite3.Row
    finally:
        con.close()
