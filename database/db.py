import sqlite3
import os


def get_db():
    # init_db() and seed_db() remain Step 01 scope, not implemented here.
    db_path = os.path.join(os.path.dirname(__file__), "..", "expense_tracker.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
