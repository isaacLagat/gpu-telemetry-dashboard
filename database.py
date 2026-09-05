"""
SQLite persistence for GPU telemetry readings and alerts.

Schema:
  readings   — one row per GPU per sampling tick
  alerts     — one row per anomaly detected against a reading
"""

import sqlite3
import time
from contextlib import contextmanager

DB_PATH = "telemetry.db"


def init_db(path: str = DB_PATH) -> None:
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gpu_id TEXT NOT NULL,
                gpu_model TEXT NOT NULL,
                temp_c REAL NOT NULL,
                power_w REAL NOT NULL,
                fan_pct REAL NOT NULL,
                timestamp REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gpu_id TEXT NOT NULL,
                severity TEXT NOT NULL,       -- 'warn' or 'critical'
                reason TEXT NOT NULL,
                temp_c REAL,
                power_w REAL,
                fan_pct REAL,
                timestamp REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_readings_gpu_time
                ON readings (gpu_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_alerts_time
                ON alerts (timestamp);
            """
        )


@contextmanager
def _connect(path: str = DB_PATH):
    conn = sqlite3.connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_reading(gpu_id: str, gpu_model: str, temp_c: float, power_w: float,
                    fan_pct: float, path: str = DB_PATH) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO readings (gpu_id, gpu_model, temp_c, power_w, fan_pct, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (gpu_id, gpu_model, temp_c, power_w, fan_pct, time.time()),
        )


def insert_alert(gpu_id: str, severity: str, reason: str, temp_c: float,
                  power_w: float, fan_pct: float, path: str = DB_PATH) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO alerts (gpu_id, severity, reason, temp_c, power_w, fan_pct, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (gpu_id, severity, reason, temp_c, power_w, fan_pct, time.time()),
        )


def latest_readings(path: str = DB_PATH) -> list[dict]:
    """One most-recent row per gpu_id."""
    with _connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT r.* FROM readings r
            INNER JOIN (
                SELECT gpu_id, MAX(timestamp) AS max_ts
                FROM readings GROUP BY gpu_id
            ) latest
            ON r.gpu_id = latest.gpu_id AND r.timestamp = latest.max_ts
            ORDER BY r.gpu_id
            """
        ).fetchall()
        return [dict(row) for row in rows]


def history(gpu_id: str, since_seconds: float = 300, path: str = DB_PATH) -> list[dict]:
    cutoff = time.time() - since_seconds
    with _connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM readings WHERE gpu_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
            (gpu_id, cutoff),
        ).fetchall()
        return [dict(row) for row in rows]


def recent_alerts(limit: int = 50, path: str = DB_PATH) -> list[dict]:
    with _connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
