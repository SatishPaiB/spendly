from flask import Flask, render_template, session, request, redirect, url_for, abort
from werkzeug.security import check_password_hash
from functools import wraps
from database.db import init_db, seed_db, get_user_by_email, create_user, get_db

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"


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

    stats = {
        "total_spent": 18420.50,
        "transaction_count": 27,
        "top_category": "Food & Dining",
    }

    transactions = [
        {"date": "2026-07-15", "description": "Swiggy — dinner order", "category": "food", "amount": 640.00},
        {"date": "2026-07-13", "description": "Uber ride to office", "category": "transport", "amount": 220.50},
        {"date": "2026-07-10", "description": "Amazon — desk lamp", "category": "shopping", "amount": 1299.00},
        {"date": "2026-07-08", "description": "Electricity bill — BESCOM", "category": "bills", "amount": 2150.00},
        {"date": "2026-07-05", "description": "Cafe Coffee Day", "category": "food", "amount": 310.00},
    ]

    categories = [
        {"name": "Food & Dining", "slug": "food", "total": 6820.00, "percent": 37},
        {"name": "Bills & Utilities", "slug": "bills", "total": 4900.00, "percent": 27},
        {"name": "Shopping", "slug": "shopping", "total": 3900.50, "percent": 21},
        {"name": "Transport", "slug": "transport", "total": 2800.00, "percent": 15},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
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
