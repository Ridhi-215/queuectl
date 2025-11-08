# src/queuectl/manager.py
"""
Queue manager: validation and operations for jobs.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from .db import get_conn, get_config


ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _now_iso():
    return datetime.now(timezone.utc).strftime(ISO_FMT)


def _get_default_max_retries() -> int:
    v = get_config("default_max_retries", "3")
    try:
        return int(v)
    except Exception:
        return 3


def validate_job_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate incoming job dict and return the normalized job dict ready for DB insertion.
    Required fields:
      - id
      - command
    Optional:
      - max_retries
    Normalized/added fields:
      - state (pending)
      - attempts (0)
      - created_at, updated_at (ISO UTC)
      - available_at (same as created_at)
    """
    if not isinstance(d, dict):
        raise ValueError("job must be a JSON object")

    if "id" not in d or not isinstance(d["id"], str) or not d["id"].strip():
        raise ValueError("job must contain a non-empty string 'id' field")

    if "command" not in d or not isinstance(d["command"], str) or not d["command"].strip():
        raise ValueError("job must contain a non-empty string 'command' field")

    job_id = d["id"].strip()
    command = d["command"].strip()

    # max_retries: try to use provided, else default
    max_retries = d.get("max_retries")
    if max_retries is None:
        max_retries = _get_default_max_retries()
    else:
        try:
            max_retries = int(max_retries)
            if max_retries < 0:
                raise ValueError()
        except Exception:
            raise ValueError("max_retries must be a non-negative integer")

    now = _now_iso()

    normalized = {
        "id": job_id,
        "command": command,
        "state": "pending",
        "attempts": 0,
        "max_retries": int(max_retries),
        "created_at": now,
        "updated_at": now,
        "available_at": now,
        "locked_by": None,
        "last_error": None,
    }
    return normalized


def enqueue_job(job_json_str: str) -> Dict[str, Any]:
    """
    Accept a JSON string or JSON-like dict and insert a normalized job into the DB.
    Returns the job dict inserted.
    Raises ValueError on validation errors, sqlite3.IntegrityError on duplicate id, etc.
    """
    # Parse JSON string (or accept a JSON-like dict string)
    if isinstance(job_json_str, str):
        try:
            parsed = json.loads(job_json_str)
        except json.JSONDecodeError as e:
            # helpful error for Windows quoting issues
            raise ValueError(f"Invalid JSON: {e.msg}. Make sure to use proper quotes in PowerShell.")
    elif isinstance(job_json_str, dict):
        parsed = job_json_str
    else:
        raise ValueError("job input must be a JSON string or a dict")

    job = validate_job_dict(parsed)

    # Insert into DB
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO jobs (id, command, state, attempts, max_retries, created_at, updated_at, available_at, locked_by, last_error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["id"],
                job["command"],
                job["state"],
                job["attempts"],
                job["max_retries"],
                job["created_at"],
                job["updated_at"],
                job["available_at"],
                job["locked_by"],
                job["last_error"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return job



def _row_to_dict(row):
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}

def list_jobs(state: str = None, limit: int = 100):
    """
    Return a list of job dicts optionally filtered by state.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        if state:
            cur.execute("SELECT * FROM jobs WHERE state = ? ORDER BY created_at ASC LIMIT ?", (state, limit))
        else:
            cur.execute("SELECT * FROM jobs ORDER BY created_at ASC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()

def status_summary():
    """
    Return counts per state and a small summary dict.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT state, COUNT(*) as cnt FROM jobs GROUP BY state;")
        rows = cur.fetchall()
        counts = {r["state"]: r["cnt"] for r in rows}
        # ensure keys exist
        for s in ("pending", "processing", "completed", "failed", "dead"):
            counts.setdefault(s, 0)

        # workers:stop flag
        stop_flag = get_config("workers:stop", "0")
        summary = {
            "counts": counts,
            "workers_stop_flag": str(stop_flag),
        }
        return summary
    finally:
        conn.close()

def dlq_list(limit: int = 100):
    """
    Return list of dead jobs (DLQ).
    """
    return list_jobs(state="dead", limit=limit)

def dlq_retry(job_id: str):
    """
    Retry a dead job: reset attempts to 0, set state to pending, available_at = now.
    Returns the updated job dict or raises if job not found or not dead.
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Job '{job_id}' not found")
        if row["state"] != "dead":
            raise ValueError(f"Job '{job_id}' is not in DLQ (state={row['state']})")

        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        cur.execute(
            "UPDATE jobs SET state = 'pending', attempts = 0, available_at = ?, updated_at = ?, last_error = NULL WHERE id = ?;",
            (now, now, job_id),
        )
        conn.commit()
        cur.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,))
        updated = cur.fetchone()
        return _row_to_dict(updated)
    finally:
        conn.close()
