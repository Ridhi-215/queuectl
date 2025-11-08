# src/queuectl/worker.py
"""
Worker logic for queuectl.

Each worker process runs run_worker(worker_id), which:
 - claims a pending job atomically
 - executes the job command
 - updates job state (completed / retry with backoff / dead)
 - checks the shared "workers:stop" config to exit gracefully
"""

import os
import sqlite3
import time
import subprocess
from datetime import datetime, timezone, timedelta
import traceback
import multiprocessing as mp

from .db import get_conn, get_config, set_config

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _now():
    return datetime.now(timezone.utc)


def _now_iso():
    return _now().strftime(ISO_FMT)


def _iso_after_seconds(seconds: float):
    dt = _now() + timedelta(seconds=seconds)
    return dt.strftime(ISO_FMT)


def _get_backoff_base() -> int:
    v = get_config("backoff_base", "2")
    try:
        return int(v)
    except Exception:
        return 2


def _should_stop():
    """Return True if a stop has been requested (via config key 'workers:stop' == '1')."""
    v = get_config("workers:stop", "0")
    return str(v) == "1"


def claim_job(conn, worker_id: str):
    """
    Atomically claim the next available pending job and set it to processing.
    Returns the claimed job row as a sqlite3.Row or None if no job.
    """
    now_iso = _now_iso()
    cur = conn.cursor()

    # SQLite trick: use UPDATE ... WHERE id = (SELECT id FROM ... LIMIT 1)
    # to atomically claim a row. Use available_at <= now or NULL.
    # We also ensure state='pending'
    sql = """
    UPDATE jobs
    SET state = 'processing', locked_by = ?, updated_at = ?
    WHERE id = (
        SELECT id FROM jobs
        WHERE state = 'pending' AND (available_at IS NULL OR available_at <= ?)
        ORDER BY created_at ASC
        LIMIT 1
    )
    AND state = 'pending'
    ;
    """
    cur.execute(sql, (worker_id, now_iso, now_iso))
    conn.commit()

    if cur.rowcount == 0:
        return None

    # fetch the claimed job to return details
    cur.execute("SELECT * FROM jobs WHERE locked_by = ? AND state = 'processing' ORDER BY updated_at DESC LIMIT 1;", (worker_id,))
    row = cur.fetchone()
    return row


def execute_command(command: str, timeout: int = None):
    """
    Execute the given shell command. Return (returncode, stdout, stderr).
    Uses subprocess.run with shell=True for convenience (documented trade-off).
    """
    try:
        completed = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        return completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as e:
        return -1, "", f"TimeoutExpired: {e}"
    except Exception as e:
        return -1, "", f"ExecutionError: {e}"


def process_job_row(conn, row, worker_id: str):
    """
    Handle the job execution and DB updates for the given job row.
    """
    job_id = row["id"]
    command = row["command"]
    attempts = int(row["attempts"])
    max_retries = int(row["max_retries"])

    # Get configured timeout (seconds) — None means no timeout
    timeout = _get_job_timeout()

    try:
        # Run the command with optional timeout
        rc, out, err = execute_command(command, timeout=timeout)
        now_iso = _now_iso()
        cur = conn.cursor()


        if rc == 0:
            # Success
            cur.execute(
                "UPDATE jobs SET state = 'completed', updated_at = ?, last_error = NULL, stdout = ?, stderr = ? WHERE id = ?;",
                (now_iso, out, err, job_id),
            )
            conn.commit()
            return {"job_id": job_id, "result": "completed", "rc": rc, "stdout": out}
        else:
            # Failure: increment attempts
            attempts += 1
            if attempts > max_retries:
                # Move to dead (DLQ)
                cur.execute(
                    "UPDATE jobs SET state = 'dead', attempts = ?, updated_at = ?, last_error = ?, stdout = ?, stderr = ? WHERE id = ?;",
                    (attempts, now_iso, f"exitcode={rc}; stderr={err}", out, err, job_id),
                )
                conn.commit()
                return {"job_id": job_id, "result": "dead", "rc": rc, "stderr": err}
            else:
                # Schedule retry with exponential backoff
                base = _get_backoff_base()
                # delay seconds = base ** attempts
                try:
                    delay = float(base) ** float(attempts)
                except Exception:
                    delay = float(base) ** float(attempts)
                available_at = _iso_after_seconds(delay)
                cur.execute(
                    """
                    UPDATE jobs
                    SET state = 'pending', attempts = ?, available_at = ?, updated_at = ?, last_error = ?, stdout = ?, stderr = ?
                    WHERE id = ?;
                    """,
                    (attempts, available_at, now_iso, f"exitcode={rc}; stderr={err}", out, err, job_id),
                )
                conn.commit()
                return {"job_id": job_id, "result": "retry_scheduled", "rc": rc, "delay": delay}
    except Exception as e:
        # On unexpected exceptions while processing, mark job as failed with last_error and leave it retryable.
        now_iso = _now_iso()
        cur = conn.cursor()
        cur.execute(
            "UPDATE jobs SET state = 'failed', updated_at = ?, last_error = ? WHERE id = ?;",
            (now_iso, f"processor-exception: {e}\n{traceback.format_exc()}", job_id),
        )
        conn.commit()
        return {"job_id": job_id, "result": "processor_exception"}


def run_worker(worker_id: str, poll_interval: float = 1.0):
    """
    Worker loop to be run in a separate process.
    Checks for the stop flag in config and exits gracefully when set.
    """
    # Each worker opens its own DB connection
    conn = get_conn()
    try:
        while True:
            # Check for global stop
            if _should_stop():
                print(f"[{worker_id}] stop requested; exiting")
                break

            row = claim_job(conn, worker_id)
            if row is None:
                # nothing to do; sleep and continue
                time.sleep(poll_interval)
                continue

            # We have a job; process it
            print(f"[{worker_id}] claimed job {row['id']} (cmd: {row['command']})")
            res = process_job_row(conn, row, worker_id)
            print(f"[{worker_id}] result: {res}")

            # continue looping
    except KeyboardInterrupt:
        print(f"[{worker_id}] KeyboardInterrupt received; exiting")
    except Exception as e:
        print(f"[{worker_id}] unexpected error: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def start_worker_processes(count: int):
    """
    Helper to launch `count` worker processes and wait for them.
    This is intended to be called from the CLI command 'worker start'.
    """
    # Clear stop flag so workers run
    set_config("workers:stop", "0")

    procs = []
    for i in range(count):
        wid = f"worker-{os.getpid()}-{i}"
        p = mp.Process(target=run_worker, args=(wid,))
        p.start()
        print(f"Started worker process pid={p.pid} id={wid}")
        procs.append(p)

    try:
        # Wait for children; allow KeyboardInterrupt to stop them
        while any(p.is_alive() for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Main: KeyboardInterrupt -> requesting workers to stop")
        set_config("workers:stop", "1")
    finally:
        # Ensure child processes terminate
        for p in procs:
            if p.is_alive():
                p.join(timeout=5)
                if p.is_alive():
                    print(f"Terminating worker pid={p.pid}")
                    p.terminate()
                    p.join()

def _get_job_timeout():
    """Return job timeout in seconds (int) or None (0 means no timeout)."""
    v = get_config("job_timeout_seconds", "0")
    try:
        t = int(v)
        if t <= 0:
            return None
        return t
    except Exception:
        return None
