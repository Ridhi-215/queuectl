# src/queuectl/db.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "queue.db"  # src/queuectl/../queue.db

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # We'll add real schema later; this is a placeholder
    cur.execute("PRAGMA journal_mode=WAL;")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Initialized DB at", DB_PATH)
