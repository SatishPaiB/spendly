"""
Tests for Step 08: Edit Expense.

Spec: .claude/specs/08-edit-expense.md

These tests exercise GET/POST /expenses/<id>/edit as described in the spec.
They are written against the documented behavior only:

- GET /expenses/<id>/edit renders a form pre-filled with the expense's
  current amount, category, date, and description, for the owning,
  logged-in user (200).
- GET /expenses/<id>/edit redirects unauthenticated users to /login.
- GET /expenses/<id>/edit returns 404 for a non-existent expense id.
- GET /expenses/<id>/edit returns 403 when the expense belongs to a
  different user.
- POST /expenses/<id>/edit with valid amount, category and date updates
  the existing expense row in place (same id, same user_id) and redirects
  to /profile.
- POST /expenses/<id>/edit with an invalid amount (non-numeric, zero,
  negative) re-renders the form with an error message and does not modify
  the row.
- POST /expenses/<id>/edit with an invalid date format re-renders the form
  with an error message and does not modify the row.
- POST /expenses/<id>/edit with an invalid/unknown category re-renders the
  form with an error message and does not modify the row.
- POST /expenses/<id>/edit with missing required fields re-renders the
  form with an error message and does not modify the row.
- On validation error, category/date/description are preserved in the
  re-rendered form.
- POST /expenses/<id>/edit returns 404 for a non-existent expense id and
  403 for an expense belonging to another user, without modifying any row.
- POST /expenses/<id>/edit without login redirects to /login and does not
  modify the row.
- Form uses the shared form-group / form-input / btn-submit classes to
  match add-expense/register/login.
- Template extends base.html (Spendly branding landmark present).

Because `database/db.py` hard-codes DB_PATH at import time, isolation is
achieved by monkeypatching `database.db.DB_PATH` to a per-test temp file and
re-running `init_db()` / `seed_db()` against it before each test (same
pattern used in tests/test_add_expense.py and tests/test_06-date-filter.py).
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


@pytest.fixture
def get_expense_by_id(app):
    """Fetch a single expense row by its primary key."""
    import database.db as db_module

    def _get(expense_id):
        conn = db_module.get_db()
        row = conn.execute(
            "SELECT id, user_id, amount, category, date, description, created_at "
            "FROM expenses WHERE id = ?",
            (expense_id,),
        ).fetchone()
        conn.close()
        return row

    return _get


@pytest.fixture
def create_expense_for_user(client, get_expenses_for_user):
    """
    Create an expense for the *currently logged-in* client via the (already
    tested) add-expense route, and return its id.

    NOTE: relies only on the add-expense feature's documented contract
    (POST /expenses/add creates a row and redirects to /profile), not on
    any edit-expense implementation detail.
    """

    def _do(
        user_id,
        amount="25.00",
        category="Food",
        expense_date=None,
        description="Original description",
    ):
        expense_date = expense_date or today_iso()
        before_ids = {row["id"] for row in get_expenses_for_user(user_id)}

        resp = client.post(
            "/expenses/add",
            data={
                "amount": amount,
                "category": category,
                "date": expense_date,
                "description": description,
            },
        )
        assert resp.status_code == 302, "Setup: creating the expense to edit must succeed"

        after = get_expenses_for_user(user_id)
        after_ids = {row["id"] for row in after}
        new_ids = after_ids - before_ids
        assert len(new_ids) == 1, "Setup: exactly one new expense should have been created"
        return new_ids.pop()

    return _do


def today_iso():
    return date.today().isoformat()


def yesterday_iso():
    return (date.today() - timedelta(days=1)).isoformat()


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
# GET /expenses/<id>/edit                                               #
# --------------------------------------------------------------------- #

class TestEditExpenseGet:
    def test_get_edit_expense_returns_200_for_owner(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        response = client.get(f"/expenses/{expense_id}/edit")

        assert response.status_code == 200
        assert b"form" in response.data.lower()

    def test_get_edit_expense_redirects_to_login_when_unauthenticated(self, client):
        response = client.get("/expenses/1/edit")

        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_get_edit_expense_returns_404_for_nonexistent_id(
        self, client, register_and_login
    ):
        register_and_login()

        response = client.get("/expenses/999999/edit")

        assert response.status_code == 404

    def test_get_edit_expense_returns_403_for_other_users_expense(
        self, client, register_and_login, create_expense_for_user
    ):
        user_a_id = register_and_login(
            name="User A", email="usera@example.com", password="passwordA1"
        )
        expense_id = create_expense_for_user(user_a_id)

        client.get("/logout")
        register_and_login(
            name="User B", email="userb@example.com", password="passwordB1"
        )

        response = client.get(f"/expenses/{expense_id}/edit")

        assert response.status_code == 403

    def test_form_uses_shared_styling_classes(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        response = client.get(f"/expenses/{expense_id}/edit")
        body = response.data.decode()

        assert response.status_code == 200
        assert "form-group" in body, (
            "Form should use the shared 'form-group' class like add-expense/register/login"
        )
        assert "form-input" in body, (
            "Form inputs should use the shared 'form-input' class like add-expense"
        )
        assert "btn-submit" in body, (
            "Submit button should use the shared 'btn-submit' class like add-expense"
        )

    def test_form_extends_base_layout(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        response = client.get(f"/expenses/{expense_id}/edit")
        body = response.data.decode()

        assert response.status_code == 200
        # base.html landmarks - Spendly branding should appear on every page.
        assert "Spendly" in body

    @pytest.mark.parametrize("category_key", VALID_CATEGORIES)
    def test_all_category_mapping_options_present_in_dropdown(
        self, client, register_and_login, create_expense_for_user, category_key
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        response = client.get(f"/expenses/{expense_id}/edit")
        body = response.data.decode()

        assert response.status_code == 200
        assert category_key in body, (
            f"Expected category option '{category_key}' from CATEGORY_MAPPING "
            "to be present in the edit form dropdown"
        )


# --------------------------------------------------------------------- #
# GET /expenses/<id>/edit — form pre-fill                               #
# --------------------------------------------------------------------- #

class TestEditExpenseFormPrefill:
    def test_get_edit_form_prefilled_with_existing_amount(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id, amount="73.25")

        response = client.get(f"/expenses/{expense_id}/edit")
        body = response.data.decode()

        assert response.status_code == 200
        assert "73.25" in body, "Existing amount should pre-fill the amount field"

    def test_get_edit_form_prefilled_with_existing_category(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id, category="Health")

        response = client.get(f"/expenses/{expense_id}/edit")
        body = response.data.decode()

        assert response.status_code == 200
        assert "Health" in body, "Existing category should pre-fill/select the category field"

    def test_get_edit_form_prefilled_with_existing_date(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id, expense_date=yesterday_iso())

        response = client.get(f"/expenses/{expense_id}/edit")
        body = response.data.decode()

        assert response.status_code == 200
        assert yesterday_iso() in body, "Existing date should pre-fill the date field"

    def test_get_edit_form_prefilled_with_existing_description(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(
            user_id, description="Unique original description text"
        )

        response = client.get(f"/expenses/{expense_id}/edit")
        body = response.data.decode()

        assert response.status_code == 200
        assert "Unique original description text" in body, (
            "Existing description should pre-fill the description field"
        )


# --------------------------------------------------------------------- #
# POST /expenses/<id>/edit — happy path                                 #
# --------------------------------------------------------------------- #

class TestEditExpenseHappyPath:
    def test_post_valid_edit_redirects_to_profile(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "99.99",
                "category": "Shopping",
                "date": today_iso(),
                "description": "Updated description",
            },
        )

        assert response.status_code == 302
        assert "/profile" in response.headers.get("Location", "")

    def test_post_valid_edit_updates_db_row_in_place(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id, count_expenses
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(
            user_id, amount="25.00", category="Food", description="Original description"
        )
        before_count = count_expenses()

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "99.99",
                "category": "Shopping",
                "date": today_iso(),
                "description": "Updated description",
            },
        )

        row = get_expense_by_id(expense_id)
        assert row is not None, "Editing must update the existing row, not delete it"
        assert row["id"] == expense_id, "Row id must remain unchanged"
        assert row["user_id"] == user_id, "Row ownership must remain unchanged"
        assert row["amount"] == 99.99
        assert row["category"] == "Shopping"
        assert row["date"] == today_iso()
        assert row["description"] == "Updated description"
        assert count_expenses() == before_count, (
            "Editing must not create a new row or delete an existing one"
        )

    def test_post_valid_edit_can_change_every_field_independently(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(
            user_id,
            amount="10.00",
            category="Food",
            expense_date=yesterday_iso(),
            description="Before edit",
        )

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "50.00",
                "category": "Bills",
                "date": today_iso(),
                "description": "After edit",
            },
        )

        row = get_expense_by_id(expense_id)
        assert row["amount"] == 50.00
        assert row["category"] == "Bills"
        assert row["date"] == today_iso()
        assert row["description"] == "After edit"

    def test_post_edit_reflected_on_profile_page(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id, description="Old text")

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "12.34",
                "category": "Entertainment",
                "date": today_iso(),
                "description": "New text after edit",
            },
        )

        response = client.get("/profile")

        assert response.status_code == 200
        assert b"New text after edit" in response.data
        assert money(12.34) in response.data
        assert b"Old text" not in response.data

    def test_post_edit_description_can_be_cleared(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id, description="Has a description")

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "5.00",
                "category": "Transport",
                "date": today_iso(),
                "description": "",
            },
        )

        assert response.status_code == 302
        row = get_expense_by_id(expense_id)
        assert row["description"] in (None, ""), (
            "Description should be clearable, same as add-expense's optional rule"
        )

    def test_post_edit_amount_is_rounded_to_two_decimal_places(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "19.995",
                "category": "Shopping",
                "date": today_iso(),
            },
        )

        row = get_expense_by_id(expense_id)
        assert row["amount"] == round(19.995, 2)

    @pytest.mark.parametrize("category_key", VALID_CATEGORIES)
    def test_post_edit_accepts_every_valid_category(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id, category_key
    ):
        user_id = register_and_login(
            email=f"edituser_{category_key.lower()}@example.com"
        )
        expense_id = create_expense_for_user(user_id, category="Other")

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "9.99",
                "category": category_key,
                "date": today_iso(),
            },
        )

        assert response.status_code == 302
        row = get_expense_by_id(expense_id)
        assert row["category"] == category_key


# --------------------------------------------------------------------- #
# POST /expenses/<id>/edit — validation                                 #
# --------------------------------------------------------------------- #

class TestEditExpenseValidation:
    @pytest.mark.parametrize(
        "bad_amount",
        ["abc", "-10", "0", "", "  ", "$5.00", "5,00"],
    )
    def test_invalid_amount_shows_error_and_does_not_modify_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id, bad_amount
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(
            user_id, amount="25.00", category="Food", description="Should stay unchanged"
        )
        before = get_expense_by_id(expense_id)

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": bad_amount,
                "category": "Food",
                "date": today_iso(),
                "description": "Should not be applied",
            },
        )
        body = response.data.decode().lower()

        assert response.status_code == 200
        assert "error" in body or "invalid" in body or "positive" in body, (
            f"Expected an error message for invalid amount {bad_amount!r}"
        )
        after = get_expense_by_id(expense_id)
        assert after["amount"] == before["amount"], (
            "No change should be applied to the row on validation failure"
        )
        assert after["description"] == before["description"]

    @pytest.mark.parametrize(
        "bad_date",
        ["07-25-2026", "2026/07/25", "not-a-date", "2026-13-45", "25th July 2026"],
    )
    def test_invalid_date_format_shows_error_and_does_not_modify_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id, bad_date
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)
        before = get_expense_by_id(expense_id)

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "20.00",
                "category": "Bills",
                "date": bad_date,
                "description": "Should not be applied",
            },
        )
        body = response.data.decode().lower()

        assert response.status_code == 200
        assert "error" in body or "invalid" in body or "format" in body, (
            f"Expected an error message for invalid date {bad_date!r}"
        )
        after = get_expense_by_id(expense_id)
        assert after["date"] == before["date"], (
            "No change should be applied to the row on validation failure"
        )

    @pytest.mark.parametrize(
        "bad_category",
        ["Groceries", "food", "", "<script>alert(1)</script>", "NotACategory"],
    )
    def test_invalid_category_shows_error_and_does_not_modify_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id, bad_category
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)
        before = get_expense_by_id(expense_id)

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "20.00",
                "category": bad_category,
                "date": today_iso(),
                "description": "Should not be applied",
            },
        )
        body = response.data.decode().lower()

        assert response.status_code == 200
        assert "error" in body or "invalid" in body or "select" in body or "valid" in body, (
            f"Expected an error message for invalid category {bad_category!r}"
        )
        after = get_expense_by_id(expense_id)
        assert after["category"] == before["category"], (
            "No change should be applied to the row on validation failure"
        )

    def test_missing_amount_shows_error_and_does_not_modify_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)
        before = get_expense_by_id(expense_id)

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={"category": "Food", "date": today_iso()},
        )

        assert response.status_code in (200, 400), (
            "Missing required field must not silently succeed"
        )
        after = get_expense_by_id(expense_id)
        assert after["amount"] == before["amount"]

    def test_missing_category_shows_error_and_does_not_modify_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)
        before = get_expense_by_id(expense_id)

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "20.00", "date": today_iso()},
        )

        assert response.status_code in (200, 400)
        after = get_expense_by_id(expense_id)
        assert after["category"] == before["category"]

    def test_missing_date_shows_error_and_does_not_modify_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)
        before = get_expense_by_id(expense_id)

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "20.00", "category": "Food"},
        )

        assert response.status_code in (200, 400)
        after = get_expense_by_id(expense_id)
        assert after["date"] == before["date"]

    def test_all_fields_empty_shows_error_and_does_not_modify_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)
        before = get_expense_by_id(expense_id)

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={"amount": "", "category": "", "date": ""},
        )
        body = response.data.decode().lower()

        assert response.status_code == 200
        assert "error" in body or "required" in body
        after = get_expense_by_id(expense_id)
        assert after["amount"] == before["amount"]
        assert after["category"] == before["category"]
        assert after["date"] == before["date"]


# --------------------------------------------------------------------- #
# POST /expenses/<id>/edit — form re-render / preserved input           #
# --------------------------------------------------------------------- #

class TestEditExpenseFormRerender:
    def test_category_and_date_preserved_after_invalid_amount(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        response = client.post(
            f"/expenses/{expense_id}/edit",
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
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        response = client.post(
            f"/expenses/{expense_id}/edit",
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

    def test_form_still_renders_after_error_with_valid_expense_id(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "garbage",
                "category": "Food",
                "date": today_iso(),
                "description": "Any",
            },
        )

        assert response.status_code == 200
        assert b"form" in response.data.lower()


# --------------------------------------------------------------------- #
# Auth / Ownership                                                       #
# --------------------------------------------------------------------- #

class TestEditExpenseAuthAndOwnership:
    def test_post_edit_without_login_redirects_to_login(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)
        client.get("/logout")

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "10.00",
                "category": "Food",
                "date": today_iso(),
            },
        )

        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_post_edit_without_login_does_not_modify_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id, amount="25.00")
        client.get("/logout")
        before = get_expense_by_id(expense_id)

        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "999.00",
                "category": "Food",
                "date": today_iso(),
            },
        )

        after = get_expense_by_id(expense_id)
        assert after["amount"] == before["amount"]

    def test_post_edit_returns_404_for_nonexistent_id(
        self, client, register_and_login
    ):
        register_and_login()

        response = client.post(
            "/expenses/999999/edit",
            data={
                "amount": "10.00",
                "category": "Food",
                "date": today_iso(),
            },
        )

        assert response.status_code == 404

    def test_get_edit_returns_403_and_does_not_leak_other_users_data(
        self, client, register_and_login, create_expense_for_user
    ):
        user_a_id = register_and_login(
            name="User A", email="usera2@example.com", password="passwordA1"
        )
        expense_id = create_expense_for_user(
            user_a_id, description="Secret User A description"
        )

        client.get("/logout")
        register_and_login(
            name="User B", email="userb2@example.com", password="passwordB1"
        )

        response = client.get(f"/expenses/{expense_id}/edit")

        assert response.status_code == 403
        assert b"Secret User A description" not in response.data, (
            "A different user's expense data must never be rendered to a non-owner"
        )

    def test_post_edit_returns_403_for_other_users_expense(
        self, client, register_and_login, create_expense_for_user
    ):
        user_a_id = register_and_login(
            name="User A", email="usera3@example.com", password="passwordA1"
        )
        expense_id = create_expense_for_user(user_a_id)

        client.get("/logout")
        register_and_login(
            name="User B", email="userb3@example.com", password="passwordB1"
        )

        response = client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "500.00",
                "category": "Shopping",
                "date": today_iso(),
                "description": "Hijacked",
            },
        )

        assert response.status_code == 403

    def test_post_edit_by_other_user_does_not_modify_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_a_id = register_and_login(
            name="User A", email="usera4@example.com", password="passwordA1"
        )
        expense_id = create_expense_for_user(
            user_a_id, amount="25.00", description="Original owner's data"
        )
        before = get_expense_by_id(expense_id)

        client.get("/logout")
        register_and_login(
            name="User B", email="userb4@example.com", password="passwordB1"
        )
        client.post(
            f"/expenses/{expense_id}/edit",
            data={
                "amount": "500.00",
                "category": "Shopping",
                "date": today_iso(),
                "description": "Hijacked",
            },
        )

        after = get_expense_by_id(expense_id)
        assert after["amount"] == before["amount"]
        assert after["description"] == before["description"]
        assert after["category"] == before["category"]

    def test_editing_one_users_expense_does_not_affect_other_users_expenses(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_a_id = register_and_login(
            name="User A", email="usera5@example.com", password="passwordA1"
        )
        expense_a_id = create_expense_for_user(
            user_a_id, amount="10.00", description="A's expense"
        )

        client.get("/logout")
        user_b_id = register_and_login(
            name="User B", email="userb5@example.com", password="passwordB1"
        )
        expense_b_id = create_expense_for_user(
            user_b_id, amount="20.00", description="B's expense"
        )

        client.post(
            f"/expenses/{expense_b_id}/edit",
            data={
                "amount": "99.00",
                "category": "Bills",
                "date": today_iso(),
                "description": "B edited own expense",
            },
        )

        row_a = get_expense_by_id(expense_a_id)
        row_b = get_expense_by_id(expense_b_id)
        assert row_a["amount"] == 10.00, "Editing B's expense must not touch A's expense"
        assert row_a["description"] == "A's expense"
        assert row_b["amount"] == 99.00
        assert row_b["description"] == "B edited own expense"
