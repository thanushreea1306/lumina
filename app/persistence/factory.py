# app/persistence/factory.py
"""Backend selection for LUMINA persistence.

Environment controls:
  LUMINA_DB_BACKEND  = sqlite (default) | postgres
  LUMINA_DB_PATH     = SQLite file path (default data/evidence.db)
  DATABASE_URL       = PostgreSQL connection string (postgres backend)

Rules:
  - A concrete SQLite ``path`` argument (tests, local dev) always selects the
    SQLite backend regardless of LUMINA_DB_BACKEND.
  - With no explicit path and LUMINA_DB_BACKEND=postgres, a PostgreSQL backend
    is built from DATABASE_URL / LUMINA_DB_URL. If neither URL is configured the
    backend refuses to construct (no silent fallback to SQLite in production).
  - Default (no path, no backend override): SQLite at LUMINA_DB_PATH.
"""
from __future__ import annotations

import os
from typing import Optional

from app.persistence.base import PersistenceBackend

_BACKEND_ENV = "LUMINA_DB_BACKEND"


def get_backend(  # type: ignore[return]
    path: Optional[str] = None,
    dsn: Optional[str] = None,
) -> PersistenceBackend:
    backend = (os.getenv(_BACKEND_ENV) or "sqlite").strip().lower()

    if path is not None:
        # An explicit SQLite path always forces SQLite (dev / tests).
        from app.persistence.sqlite import SQLiteBackend

        return SQLiteBackend(path)

    if backend in ("postgres", "postgresql", "supabase", "pg"):
        from app.persistence.postgres import PostgresBackend

        return PostgresBackend(dsn)

    # Explicit "sqlite" (or anything unknown) with no path -> SQLite.
    from app.persistence.sqlite import SQLiteBackend

    return SQLiteBackend()
