import sqlite3, os

db = os.path.join("src", "queue.db")
conn = sqlite3.connect(db)
cur = conn.cursor()

cur.execute("PRAGMA table_info(jobs);")
cols = cur.fetchall()

print("jobs table columns:")
for c in cols:
    print(c)

conn.close()
