import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from random import randint, choice, seed as set_seed

# Set seed for reproducibility
set_seed(42)

# Database path - use same pattern as db.py
DB_PATH = Path(__file__).resolve().parent / "expense_tracker.db"

# Category definitions with realistic amounts in ₹
CATEGORIES = {
    "Food": {"min": 50, "max": 800, "weight": 4},
    "Transport": {"min": 20, "max": 500, "weight": 2},
    "Bills": {"min": 200, "max": 3000, "weight": 2},
    "Health": {"min": 100, "max": 2000, "weight": 1},
    "Entertainment": {"min": 100, "max": 1500, "weight": 1},
    "Shopping": {"min": 200, "max": 5000, "weight": 2},
    "Other": {"min": 50, "max": 1000, "weight": 1},
}

DESCRIPTIONS = {
    "Food": ["Lunch", "Dinner", "Breakfast", "Groceries", "Cafe", "Restaurant"],
    "Transport": ["Auto/Taxi", "Bus", "Train", "Petrol", "Parking"],
    "Bills": ["Electricity", "Water", "Internet", "Phone", "Rent"],
    "Health": ["Doctor visit", "Pharmacy", "Hospital", "Medical test"],
    "Entertainment": ["Movie tickets", "Concert", "Games", "Streaming subscription"],
    "Shopping": ["Clothes", "Shoes", "Books", "Electronics", "Home items"],
    "Other": ["Misc", "Gifts", "Donations"],
}


def verify_user_exists(user_id):
    """Check if user exists in the database."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def generate_expenses(user_id, count, months):
    """Generate random expenses spread across the past N months."""
    expenses = []
    today = date.today()

    # Create weighted category list for proportional distribution
    weighted_categories = []
    for cat, info in CATEGORIES.items():
        weighted_categories.extend([cat] * info["weight"])

    for _ in range(count):
        # Random date within the past N months
        days_back = randint(0, months * 30)
        expense_date = today - timedelta(days=days_back)

        # Pick category
        category = choice(weighted_categories)

        # Random amount within category range
        cat_info = CATEGORIES[category]
        amount = randint(cat_info["min"], cat_info["max"]) + randint(0, 99) / 100

        # Pick description
        description = choice(DESCRIPTIONS[category])

        expenses.append({
            "user_id": user_id,
            "amount": amount,
            "category": category,
            "date": expense_date.isoformat(),
            "description": description,
        })

    return expenses


def insert_expenses(expenses):
    """Insert expenses into database with transaction handling."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        for expense in expenses:
            cursor.execute(
                """INSERT INTO expenses
                   (user_id, amount, category, date, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    expense["user_id"],
                    expense["amount"],
                    expense["category"],
                    expense["date"],
                    expense["description"],
                ),
            )
        conn.commit()
        return True, len(expenses)
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def get_sample_records(user_id, limit=5):
    """Fetch sample records for the user."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """SELECT id, user_id, amount, category, date, description
           FROM expenses
           WHERE user_id = ?
           ORDER BY date DESC
           LIMIT ?""",
        (user_id, limit),
    )

    records = cursor.fetchall()
    conn.close()
    return records


def main():
    if len(sys.argv) != 4:
        print("Usage: python seed_expenses.py <user_id> <count> <months>")
        print("Example: python seed_expenses.py 1 50 6")
        sys.exit(1)

    try:
        user_id = int(sys.argv[1])
        count = int(sys.argv[2])
        months = int(sys.argv[3])
    except ValueError:
        print("Usage: python seed_expenses.py <user_id> <count> <months>")
        print("Example: python seed_expenses.py 1 50 6")
        sys.exit(1)

    # Step 1: Verify user exists
    if not verify_user_exists(user_id):
        print(f"No user found with id {user_id}.")
        sys.exit(1)

    # Step 2: Generate expenses
    expenses = generate_expenses(user_id, count, months)

    # Step 3: Insert expenses
    success, result = insert_expenses(expenses)

    if not success:
        print(f"Error inserting expenses: {result}")
        sys.exit(1)

    # Step 4: Confirm and display results
    print(f"\n✓ Successfully inserted {result} expenses")

    # Show date range
    dates = [e["date"] for e in expenses]
    min_date = min(dates)
    max_date = max(dates)
    print(f"  Date range: {min_date} to {max_date}")

    # Show sample records
    print("\nSample records:")
    print("-" * 80)
    records = get_sample_records(user_id, 5)

    for record in records:
        print(
            f"  ID {record['id']:3} | ₹{record['amount']:8.2f} | {record['category']:15} | "
            f"{record['date']} | {record['description']}"
        )


if __name__ == "__main__":
    main()
