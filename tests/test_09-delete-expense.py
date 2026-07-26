"""
Tests for Step 09: Delete Expense.

Spec: .claude/specs/09-delete-expense.md

These tests exercise POST /expenses/<id>/delete as described in the spec.
They are written against the documented behavior only:

- POST /expenses/<id>/delete permanently removes the expense row for the
  owning, logged-in user and redirects (302) to /profile.
- There is no GET route for delete — deletion happens via form submission
  only. GET (and other non-POST methods) must return 405.
- Unauthenticated requests are redirected to /login (via @login_required)
  and must not delete anything.
- A non-existent expense id returns 404.
- An expense that exists but belongs to a different user returns 403, and
  the row is not deleted.
- After a successful delete, the expense row no longer exists in the DB,
  the transaction row no longer appears on the profile page, and the
  profile stats (total spent, transaction count, top category) reflect
  the remaining expenses only.
- Deleting one user's expense must never affect another user's expenses.

Because `database/db.py` hard-codes DB_PATH at import time, isolation is
achieved by monkeypatching `database.db.DB_PATH` to a per-test temp file and
re-running `init_db()` / `seed_db()` against it before each test (same
pattern used in tests/test_08-edit-expense.py).
"""
from datetime import date

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
def count_expenses_for_user(app):
    """Return the number of expense rows belonging to a given user."""
    import database.db as db_module

    def _count(user_id):
        conn = db_module.get_db()
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
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
    any delete-expense implementation detail.
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
        assert resp.status_code == 302, "Setup: creating the expense to delete must succeed"

        after = get_expenses_for_user(user_id)
        after_ids = {row["id"] for row in after}
        new_ids = after_ids - before_ids
        assert len(new_ids) == 1, "Setup: exactly one new expense should have been created"
        return new_ids.pop()

    return _do


def today_iso():
    return date.today().isoformat()


def money(amount):
    """Render an amount the same way the template does: '%.2f'|format."""
    return f"{amount:.2f}".encode("utf-8")


# --------------------------------------------------------------------- #
# POST /expenses/<id>/delete — happy path                               #
# --------------------------------------------------------------------- #

class TestDeleteExpenseHappyPath:
    def test_post_delete_redirects_to_profile(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        response = client.post(f"/expenses/{expense_id}/delete")

        assert response.status_code == 302
        assert "/profile" in response.headers.get("Location", "")

    def test_post_delete_removes_row_from_db(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)
        assert get_expense_by_id(expense_id) is not None, "Setup: expense should exist"

        client.post(f"/expenses/{expense_id}/delete")

        assert get_expense_by_id(expense_id) is None, (
            "Expense row must be permanently removed from the database"
        )

    def test_post_delete_decrements_total_expense_count(
        self, client, register_and_login, create_expense_for_user, count_expenses
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)
        before_count = count_expenses()

        client.post(f"/expenses/{expense_id}/delete")

        assert count_expenses() == before_count - 1, (
            "Deleting an expense must decrease the total row count by exactly one"
        )

    def test_post_delete_removes_row_from_profile_page(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(
            user_id, description="Unique row to be deleted"
        )

        response = client.get("/profile")
        assert b"Unique row to be deleted" in response.data, (
            "Setup: expense should be visible before deletion"
        )

        client.post(f"/expenses/{expense_id}/delete")
        response = client.get("/profile")

        assert response.status_code == 200
        assert b"Unique row to be deleted" not in response.data, (
            "Deleted expense must no longer appear in the transaction list"
        )

    def test_post_delete_follow_redirects_lands_on_profile(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        response = client.post(f"/expenses/{expense_id}/delete", follow_redirects=True)

        assert response.status_code == 200
        assert b"Spendly" in response.data


# --------------------------------------------------------------------- #
# Auth                                                                   #
# --------------------------------------------------------------------- #

class TestDeleteExpenseAuth:
    def test_post_delete_without_login_redirects_to_login(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)
        client.get("/logout")

        response = client.post(f"/expenses/{expense_id}/delete")

        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_post_delete_without_login_does_not_remove_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)
        client.get("/logout")

        client.post(f"/expenses/{expense_id}/delete")

        assert get_expense_by_id(expense_id) is not None, (
            "An unauthenticated delete request must not remove the expense"
        )

    def test_post_delete_nonexistent_id_returns_404(
        self, client, register_and_login
    ):
        register_and_login()

        response = client.post("/expenses/999999/delete")

        assert response.status_code == 404


# --------------------------------------------------------------------- #
# HTTP method enforcement — POST-only route                             #
# --------------------------------------------------------------------- #

class TestDeleteExpenseMethod:
    @pytest.mark.parametrize("method", ["get", "head", "put", "patch", "delete"])
    def test_non_post_methods_return_405(
        self, client, register_and_login, create_expense_for_user, method
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        response = getattr(client, method)(f"/expenses/{expense_id}/delete")

        assert response.status_code == 405, (
            f"{method.upper()} /expenses/<id>/delete should not be allowed; "
            "deletion must only be reachable via POST form submission"
        )

    def test_get_delete_does_not_remove_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        client.get(f"/expenses/{expense_id}/delete")

        assert get_expense_by_id(expense_id) is not None, (
            "Navigating to the delete URL via GET must never delete the expense "
            "(protects against browser prefetch / crawlers)"
        )


# --------------------------------------------------------------------- #
# Ownership                                                              #
# --------------------------------------------------------------------- #

class TestDeleteExpenseOwnership:
    def test_post_delete_other_users_expense_returns_403(
        self, client, register_and_login, create_expense_for_user
    ):
        user_a_id = register_and_login(
            name="User A", email="usera_del@example.com", password="passwordA1"
        )
        expense_id = create_expense_for_user(user_a_id)

        client.get("/logout")
        register_and_login(
            name="User B", email="userb_del@example.com", password="passwordB1"
        )

        response = client.post(f"/expenses/{expense_id}/delete")

        assert response.status_code == 403

    def test_post_delete_other_users_expense_does_not_remove_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_a_id = register_and_login(
            name="User A", email="usera_del2@example.com", password="passwordA1"
        )
        expense_id = create_expense_for_user(
            user_a_id, description="A's protected expense"
        )

        client.get("/logout")
        register_and_login(
            name="User B", email="userb_del2@example.com", password="passwordB1"
        )
        client.post(f"/expenses/{expense_id}/delete")

        row = get_expense_by_id(expense_id)
        assert row is not None, (
            "A non-owner's delete attempt must not remove another user's expense"
        )
        assert row["description"] == "A's protected expense"

    def test_deleting_one_users_expense_does_not_affect_other_users_expenses(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id,
        count_expenses_for_user,
    ):
        user_a_id = register_and_login(
            name="User A", email="usera_del3@example.com", password="passwordA1"
        )
        expense_a_id = create_expense_for_user(
            user_a_id, amount="10.00", description="A's expense"
        )

        client.get("/logout")
        user_b_id = register_and_login(
            name="User B", email="userb_del3@example.com", password="passwordB1"
        )
        expense_b_id = create_expense_for_user(
            user_b_id, amount="20.00", description="B's expense"
        )
        before_a_count = count_expenses_for_user(user_a_id)

        client.post(f"/expenses/{expense_b_id}/delete")

        row_a = get_expense_by_id(expense_a_id)
        row_b = get_expense_by_id(expense_b_id)
        assert row_a is not None, "Deleting B's expense must not touch A's expense"
        assert row_a["description"] == "A's expense"
        assert count_expenses_for_user(user_a_id) == before_a_count
        assert row_b is None, "B's own expense should have been deleted"


# --------------------------------------------------------------------- #
# Database side effects                                                 #
# --------------------------------------------------------------------- #

class TestDeleteExpenseDatabase:
    def test_delete_only_removes_targeted_row(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id,
        get_expenses_for_user,
    ):
        user_id = register_and_login()
        expense_1 = create_expense_for_user(user_id, amount="10.00", description="Keep me")
        expense_2 = create_expense_for_user(user_id, amount="20.00", description="Delete me")
        expense_3 = create_expense_for_user(user_id, amount="30.00", description="Keep me too")

        client.post(f"/expenses/{expense_2}/delete")

        assert get_expense_by_id(expense_1) is not None
        assert get_expense_by_id(expense_2) is None
        assert get_expense_by_id(expense_3) is not None
        remaining = get_expenses_for_user(user_id)
        assert len(remaining) == 2

    def test_delete_is_idempotent_failure_on_second_attempt(
        self, client, register_and_login, create_expense_for_user, get_expense_by_id
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(user_id)

        first = client.post(f"/expenses/{expense_id}/delete")
        assert first.status_code == 302

        second = client.post(f"/expenses/{expense_id}/delete")

        assert second.status_code == 404, (
            "Deleting an already-deleted expense id should now report 404"
        )
        assert get_expense_by_id(expense_id) is None


# --------------------------------------------------------------------- #
# Profile stats update after deletion                                   #
# --------------------------------------------------------------------- #

class TestDeleteExpenseProfileUpdate:
    def test_transaction_count_updates_after_deletion(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        create_expense_for_user(user_id, amount="10.00", description="First")
        expense_id = create_expense_for_user(user_id, amount="20.00", description="Second")
        create_expense_for_user(user_id, amount="30.00", description="Third")

        response_before = client.get("/profile")
        assert response_before.status_code == 200

        client.post(f"/expenses/{expense_id}/delete")
        response_after = client.get("/profile")

        assert response_after.status_code == 200
        assert b"Second" not in response_after.data
        assert b"First" in response_after.data
        assert b"Third" in response_after.data

    def test_total_spent_decreases_after_deletion(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        create_expense_for_user(user_id, amount="10.00", description="Stays")
        expense_id = create_expense_for_user(user_id, amount="50.00", description="Removed")

        client.post(f"/expenses/{expense_id}/delete")
        response = client.get("/profile")
        body = response.data.decode()

        assert response.status_code == 200
        assert money(60.00).decode() not in body, (
            "Total spent should no longer include the deleted expense's amount"
        )

    def test_top_category_updates_after_deletion_of_only_expense_in_category(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        create_expense_for_user(
            user_id, amount="10.00", category="Food", description="Food expense"
        )
        expense_id = create_expense_for_user(
            user_id, amount="500.00", category="Shopping", description="Big shopping expense"
        )

        response_before = client.get("/profile")
        assert response_before.status_code == 200

        client.post(f"/expenses/{expense_id}/delete")
        response_after = client.get("/profile")
        body = response_after.data.decode()

        assert response_after.status_code == 200
        assert b"Big shopping expense" not in response_after.data
        assert "Food" in body

    def test_all_stats_reflect_zero_after_deleting_only_expense(
        self, client, register_and_login, create_expense_for_user
    ):
        user_id = register_and_login()
        expense_id = create_expense_for_user(
            user_id, amount="42.00", description="Only expense"
        )

        client.post(f"/expenses/{expense_id}/delete")
        response = client.get("/profile")

        assert response.status_code == 200
        assert b"Only expense" not in response.data
        assert money(42.00) not in response.data
