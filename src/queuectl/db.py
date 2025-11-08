# src/queuectl/db.py
"""
Database helpers and migration for queuectl.

Creates an SQLite DB (src/queue.db) and initializes required tables:
- config
- jobs
- workers

Provides a small API to get connections and run migrations.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import json

# DB file path: src/queue.db
BASE_DIR = Path(__file__).resolve().parents[1]  # src/
DB_PATH = BASE_DIR / "queue.db"

# Default config values we will seed (if not present)
DEFAULT_CONFIG = {
    "backoff_base": "2",            # base for exponential backoff (string stored)
    "default_max_retries": "3",     # default max_retries for jobs (string stored)
    "job_timeout_seconds": "0"      # default job timeout (0 => no timeout)
}



def get_conn():
    """Return a sqlite3 connection to the DB with sensible settings."""
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    # Return rows as dict-like objects
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_pragmas(conn):
    """Set pragmas to improve concurrency and safety."""
    cur = conn.cursor()
    # Use Write-Ahead Log for better concurrency
    cur.execute("PRAGMA journal_mode = WAL;")
    # Foreign keys if we add relations later
    cur.execute("PRAGMA foreign_keys = ON;")
    conn.commit()

def _ensure_columns(conn):
    """Ensure stdout/stderr columns exist in jobs table (migration helper)."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(jobs);")
    cols = [r["name"] for r in cur.fetchall()]
    # Add stdout column if missing
    if "stdout" not in cols:
        cur.execute("ALTER TABLE jobs ADD COLUMN stdout TEXT;")
    if "stderr" not in cols:
        cur.execute("ALTER TABLE jobs ADD COLUMN stderr TEXT;")
    conn.commit()


def init_db():
    """Create DB file and tables if they don't exist. Seed default config values."""
    # Ensure directory exists (BASE_DIR should exist)
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    # Connect (this will create the DB file if it doesn't exist)
    conn = get_conn()
    try:
        _ensure_pragmas(conn)
        cur = conn.cursor()

        # Create config table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        # Create jobs table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                state TEXT NOT NULL,                 -- pending, processing, completed, failed, dead
                attempts INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                available_at TEXT,                   -- next time job is eligible to be picked (ISO string)
                locked_by TEXT,                      -- worker id or pid that claimed the job
                last_error TEXT
            );
            """
        )

        # Create simple index to help querying next pending jobs
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_state_available ON jobs (state, available_at);"
        )

        # Ensure stdout/stderr columns exist (migration)
        _ensure_columns(conn)

        # Create workers table (to track active workers if needed)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS workers (
                worker_id TEXT PRIMARY KEY,
                pid INTEGER,
                started_at TEXT,
                last_heartbeat TEXT
            );
            """
        )

        conn.commit()

        # Seed default config entries (only if missing)
        for k, v in DEFAULT_CONFIG.items():
            cur.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?);", (k, v))
        conn.commit()

    finally:
        conn.close()


def get_config(key, default=None):
    """Return config value for key or default if missing."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM config WHERE key = ?;", (key,))
        row = cur.fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_config(key, value):
    """Set or update a config value."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO config(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value;", (key, str(value)))
        conn.commit()
    finally:
        conn.close()


def db_path_str():
    """Return DB path as string (useful for debugging)."""
    return str(DB_PATH)


if __name__ == "__main__":
    init_db()
    print("Initialized DB at", DB_PATH)
    # Print seeded config for quick verification
    print("Seeded config:")
    for k in DEFAULT_CONFIG.keys():
        print(f"  {k} = {get_config(k)}")
