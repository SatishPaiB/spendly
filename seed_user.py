import random
import sqlite3
from datetime import datetime
from pathlib import Path
from werkzeug.security import generate_password_hash

# Import the get_db function from db.py
from database.db import get_db

# Common Indian first names across regions
FIRST_NAMES = [
    "Rahul", "Priya", "Arjun", "Ananya", "Vikram", "Shreya",
    "Aditya", "Neha", "Rohan", "Pooja", "Sanjay", "Deepika",
    "Nikhil", "Isha", "Akshay", "Kavya", "Harsh", "Ritika",
    "Devesh", "Anjali", "Kunal", "Sneha", "Varun", "Simran"
]

# Common Indian last names
LAST_NAMES = [
    "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Verma",
    "Reddy", "Sinha", "Malhotra", "Iyer", "Nair", "Pandey",
    "Chopra", "Kapoor", "Desai", "Joshi", "Rao", "Nayak",
    "Banerjee", "Mishra", "Trivedi", "Saxena"
]

def generate_unique_user():
    """Generate a user with unique email"""
    conn = get_db()
    cursor = conn.cursor()

    while True:
        # Generate random Indian name
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        name = f"{first_name} {last_name}"

        # Generate email with random suffix
        suffix = random.randint(10, 999)
        email = f"{first_name.lower()}.{last_name.lower()}{suffix}@gmail.com"

        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone() is None:
            # Email is unique, break the loop
            break

    # Hash the password
    password_hash = generate_password_hash("password123")

    # Insert the user
    cursor.execute(
        "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (name, email, password_hash, datetime.now().isoformat())
    )

    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": user_id,
        "name": name,
        "email": email
    }

if __name__ == "__main__":
    user = generate_unique_user()
    print("\n✓ User created successfully:")
    print(f"  ID:    {user['id']}")
    print(f"  Name:  {user['name']}")
    print(f"  Email: {user['email']}\n")
