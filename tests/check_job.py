import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from src.queuectl.db import get_conn

conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT id, command, state, attempts, max_retries, created_at, updated_at, last_error, stdout, stderr FROM jobs WHERE id='job1'")
r = cur.fetchone()
print("job1 row:")
print(dict(r) if r else "not found")
conn.close()
