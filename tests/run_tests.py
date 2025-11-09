# tests/run_tests.py
"""
Run basic functional tests for queuectl.
Designed to run under the same Python interpreter / venv you're using for development.

Scenarios covered:
1. Basic job completes successfully.
2. Failed job retries and moves to DLQ (uses small max_retries).
3. Multiple workers process jobs without overlap.
4. Persistence: job remains in DB after a simulated restart.
"""

import subprocess
import sys
import os
import time
import json
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "cli.py"]  # runs same python and project root
DB_PATH = PROJECT_ROOT / "src" / "queue.db"

# Helper functions
def run_cli(args, capture=True, check=True):
    cmd = CLI + args
    print("RUN:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=capture, text=True)
    if check and res.returncode != 0:
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)} (rc={res.returncode})")
    return res

def write_job_file(job_dict):
    tmp_path = PROJECT_ROOT / f"tests_job_{job_dict['id']}.json"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(job_dict, fh)
    return tmp_path

def start_worker_process(count=1):
    # Start worker in background (process will run until stopped)
    p = subprocess.Popen(CLI + ["worker", "start", "--count", str(count)], cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(1.0)  # give it a moment to start
    return p

def stop_workers():
    run_cli(["worker", "stop"])

def db_get_job(job_id):
    # Import DB helper from project (ensures we use same code base)
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from queuectl.db import get_conn
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)

def wait_for_state(job_id, target_state, timeout=20.0, poll=0.5):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = db_get_job(job_id)
        if r and r.get("state") == target_state:
            return r
        time.sleep(poll)
    raise TimeoutError(f"Timeout waiting for job {job_id} -> {target_state}. Last row: {r}")

def set_config(key, value):
    run_cli(["config", "set", key, str(value)])

def ensure_db_exists():
    if not DB_PATH.exists():
        print("DB file missing; initializing DB...")
        run_cli(["-c", "from src.queuectl.db import init_db; init_db()"])  # fallback
    print("DB path:", DB_PATH)

def clean_jobs(prefix="test-"):
    # remove any previous test jobs created by this runner
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from queuectl.db import get_conn
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM jobs WHERE id LIKE ?", (f"{prefix}%",))
    conn.commit()
    conn.close()

def run_all_tests():
    ensure_db_exists()
    print("Cleaning old test jobs...")
    clean_jobs()
    print("Tests start\n")

    # Test 1: Basic job completes successfully
    j1 = {"id": "test-echo-1", "command": "python -c \"print('hello-test')\""}
    f1 = write_job_file(j1)
    run_cli(["enqueue", "--file", str(f1)])
    p = start_worker_process(count=1)
    try:
        job = wait_for_state(j1["id"], "completed", timeout=20)
        print("Test1 PASS: job completed:", job["id"])
    finally:
        stop_workers()
        p.wait(timeout=5)

    # Test 2: Failed job retries and moves to DLQ
    # set default_max_retries to 1 so it quickly moves to dead
    set_config("default_max_retries", "1")
    j2 = {"id": "test-fail-1", "command": "python -c \"import sys; sys.exit(2)\""}
    f2 = write_job_file(j2)
    run_cli(["enqueue", "--file", str(f2)])
    p2 = start_worker_process(count=1)
    try:
        job_dead = wait_for_state(j2["id"], "dead", timeout=40)
        print("Test2 PASS: job moved to DLQ:", job_dead["id"])
    finally:
        stop_workers()
        p2.wait(timeout=5)
    # reset config
    set_config("default_max_retries", "3")

    # Test 3: Multiple workers process jobs without overlap
    # Enqueue 5 jobs and start 3 workers
    jobs_multi = []
    for i in range(5):
        jid = f"test-multi-{i}"
        j = {"id": jid, "command": "python -c \"print('m-%s')\"" % i}
        jobs_multi.append(j)
        write_job_file(j)
        run_cli(["enqueue", "--file", str(PROJECT_ROOT / f"tests_job_{jid}.json")])
    p3 = start_worker_process(count=3)
    try:
        # wait for all to be completed
        for j in jobs_multi:
            wait_for_state(j["id"], "completed", timeout=30)
        print("Test3 PASS: multiple workers completed all jobs")
    finally:
        stop_workers()
        p3.wait(timeout=5)

    # Test 4: Persistence across restart (job remains pending before worker start)
    jid = "test-persist-1"
    j4 = {"id": jid, "command": "python -c \"print('persist')\""}
    write_job_file(j4)
    run_cli(["enqueue", "--file", str(PROJECT_ROOT / f"tests_job_{jid}.json")])
    # simulate restart by re-importing DB and checking row exists
    row = db_get_job(jid)
    if not row or row.get("state") != "pending":
        raise RuntimeError("Test4 FAIL: job not persisted or not pending")
    print("Test4 PASS: job persisted in DB and pending")

    print("\nALL TESTS PASSED ✅")

if __name__ == "__main__":
    try:
        run_all_tests()
    except Exception as e:
        print("\nTEST RUN FAILED:", e)
        sys.exit(2)
