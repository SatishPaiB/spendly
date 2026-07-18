import sqlite3
from datetime import date, timedelta
from pathlib import Path
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent.parent / "expense_tracker.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    password_hash = generate_password_hash("demo123")
    cursor.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash),
    )
    user_id = cursor.lastrowid

    today = date.today()
    expenses = [
        (user_id, 15.50, "Food", (today - timedelta(days=5)).isoformat(), "Lunch"),
        (user_id, 45.00, "Transport", (today - timedelta(days=4)).isoformat(), "Taxi"),
        (user_id, 120.00, "Bills", (today - timedelta(days=3)).isoformat(), "Electricity"),
        (user_id, 35.00, "Health", (today - timedelta(days=2)).isoformat(), "Pharmacy"),
        (user_id, 50.00, "Entertainment", (today - timedelta(days=1)).isoformat(), "Movie tickets"),
        (user_id, 85.00, "Shopping", today.isoformat(), "Clothes"),
        (user_id, 25.50, "Food", (today - timedelta(days=6)).isoformat(), "Dinner"),
        (user_id, 12.00, "Other", (today - timedelta(days=7)).isoformat(), "Misc"),
    ]

    cursor.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )

    conn.commit()
    conn.close()
