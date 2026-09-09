# app/evidence/schema.py
"""Versioned, idempotent, non-destructive SQLite schema migrations.

Both EvidenceStore and IncidentStore share a single SQLite database file in
production (LUMINA_DB_PATH). This module centralizes schema maintenance so an
existing database from an older checkpoint is upgraded safely in place:

  - Existing tables are NEVER dropped.
  - Existing rows are NEVER deleted.
  - Missing columns / tables are added with ALTER/CREATE ... IF NOT EXISTS.
  - Each migration runs at most once (tracked in schema_migrations), so
    restarting the application never repeats (or double-applies) work.
  - Fresh databases create the full current schema directly.
"""
from __future__ import annotations

import sqlite3
from typing import Callable, Dict, List, Optional

# Ordered list of migrations. Each entry: (name, apply(conn)).
# `name` is the unique idempotency key recorded in schema_migrations.
# `apply` receives an open connection and must be safe and non-destructive.
_MIGRATIONS: List = []


def _migration(name: str, check: Callable[[sqlite3.Connection], bool],
               apply: Callable[[sqlite3.Connection], None]) -> None:
    """Register a migration guarded by a schema-check function.

    The migration is applied only if `check(conn)` returns True AND the
    migration has not already been recorded in schema_migrations.
    """
    _MIGRATIONS.append((name, check, apply))


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    if not _table_exists(conn, table):
        # Table is created later by the CREATE TABLE IF NOT EXISTS schema
        # scripts (which already include the current columns); nothing to
        # migrate for a missing table.
        return True
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    return column in cols


def _column_exists(table: str, column: str) -> Callable[[sqlite3.Connection], bool]:
    return lambda conn: not _has_column(conn, table, column)


_migration(
    "transcripts.batch_id",
    _column_exists("transcripts", "batch_id"),
    lambda conn: conn.execute("ALTER TABLE transcripts ADD COLUMN batch_id TEXT"),
)

_migration(
    "incidents.owner_device_id",
    _column_exists("incidents", "owner_device_id"),
    lambda conn: conn.execute("ALTER TABLE incidents ADD COLUMN owner_device_id TEXT"),
)

_migration(
    "identity.lumina_phone_verifications.device_id",
    _column_exists("lumina_phone_verifications", "device_id"),
    lambda conn: conn.execute(
        "ALTER TABLE lumina_phone_verifications ADD COLUMN device_id TEXT"
    ),
)

_migration(
    "identity.lumina_users.account_status",
    _column_exists("lumina_users", "account_status"),
    lambda conn: conn.execute(
        "ALTER TABLE lumina_users ADD COLUMN "
        "account_status TEXT NOT NULL DEFAULT 'ACTIVE'"
    ),
)


def _needs_used_nonces_table(conn: sqlite3.Connection) -> bool:
    return not _table_exists(conn, "used_nonces")


def _create_used_nonces_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS used_nonces ("
        "  device_id TEXT NOT NULL,"
        "  nonce TEXT NOT NULL,"
        "  used_at TEXT NOT NULL,"
        "  PRIMARY KEY (device_id, nonce)"
        ")"
    )


_migration(
    "auth.used_nonces_table",
    _needs_used_nonces_table,
    _create_used_nonces_table,
)


def _needs_phone_unique_index(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, "lumina_users"):
        return False
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' "
        "AND name='idx_lumina_users_phone_unique'"
    ).fetchone()
    return row is None


def _dedupe_lumina_users_by_phone(conn: sqlite3.Connection) -> None:
    """Drop duplicate lumina_users rows per phone, keeping the newest account.

    Only rows sharing a phone_number are touched; unique phones and rows with
    an empty phone are never candidates. The dedupe is idempotent, so it can
    safely run again on a fresh database.
    """
    conn.execute(
        """
        DELETE FROM lumina_users
        WHERE phone_number <> ''
          AND user_id NOT IN (
            SELECT user_id FROM (
              SELECT user_id,
                     ROW_NUMBER() OVER (
                       PARTITION BY phone_number
                       ORDER BY updated_at DESC, created_at DESC
                     ) AS rn
              FROM lumina_users
            )
            WHERE rn = 1
          )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_lumina_users_phone_unique "
        "ON lumina_users (phone_number)"
    )


_migration(
    "identity.lumina_users.phone_number_unique",
    _needs_phone_unique_index,
    _dedupe_lumina_users_by_phone,
)


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "  name TEXT PRIMARY KEY,"
        "  applied_at TEXT NOT NULL"
        ")"
    )


def run_migrations(conn: sqlite3.Connection) -> None:
    """Apply pending migrations idempotently within a single transaction.

    Safe to call multiple times and from multiple processes (the PRIMARY KEY
    on schema_migrations makes re-application a no-op).
    """
    from datetime import datetime, timezone

    _ensure_migrations_table(conn)
    applied = {
        r["name"]
        for r in conn.execute("SELECT name FROM schema_migrations").fetchall()
    }
    now = datetime.now(timezone.utc).isoformat()
    for name, check, apply in _MIGRATIONS:
        if name in applied:
            continue
        with conn:  # transaction boundary for each migration
            if check(conn):
                apply(conn)
            try:
                conn.execute(
                    "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                    (name, now),
                )
            except sqlite3.IntegrityError:
                # Another process applied it concurrently; treat as done.
                pass


def applied_migrations(conn: sqlite3.Connection) -> List[str]:
    """Return the list of already-applied migration names (for diagnostics)."""
    _ensure_migrations_table(conn)
    rows = conn.execute("SELECT name FROM schema_migrations ORDER BY name").fetchall()
    return [r["name"] for r in rows]
