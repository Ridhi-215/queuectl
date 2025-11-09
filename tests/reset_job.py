import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from src.queuectl.db import get_conn
from datetime import datetime, timezone

conn = get_conn()
cur = conn.cursor()
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

cur.execute("""
    UPDATE jobs
    SET state='pending',
        attempts=0,
        available_at=?,
        updated_at=?,
        last_error=NULL,
        stdout=NULL,
        stderr=NULL
    WHERE id = 'job1'
""", (now, now))

conn.commit()

cur.execute("SELECT id, state, attempts, last_error, stdout, stderr, available_at, updated_at FROM jobs WHERE id='job1'")
print(dict(cur.fetchone()))

conn.close()
