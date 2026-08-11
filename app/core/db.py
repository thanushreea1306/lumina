# app/core/db.py
import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

DB_PATH = os.path.join("data", "incidents.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            risk_score REAL NOT NULL,
            risk_level TEXT NOT NULL,
            detected_signals TEXT,
            explanation TEXT,
            alert_status TEXT,
            mode TEXT NOT NULL DEFAULT 'demo'
        )
        """
    )
    conn.commit()
    conn.close()


def log_incident(
    risk_score: float,
    risk_level: str,
    detected_signals: Optional[Dict] = None,
    explanation: Optional[str] = None,
    alert_status: Optional[str] = None,
    mode: str = "demo",
) -> int:
    """Insert a record and return the new incident id."""
    init_db()
    conn = _connect()
    cur = conn.execute(
        """
        INSERT INTO incidents
            (timestamp, risk_score, risk_level, detected_signals, explanation, alert_status, mode)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().isoformat(),
            float(risk_score),
            str(risk_level),
            json.dumps(detected_signals, default=str) if detected_signals else None,
            explanation,
            alert_status,
            mode,
        ),
    )
    conn.commit()
    incident_id = int(cur.lastrowid)
    conn.close()
    return incident_id


def get_incidents(limit: int = 50) -> List[Dict]:
    """Return the most recent incidents, newest first."""
    limit = max(1, min(int(limit), 500))
    init_db()
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    incidents = []
    for row in rows:
        record = dict(row)
        raw = record.get("detected_signals")
        if raw:
            try:
                record["detected_signals"] = json.loads(raw)
            except (ValueError, TypeError):
                record["detected_signals"] = None
        incidents.append(record)
    return incidents
