# job1.py (migration helper) — optional; save and run only if needed
import sqlite3, os
db_path = os.path.join("src","queue.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("PRAGMA table_info(jobs);")
cols = [r[1] for r in cur.fetchall()]
if "stdout" not in cols:
    cur.execute("ALTER TABLE jobs ADD COLUMN stdout TEXT;")
    print("Added column stdout")
else:
    print("stdout column already exists")
if "stderr" not in cols:
    cur.execute("ALTER TABLE jobs ADD COLUMN stderr TEXT;")
    print("Added column stderr")
else:
    print("stderr column already exists")
conn.commit()
conn.close()
