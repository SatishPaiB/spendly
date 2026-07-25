"""
Tests for Step 07: Add Expense.

Spec: .claude/specs/07-add-expense.md

These tests exercise GET/POST /expenses/add as described in the spec. They
are written against the documented behavior only:

- GET /expenses/add renders the creation form for logged-in users (200).
- GET /expenses/add redirects unauthenticated users to /login.
- POST /expenses/add with valid amount, category and date creates an
  expense row for the logged-in user and redirects to /profile.
- POST /expenses/add with an invalid amount (non-numeric, zero, negative)
  re-renders the form with an error message and does not create a row.
- POST /expenses/add with an invalid date format re-renders the form with
  an error message and does not create a row.
- POST /expenses/add with an invalid/unknown category re-renders the form
  with an error message and does not create a row.
- POST /expenses/add with missing required fields (amount, category, date)
  re-renders the form with an error message and does not create a row.
- On validation error, category/date/description are preserved in the
  re-rendered form; amount is not required to be preserved per spec.
- A newly created expense appears in the profile page transaction list.
- All CATEGORY_MAPPING categories are present as options in the dropdown.
- Page title is "Add Expense — Spendly".
- Form uses the shared form-group / form-input / btn-submit classes to
  match register.html and login.html.

Because `database/db.py` hard-codes DB_PATH at import time, isolation is
achieved by monkeypatching `database.db.DB_PATH` to a per-test temp file and
re-running `init_db()` / `seed_db()` against it before each test (same
pattern used in tests/test_06-date-filter.py).
"""
from datetime import date, timedelta

import pytest


# --------------------------------------------------------------------- #
# Fixtures                                                              #
# --------------------------------------------------------------------- #

@pytest.fixture
def app(tmp_path, monkeypatch):
    """Flask app wired to an isolated, freshly initialized+seeded SQLite file."""
    import database.db as db_module

    db_file = tmp_path / "test_expense_tracker.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_file)

    db_module.init_db()
    db_module.seed_db()

    from app import app as flask_app

    flask_app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
        }
    )
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def register_and_login(client):
    """Register + log in a brand new user, returning their user_id."""

    def _do(name="Test User", email="testuser@example.com", password="testpass123"):
        resp = client.post(
            "/register",
            data={"name": name, "email": email, "password": password},
            follow_redirects=True,
        )
        assert resp.status_code == 200, "Registration should succeed for valid input"

        resp = client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )
        assert resp.status_code == 200, "Login should succeed with the just-registered credentials"

        import database.db as db_module

        user = db_module.get_user_by_email(email)
        assert user is not None, "User should exist after registration"
        return user["id"]

    return _do


@pytest.fixture
def count_expenses(app):
    """Return the total number of rows currently in the expenses table."""
    import database.db as db_module

    def _count():
        conn = db_module.get_db()
        row = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()
        conn.close()
        return row["c"]

    return _count


@pytest.fixture
def get_expenses_for_user(app):
    """Fetch all expense rows for a given user id, newest insert last (by id)."""
    import database.db as db_module

    def _get(user_id):
        conn = db_module.get_db()
        rows = conn.execute(
            "SELECT id, user_id, amount, category, date, description, created_at "
            "FROM expenses WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
        conn.close()
        return rows

    return _get


def today_iso():
    return date.today().isoformat()


def money(amount):
    """Render an amount the same way the template does: '%.2f'|format."""
    return f"{amount:.2f}".encode("utf-8")


VALID_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Shopping",
    "Health",
    "Entertainment",
    "Other",
]


# --------------------------------------------------------------------- #
# GET /expenses/add                                                     #
# --------------------------------------------------------------------- #

class TestAddExpenseGet:
    def test_get_add_expense_returns_200_for_logged_in_user(
        self, client, register_and_login
    ):
        register_and_login()

        response = client.get("/expenses/add")

        assert response.status_code == 200
        assert b"form" in response.data.lower()

    def test_get_add_expense_redirects_to_login_when_unauthenticated(self, client):
        response = client.get("/expenses/add")

        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_get_add_expense_page_title_is_correct(self, client, register_and_login):
        register_and_login()

        response = client.get("/expenses/add")
        body = response.data.decode()

        assert response.status_code == 200
        assert "Add Expense — Spendly" in body, (
            "Page title block must read 'Add Expense — Spendly' per spec"
        )

    @pytest.mark.parametrize("category_key", VALID_CATEGORIES)
    def test_all_category_mapping_options_present_in_dropdown(
        self, client, register_and_login, category_key
    ):
        register_and_login()

        response = client.get("/expenses/add")
        body = response.data.decode()

        assert response.status_code == 200
        assert category_key in body, (
            f"Expected category option '{category_key}' from CATEGORY_MAPPING "
            "to be present in the form dropdown"
        )

    def test_form_uses_shared_styling_classes(self, client, register_and_login):
        register_and_login()

        response = client.get("/expenses/add")
        body = response.data.decode()

        assert response.status_code == 200
        assert 'class="form-group"' in body or "form-group" in body, (
            "Form should use the shared 'form-group' class like register/login"
        )
        assert "form-input" in body, (
            "Form inputs should use the shared 'form-input' class like register/login"
        )
        assert "btn-submit" in body, (
            "Submit button should use the shared 'btn-submit' class like register/login"
        )

    def test_form_extends_base_layout(self, client, register_and_login):
        register_and_login()

        response = client.get("/expenses/add")
        body = response.data.decode()

        assert response.status_code == 200
        # base.html landmarks - Spendly branding should appear on every page.
        assert "Spendly" in body


# --------------------------------------------------------------------- #
# POST /expenses/add — happy path                                       #
# --------------------------------------------------------------------- #

class TestAddExpenseHappyPath:
    def test_post_valid_expense_redirects_to_profile(
        self, client, register_and_login
    ):
        register_and_login()

        response = client.post(
            "/expenses/add",
            data={
                "amount": "42.50",
                "category": "Food",
                "date": today_iso(),
                "description": "Grocery run",
            },
        )

        assert response.status_code == 302
        assert "/profile" in response.headers.get("Location", "")

    def test_post_valid_expense_creates_db_row_with_correct_data(
        self, client, register_and_login, get_expenses_for_user
    ):
        user_id = register_and_login()

        client.post(
            "/expenses/add",
            data={
                "amount": "42.50",
                "category": "Food",
                "date": today_iso(),
                "description": "Grocery run",
            },
        )

        rows = get_expenses_for_user(user_id)
        assert len(rows) == 1, "Exactly one expense should have been created"
        row = rows[0]
        assert row["amount"] == 42.50
        assert row["category"] == "Food"
        assert row["date"] == today_iso()
        assert row["description"] == "Grocery run"
        assert row["user_id"] == user_id

    def test_post_valid_expense_sets_created_at_automatically(
        self, client, register_and_login, get_expenses_for_user
    ):
        user_id = register_and_login()

        client.post(
            "/expenses/add",
            data={
                "amount": "10.00",
                "category": "Other",
                "date": today_iso(),
            },
        )

        rows = get_expenses_for_user(user_id)
        assert len(rows) == 1
        assert rows[0]["created_at"], "created_at should be populated automatically"

    def test_post_expense_appears_on_profile_page_after_creation(
        self, client, register_and_login
    ):
        register_and_login()

        client.post(
            "/expenses/add",
            data={
                "amount": "18.75",
                "category": "Entertainment",
                "date": today_iso(),
                "description": "Concert ticket",
            },
        )

        response = client.get("/profile")

        assert response.status_code == 200
        assert b"Concert ticket" in response.data
        assert money(18.75) in response.data

    def test_post_expense_description_is_optional(
        self, client, register_and_login, get_expenses_for_user
    ):
        user_id = register_and_login()

        response = client.post(
            "/expenses/add",
            data={
                "amount": "5.00",
                "category": "Transport",
                "date": today_iso(),
                "description": "",
            },
        )

        assert response.status_code == 302
        rows = get_expenses_for_user(user_id)
        assert len(rows) == 1
        assert rows[0]["description"] in (None, ""), (
            "Empty description should be allowed and stored as empty/null"
        )

    def test_post_expense_amount_is_rounded_to_two_decimal_places(
        self, client, register_and_login, get_expenses_for_user
    ):
        user_id = register_and_login()

        client.post(
            "/expenses/add",
            data={
                "amount": "19.995",
                "category": "Shopping",
                "date": today_iso(),
            },
        )

        rows = get_expenses_for_user(user_id)
        assert len(rows) == 1
        assert rows[0]["amount"] == round(19.995, 2), (
            "Stored amount should be rounded to 2 decimal places"
        )

    @pytest.mark.parametrize("category_key", VALID_CATEGORIES)
    def test_post_expense_accepts_every_valid_category(
        self, client, register_and_login, get_expenses_for_user, category_key
    ):
        user_id = register_and_login(
            email=f"user_{category_key.lower()}@example.com"
        )

        response = client.post(
            "/expenses/add",
            data={
                "amount": "9.99",
                "category": category_key,
                "date": today_iso(),
            },
        )

        assert response.status_code == 302
        rows = get_expenses_for_user(user_id)
        assert len(rows) == 1
        assert rows[0]["category"] == category_key


# --------------------------------------------------------------------- #
# POST /expenses/add — validation                                       #
# --------------------------------------------------------------------- #

class TestAddExpenseValidation:
    @pytest.mark.parametrize(
        "bad_amount",
        ["abc", "-10", "0", "", "  ", "$5.00", "5,00"],
    )
    def test_invalid_amount_shows_error_and_does_not_create_row(
        self, client, register_and_login, count_expenses, bad_amount
    ):
        register_and_login()
        before = count_expenses()

        response = client.post(
            "/expenses/add",
            data={
                "amount": bad_amount,
                "category": "Food",
                "date": today_iso(),
                "description": "Should fail",
            },
        )
        body = response.data.decode().lower()

        assert response.status_code == 200
        assert "error" in body or "invalid" in body or "positive" in body, (
            f"Expected an error message for invalid amount {bad_amount!r}"
        )
        assert count_expenses() == before, "No row should be created on validation failure"

    @pytest.mark.parametrize(
        "bad_date",
        ["07-25-2026", "2026/07/25", "not-a-date", "2026-13-45", "25th July 2026"],
    )
    def test_invalid_date_format_shows_error_and_does_not_create_row(
        self, client, register_and_login, count_expenses, bad_date
    ):
        register_and_login()
        before = count_expenses()

        response = client.post(
            "/expenses/add",
            data={
                "amount": "20.00",
                "category": "Bills",
                "date": bad_date,
                "description": "Should fail",
            },
        )
        body = response.data.decode().lower()

        assert response.status_code == 200
        assert "error" in body or "invalid" in body or "format" in body, (
            f"Expected an error message for invalid date {bad_date!r}"
        )
        assert count_expenses() == before, "No row should be created on validation failure"

    @pytest.mark.parametrize(
        "bad_category",
        ["Groceries", "food", "", "<script>alert(1)</script>", "NotACategory"],
    )
    def test_invalid_category_shows_error_and_does_not_create_row(
        self, client, register_and_login, count_expenses, bad_category
    ):
        register_and_login()
        before = count_expenses()

        response = client.post(
            "/expenses/add",
            data={
                "amount": "20.00",
                "category": bad_category,
                "date": today_iso(),
                "description": "Should fail",
            },
        )
        body = response.data.decode().lower()

        assert response.status_code == 200
        assert "error" in body or "invalid" in body or "select" in body or "valid" in body, (
            f"Expected an error message for invalid category {bad_category!r}"
        )
        assert count_expenses() == before, "No row should be created on validation failure"

    def test_missing_amount_shows_error_and_does_not_create_row(
        self, client, register_and_login, count_expenses
    ):
        register_and_login()
        before = count_expenses()

        response = client.post(
            "/expenses/add",
            data={"category": "Food", "date": today_iso()},
        )

        assert response.status_code in (200, 400), (
            "Missing required field must not silently succeed"
        )
        assert count_expenses() == before

    def test_missing_category_shows_error_and_does_not_create_row(
        self, client, register_and_login, count_expenses
    ):
        register_and_login()
        before = count_expenses()

        response = client.post(
            "/expenses/add",
            data={"amount": "20.00", "date": today_iso()},
        )

        assert response.status_code in (200, 400)
        assert count_expenses() == before

    def test_missing_date_shows_error_and_does_not_create_row(
        self, client, register_and_login, count_expenses
    ):
        register_and_login()
        before = count_expenses()

        response = client.post(
            "/expenses/add",
            data={"amount": "20.00", "category": "Food"},
        )

        assert response.status_code in (200, 400)
        assert count_expenses() == before

    def test_all_fields_empty_shows_error_and_does_not_create_row(
        self, client, register_and_login, count_expenses
    ):
        register_and_login()
        before = count_expenses()

        response = client.post(
            "/expenses/add",
            data={"amount": "", "category": "", "date": ""},
        )
        body = response.data.decode().lower()

        assert response.status_code == 200
        assert "error" in body or "required" in body
        assert count_expenses() == before


# --------------------------------------------------------------------- #
# POST /expenses/add — form re-render / preserved input                 #
# --------------------------------------------------------------------- #

class TestAddExpenseFormPrefill:
    def test_category_and_date_preserved_after_invalid_amount(
        self, client, register_and_login
    ):
        register_and_login()

        response = client.post(
            "/expenses/add",
            data={
                "amount": "not-a-number",
                "category": "Health",
                "date": today_iso(),
                "description": "Doctor visit",
            },
        )
        body = response.data.decode()

        assert response.status_code == 200
        assert "Doctor visit" in body, "Description should be preserved on validation error"
        assert today_iso() in body, "Date should be preserved on validation error"

    def test_description_preserved_after_invalid_category(
        self, client, register_and_login
    ):
        register_and_login()

        response = client.post(
            "/expenses/add",
            data={
                "amount": "15.00",
                "category": "NotReal",
                "date": today_iso(),
                "description": "Keep me around",
            },
        )
        body = response.data.decode()

        assert response.status_code == 200
        assert "Keep me around" in body, "Description input should be preserved after error"

    def test_amount_field_not_required_to_be_preserved_after_error(
        self, client, register_and_login
    ):
        """
        Per spec: 'Form pre-fills with user input after validation error
        (except amount if invalid)'. This test only asserts the route does
        not error out when amount is invalid — it intentionally does not
        assert the amount value is echoed back, since the spec explicitly
        exempts it.
        """
        register_and_login()

        response = client.post(
            "/expenses/add",
            data={
                "amount": "garbage",
                "category": "Food",
                "date": today_iso(),
                "description": "Any",
            },
        )

        assert response.status_code == 200


# --------------------------------------------------------------------- #
# Auth                                                                   #
# --------------------------------------------------------------------- #

class TestAddExpenseAuth:
    def test_post_add_expense_without_login_redirects_to_login(self, client):
        response = client.post(
            "/expenses/add",
            data={
                "amount": "10.00",
                "category": "Food",
                "date": today_iso(),
            },
        )

        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_post_add_expense_without_login_does_not_create_row(
        self, client, count_expenses
    ):
        before = count_expenses()

        client.post(
            "/expenses/add",
            data={
                "amount": "10.00",
                "category": "Food",
                "date": today_iso(),
            },
        )

        assert count_expenses() == before

    def test_expense_is_linked_to_the_logged_in_user_not_another_user(
        self, client, register_and_login, get_expenses_for_user
    ):
        user_a_id = register_and_login(
            name="User A", email="usera@example.com", password="passwordA1"
        )
        client.post(
            "/expenses/add",
            data={
                "amount": "30.00",
                "category": "Food",
                "date": today_iso(),
                "description": "User A's expense",
            },
        )

        client.get("/logout")
        user_b_id = register_and_login(
            name="User B", email="userb@example.com", password="passwordB1"
        )
        client.post(
            "/expenses/add",
            data={
                "amount": "40.00",
                "category": "Transport",
                "date": today_iso(),
                "description": "User B's expense",
            },
        )

        a_rows = get_expenses_for_user(user_a_id)
        b_rows = get_expenses_for_user(user_b_id)

        assert len(a_rows) == 1 and a_rows[0]["description"] == "User A's expense"
        assert len(b_rows) == 1 and b_rows[0]["description"] == "User B's expense"
