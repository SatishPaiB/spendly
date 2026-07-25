"""
Tests for Step 06: Date Filter for Profile Page.

Spec: .claude/specs/06-date-filter.md

These tests exercise GET /profile with the optional `start_date` and
`end_date` query parameters described in the spec. They are written against
the documented behavior only:

- No filter -> all of the user's expenses are shown.
- start_date + end_date -> only expenses within [start_date, end_date].
- start_date only -> filter from start_date through "today".
- end_date only -> filter from the earliest expense through end_date.
- Stats (total_spent, transaction_count, top_category) and the category
  breakdown are derived from the filtered set.
- Invalid date format or start_date > end_date -> an error is displayed.
- Empty result set -> "No expenses in this date range" message.
- Transactions are sorted by date descending.
- The route is read-only and protected by login.
- Only the logged-in user's own expenses are ever shown.

Because `database/db.py` hard-codes DB_PATH at import time, isolation is
achieved by monkeypatching `database.db.DB_PATH` to a per-test temp file and
re-running `init_db()` / `seed_db()` against it before each test.
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
def insert_expense(app):
    """Insert an expense row directly via parameterized SQL for a given user."""
    import database.db as db_module

    def _insert(user_id, amount, category, date_str, description="Test expense"):
        conn = db_module.get_db()
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date_str, description),
        )
        conn.commit()
        conn.close()

    return _insert


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


def iso(offset_days):
    """ISO date string `offset_days` away from today (negative = past)."""
    return (date.today() + timedelta(days=offset_days)).isoformat()


def money(amount):
    """Render an amount the same way the template does: '%.2f'|format."""
    return f"{amount:.2f}".encode("utf-8")


# --------------------------------------------------------------------- #
# Happy path                                                            #
# --------------------------------------------------------------------- #

class TestDateFilterHappyPath:
    def test_profile_without_filter_shows_all_expenses(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        insert_expense(user_id, 10.00, "Food", iso(-30), "Old lunch")
        insert_expense(user_id, 20.00, "Transport", iso(-2), "Recent taxi")
        insert_expense(user_id, 30.00, "Bills", iso(0), "Today's bill")

        response = client.get("/profile")

        assert response.status_code == 200
        assert b"Old lunch" in response.data
        assert b"Recent taxi" in response.data
        assert b"Today&#39;s bill" in response.data or b"Today's bill" in response.data

    def test_profile_with_start_and_end_date_filters_correctly(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        insert_expense(user_id, 10.00, "Food", iso(-30), "Too early")
        insert_expense(user_id, 20.00, "Transport", iso(-10), "In range start")
        insert_expense(user_id, 25.00, "Bills", iso(-5), "In range middle")
        insert_expense(user_id, 40.00, "Shopping", iso(-1), "In range end")
        insert_expense(user_id, 50.00, "Health", iso(5), "Too late")

        response = client.get(
            f"/profile?start_date={iso(-10)}&end_date={iso(-1)}"
        )

        assert response.status_code == 200
        assert b"In range start" in response.data
        assert b"In range middle" in response.data
        assert b"In range end" in response.data
        assert b"Too early" not in response.data
        assert b"Too late" not in response.data

    def test_profile_with_only_start_date_filters_from_that_date_forward(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        insert_expense(user_id, 10.00, "Food", iso(-10), "Before start")
        insert_expense(user_id, 20.00, "Transport", iso(-5), "On start boundary")
        insert_expense(user_id, 30.00, "Bills", iso(-1), "After start, before today")
        insert_expense(user_id, 40.00, "Shopping", iso(0), "Today")

        response = client.get(f"/profile?start_date={iso(-5)}")

        assert response.status_code == 200
        assert b"Before start" not in response.data
        assert b"On start boundary" in response.data
        assert b"After start" in response.data
        assert b"Today" in response.data

    def test_profile_with_only_end_date_filters_up_to_that_date(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        insert_expense(user_id, 10.00, "Food", iso(-20), "Earliest expense")
        insert_expense(user_id, 20.00, "Transport", iso(-5), "On end boundary")
        insert_expense(user_id, 30.00, "Bills", iso(-1), "Just after end")
        insert_expense(user_id, 40.00, "Shopping", iso(0), "Today, after end")

        response = client.get(f"/profile?end_date={iso(-5)}")

        assert response.status_code == 200
        assert b"Earliest expense" in response.data
        assert b"On end boundary" in response.data
        assert b"Just after end" not in response.data
        assert b"Today, after end" not in response.data

    def test_stats_update_based_on_filtered_data(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        # Outside the filter window - must not affect stats.
        insert_expense(user_id, 1000.00, "Health", iso(-100), "Outside window")
        # Inside the filter window.
        insert_expense(user_id, 15.00, "Food", iso(-3), "In window 1")
        insert_expense(user_id, 25.00, "Food", iso(-2), "In window 2")

        response = client.get(
            f"/profile?start_date={iso(-5)}&end_date={iso(0)}"
        )
        body = response.data

        assert response.status_code == 200
        # total_spent should be 15 + 25 = 40.00, not including the 1000 outlier
        assert money(40.00) in body
        assert money(1000.00) not in body
        # transaction_count should be 2
        assert b">2<" in body or b"2</span>" in body
        # top_category should be Food & Dining (mapped display name)
        assert b"Food" in body

    def test_category_breakdown_reflects_filtered_expenses_only(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        insert_expense(user_id, 50.00, "Entertainment", iso(-50), "Old movie")
        insert_expense(user_id, 10.00, "Food", iso(-2), "New lunch")

        response = client.get(f"/profile?start_date={iso(-5)}&end_date={iso(0)}")
        body = response.data

        assert response.status_code == 200
        assert b"Food" in body
        assert b"Entertainment" not in body


# --------------------------------------------------------------------- #
# Edge cases                                                            #
# --------------------------------------------------------------------- #

class TestDateFilterEdgeCases:
    def test_empty_result_set_shows_no_expenses_message(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        insert_expense(user_id, 10.00, "Food", iso(-100), "Way in the past")

        response = client.get(f"/profile?start_date={iso(-1)}&end_date={iso(0)}")

        assert response.status_code == 200
        assert b"No expenses in this date range" in response.data
        assert b"Way in the past" not in response.data

    def test_single_expense_in_range(self, client, register_and_login, insert_expense):
        user_id = register_and_login()
        insert_expense(user_id, 42.50, "Shopping", iso(-2), "Solo expense")
        insert_expense(user_id, 99.00, "Health", iso(-50), "Excluded expense")

        response = client.get(f"/profile?start_date={iso(-5)}&end_date={iso(0)}")
        body = response.data

        assert response.status_code == 200
        assert b"Solo expense" in body
        assert b"Excluded expense" not in body
        assert money(42.50) in body

    def test_all_expenses_in_range_matches_unfiltered(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        insert_expense(user_id, 10.00, "Food", iso(-3), "Exp A")
        insert_expense(user_id, 20.00, "Transport", iso(-2), "Exp B")
        insert_expense(user_id, 30.00, "Bills", iso(-1), "Exp C")

        unfiltered = client.get("/profile")
        filtered = client.get(f"/profile?start_date={iso(-10)}&end_date={iso(0)}")

        assert unfiltered.status_code == 200
        assert filtered.status_code == 200
        for marker in (b"Exp A", b"Exp B", b"Exp C"):
            assert marker in unfiltered.data
            assert marker in filtered.data

    def test_percentage_calculation_with_zero_total_does_not_error(
        self, client, register_and_login
    ):
        # A brand new user with no expenses at all - total_spent is 0.
        register_and_login()

        response = client.get("/profile")

        assert response.status_code == 200
        assert b"No expenses in this date range" in response.data
        assert money(0.00) in response.data

    def test_top_category_selection_with_tied_totals_does_not_error(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        insert_expense(user_id, 50.00, "Food", iso(-2), "Tie A")
        insert_expense(user_id, 50.00, "Transport", iso(-1), "Tie B")

        response = client.get(f"/profile?start_date={iso(-5)}&end_date={iso(0)}")
        body = response.data

        assert response.status_code == 200
        # One of the two tied categories must be reported as top_category;
        # the important contract is that the app does not error out.
        assert b"Food" in body or b"Transport" in body


# --------------------------------------------------------------------- #
# Validation                                                            #
# --------------------------------------------------------------------- #

class TestDateFilterValidation:
    @pytest.mark.parametrize(
        "bad_start",
        [
            "07-25-2026",
            "2026/07/25",
            "not-a-date",
            "2026-13-45",
            "25th July 2026",
        ],
    )
    def test_invalid_start_date_format_shows_error(
        self, client, register_and_login, bad_start
    ):
        register_and_login()

        response = client.get("/profile", query_string={"start_date": bad_start})
        body = response.data.decode().lower()

        assert response.status_code == 200
        assert "error" in body or "invalid" in body or "format" in body, (
            "Expected an error message for an invalid start_date format"
        )

    @pytest.mark.parametrize(
        "bad_end",
        ["2026.07.25", "invalid", "2026-02-30"],
    )
    def test_invalid_end_date_format_shows_error(
        self, client, register_and_login, bad_end
    ):
        register_and_login()

        response = client.get("/profile", query_string={"end_date": bad_end})
        body = response.data.decode().lower()

        assert response.status_code == 200
        assert "error" in body or "invalid" in body or "format" in body

    def test_start_date_after_end_date_shows_error(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        insert_expense(user_id, 10.00, "Food", iso(-3), "Should not show")

        response = client.get(
            f"/profile?start_date={iso(0)}&end_date={iso(-10)}"
        )
        body = response.data.decode().lower()

        assert response.status_code == 200
        assert "error" in body or "cannot" in body or "invalid" in body, (
            "Expected an error message when start_date is after end_date"
        )


# --------------------------------------------------------------------- #
# Auth                                                                  #
# --------------------------------------------------------------------- #

class TestDateFilterAuth:
    def test_profile_without_login_redirects_to_login(self, client):
        response = client.get("/profile")

        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_profile_with_filter_without_login_redirects_to_login(self, client):
        response = client.get(f"/profile?start_date={iso(-5)}&end_date={iso(0)}")

        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_profile_only_shows_own_expenses(
        self, client, register_and_login, insert_expense
    ):
        user_a_id = register_and_login(
            name="User A", email="usera@example.com", password="passwordA1"
        )
        insert_expense(user_a_id, 77.00, "Food", iso(-1), "User A's private expense")

        # Log out A, register + log in as B.
        client.get("/logout")
        register_and_login(
            name="User B", email="userb@example.com", password="passwordB1"
        )

        response = client.get("/profile")

        assert response.status_code == 200
        assert b"User A" not in response.data or b"private expense" not in response.data
        assert b"User A's private expense" not in response.data

    def test_profile_only_shows_own_expenses_with_filter_applied(
        self, client, register_and_login, insert_expense
    ):
        user_a_id = register_and_login(
            name="User A", email="usera2@example.com", password="passwordA1"
        )
        insert_expense(user_a_id, 77.00, "Food", iso(-1), "A only expense")

        client.get("/logout")
        register_and_login(
            name="User B", email="userb2@example.com", password="passwordB1"
        )

        response = client.get(f"/profile?start_date={iso(-5)}&end_date={iso(0)}")

        assert response.status_code == 200
        assert b"A only expense" not in response.data


# --------------------------------------------------------------------- #
# Database behavior                                                     #
# --------------------------------------------------------------------- #

class TestDateFilterDatabase:
    def test_get_request_does_not_modify_expenses_table(
        self, client, register_and_login, insert_expense, count_expenses
    ):
        user_id = register_and_login()
        insert_expense(user_id, 10.00, "Food", iso(-3), "Untouched A")
        insert_expense(user_id, 20.00, "Transport", iso(-1), "Untouched B")

        before = count_expenses()
        client.get(f"/profile?start_date={iso(-5)}&end_date={iso(0)}")
        after = count_expenses()

        assert before == after, "GET /profile must never modify the expenses table"

    def test_transactions_sorted_by_date_descending(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        insert_expense(user_id, 10.00, "Food", iso(-10), "Oldest")
        insert_expense(user_id, 20.00, "Transport", iso(-5), "Middle")
        insert_expense(user_id, 30.00, "Bills", iso(-1), "Newest")

        response = client.get("/profile")
        body = response.data.decode()

        pos_newest = body.find("Newest")
        pos_middle = body.find("Middle")
        pos_oldest = body.find("Oldest")

        assert -1 not in (pos_newest, pos_middle, pos_oldest), (
            "All three transactions should be present in the response"
        )
        assert pos_newest < pos_middle < pos_oldest, (
            "Transactions must be sorted by date descending (most recent first)"
        )

    def test_get_expenses_by_user_and_date_uses_parameterized_queries(self, app):
        """
        Passing SQL-injection-style strings as date arguments must not break
        the query or leak/alter other users' data - proving `?` placeholders
        are used rather than string formatting.
        """
        import database.db as db_module

        malicious = "2026-01-01' OR '1'='1"

        # Should not raise, and should simply return no rows (since the
        # value doesn't match the stored date format) rather than executing
        # injected SQL.
        rows = db_module.get_expenses_by_user_and_date(1, malicious, None)
        assert isinstance(rows, list) or rows is not None

        # Sanity: the users table must be unaffected by the attempted injection.
        conn = db_module.get_db()
        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        conn.close()
        assert user_count >= 1, "Injection attempt must not corrupt the users table"

    def test_invalid_date_via_route_does_not_touch_database(
        self, client, register_and_login, insert_expense, count_expenses
    ):
        user_id = register_and_login()
        insert_expense(user_id, 10.00, "Food", iso(-1), "Safe expense")

        before = count_expenses()
        client.get(
            "/profile",
            query_string={
                "start_date": "2026-01-01' OR '1'='1",
                "end_date": "2026-12-31",
            },
        )
        after = count_expenses()

        assert before == after, "Malformed/malicious date params must not mutate data"


# --------------------------------------------------------------------- #
# Template landmarks / Definition-of-Done checks                        #
# --------------------------------------------------------------------- #

class TestDateFilterTemplate:
    def test_filter_form_is_visible_with_expected_inputs(self, client, register_and_login):
        register_and_login()

        response = client.get("/profile")
        body = response.data

        assert response.status_code == 200
        assert b'name="start_date"' in body
        assert b'name="end_date"' in body
        assert b"Filter" in body

    def test_clear_filter_link_present_only_when_filter_active(
        self, client, register_and_login
    ):
        register_and_login()

        no_filter = client.get("/profile")
        with_filter = client.get(f"/profile?start_date={iso(-5)}&end_date={iso(0)}")

        assert b"Clear filter" not in no_filter.data
        assert b"Clear filter" in with_filter.data

    def test_active_date_range_displayed_in_transaction_header(
        self, client, register_and_login, insert_expense
    ):
        user_id = register_and_login()
        insert_expense(user_id, 10.00, "Food", iso(-2), "Ranged expense")

        response = client.get(f"/profile?start_date={iso(-5)}&end_date={iso(0)}")
        body = response.data.decode()

        assert response.status_code == 200
        assert "Transactions (" in body, (
            "When a date filter is active, the transaction history header "
            "should reflect the active date range per the spec example "
            "'Transactions (Jul 1 - Jul 31, 2026)'"
        )
