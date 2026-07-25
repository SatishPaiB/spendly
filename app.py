from flask import Flask, render_template, session, request, redirect, url_for, abort
from werkzeug.security import check_password_hash
from functools import wraps
from datetime import datetime
from database.db import init_db, seed_db, get_user_by_email, create_user, get_db, get_expenses_by_user_and_date

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"

CATEGORY_MAPPING = {
    "Food": {"name": "Food & Dining", "slug": "food"},
    "Transport": {"name": "Transport", "slug": "transport"},
    "Bills": {"name": "Bills & Utilities", "slug": "bills"},
    "Shopping": {"name": "Shopping", "slug": "shopping"},
    "Health": {"name": "Health", "slug": "health"},
    "Entertainment": {"name": "Entertainment", "slug": "entertainment"},
    "Other": {"name": "Other", "slug": "other"},
}


# ------------------------------------------------------------------ #
# Decorators                                                          #
# ------------------------------------------------------------------ #

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


def is_valid_date(date_string):
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def format_date_range(start_date, end_date):
    try:
        if start_date:
            start_obj = datetime.strptime(start_date, "%Y-%m-%d")
            start_formatted = f"{start_obj.strftime('%b')} {start_obj.day}, {start_obj.year}"
        else:
            start_formatted = "earliest"

        if end_date:
            end_obj = datetime.strptime(end_date, "%Y-%m-%d")
            end_formatted = f"{end_obj.strftime('%b')} {end_obj.day}, {end_obj.year}"
        else:
            end_formatted = "today"

        return f"{start_formatted} - {end_formatted}"
    except ValueError:
        return ""


def build_transactions_and_stats(expenses_rows):
    transactions = []
    category_totals = {}

    for expense in expenses_rows:
        db_category = expense["category"]
        mapped = CATEGORY_MAPPING.get(db_category, {"name": db_category, "slug": db_category.lower()})

        transactions.append({
            "date": expense["date"],
            "description": expense["description"],
            "category": mapped["slug"],
            "amount": expense["amount"],
        })

        if db_category not in category_totals:
            category_totals[db_category] = 0
        category_totals[db_category] += expense["amount"]

    total_spent = sum(category_totals.values())
    transaction_count = len(transactions)

    if category_totals:
        top_category_db = max(category_totals, key=category_totals.get)
        top_category = CATEGORY_MAPPING[top_category_db]["name"]
    else:
        top_category = "—"

    stats = {
        "total_spent": round(total_spent, 2),
        "transaction_count": transaction_count,
        "top_category": top_category,
    }

    categories = []
    if total_spent > 0:
        for db_category, total in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            mapped = CATEGORY_MAPPING[db_category]
            percent = int((total / total_spent) * 100)
            categories.append({
                "name": mapped["name"],
                "slug": mapped["slug"],
                "total": round(total, 2),
                "percent": percent,
            })

    return transactions, stats, categories

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    if "name" not in request.form or "email" not in request.form or "password" not in request.form:
        abort(400)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name:
        return render_template("register.html", error="Please enter your full name.")

    if "@" not in email:
        return render_template("register.html", error="Please enter a valid email address.")

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    existing_user = get_user_by_email(email)
    if existing_user:
        return render_template("register.html", error="An account with that email already exists.")

    create_user(name, email, password)
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        error = None

        if not email or not password:
            error = "Please enter both email and password."
        else:
            db = get_db()
            user = db.execute(
                "SELECT id, email, password_hash FROM users WHERE email = ?", (email,)
            ).fetchone()
            db.close()

            if user is None or not check_password_hash(user["password_hash"], password):
                error = "Invalid email or password."

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            return redirect(url_for("profile"))

        return render_template("login.html", error=error)

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/analytics")
@login_required
def analytics():
    stats = {
        "users": "2,400",
        "satisfaction": "97%",
        "speed": "<200ms",
        "data": "5M+",
    }
    return render_template("analytics.html", active_page="analytics", stats=stats)


@app.route("/profile")
@login_required
def profile():
    db = get_db()
    user_row = db.execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()
    db.close()

    if user_row is None:
        abort(404)

    name = user_row["name"]
    email = user_row["email"]
    initials = "".join([part[0].upper() for part in name.split()])
    created_date = user_row["created_at"][:10]

    user = {
        "name": name,
        "email": email,
        "initials": initials,
        "member_since": created_date,
    }

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    error = None

    if start_date or end_date:
        if start_date and not is_valid_date(start_date):
            error = "Please enter dates in YYYY-MM-DD format."
        elif end_date and not is_valid_date(end_date):
            error = "Please enter dates in YYYY-MM-DD format."
        elif start_date and end_date and start_date > end_date:
            error = "Start date cannot be after end date."

    expenses_rows = get_expenses_by_user_and_date(session["user_id"], start_date, end_date)
    transactions, stats, categories = build_transactions_and_stats(expenses_rows)

    has_filter = bool(start_date or end_date)
    date_range_text = format_date_range(start_date, end_date) if has_filter else ""

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        error=error,
        has_filter=has_filter,
        active_start_date=start_date,
        active_end_date=end_date,
        date_range_text=date_range_text,
        active_page="profile",
    )


@app.route("/expenses/add")
@login_required
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
@login_required
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
@login_required
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
