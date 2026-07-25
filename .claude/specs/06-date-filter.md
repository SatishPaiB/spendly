# Spec: Date Filter for Profile Page

## Overview
This feature enhances the `/profile` page with the ability to filter transactions by a date range. Instead of displaying all historical expenses, users can now select a start and end date to view spending for a specific period. The profile stats (total spent, transaction count, top category) dynamically update based on the selected date range. This feature makes it easy for users to analyze their spending patterns over custom time periods and prepare for budgeting decisions.

## Depends on
- Step 1: Database setup (expenses table with date column must exist)
- Step 2: Registration (user accounts must be creatable)
- Step 3: Login + Logout (session must be set; `/profile` must be a protected route)
- Step 4: Profile Page (profile.html template and layout must exist)

## Routes
No new routes. Existing `GET /profile` is enhanced to accept optional query parameters:
- `GET /profile?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` — filter transactions within the date range

## Database changes
No new tables or columns. The existing `expenses` table is queried with date filtering using the existing `date` and `user_id` columns.

## Templates
- **Modify:** `templates/profile.html` — add a date filter form above the transaction history table with:
  1. Two date input fields (`start_date` and `end_date`)
  2. A "Filter" submit button
  3. A "Clear Filter" link to reset to all-time view
  4. Display the active date range in the transaction history section header

## Files to change
- `app.py` — modify the `/profile` route to:
  - Accept optional `start_date` and `end_date` query parameters
  - Query the database for actual user expenses instead of using hardcoded data
  - Filter expenses by user_id and date range (if provided)
  - Calculate stats (total_spent, transaction_count, top_category) from filtered expenses
  - Derive categories and their totals from filtered expenses (not hardcoded)
  - Pass filtered data to the template
- `database/db.py` — add a new helper function:
  - `get_expenses_by_user_and_date(user_id, start_date=None, end_date=None)` — returns list of expenses filtered by date range

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw sqlite3 via `get_db()` only
- Parameterised queries only — never string-format SQL or use f-strings in SQL
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Date format must be YYYY-MM-DD for both input and database queries
- If no date range is provided, show all expenses (no default date range)
- If only `start_date` is provided, filter from that date to today
- If only `end_date` is provided, filter from the earliest expense to that date
- Category breakdown must be derived from the filtered transaction set, not hardcoded
- Top category is determined by total amount spent in that category within the date range
- SQL queries must use parameterised `?` placeholders for all user input
- Date validation must happen on the backend (valid YYYY-MM-DD format, start_date <= end_date)

## Definition of done
- [ ] Visiting `/profile` without a date filter shows all expenses
- [ ] Date filter form is visible on the profile page with start_date and end_date inputs
- [ ] Entering a start_date and end_date and clicking "Filter" filters the transaction history to only show expenses within that range
- [ ] Summary stats (total_spent, transaction_count, top_category) update based on the filtered transactions
- [ ] Category breakdown updates to reflect only the categories present in the filtered transactions
- [ ] Clicking "Clear Filter" removes the filter and shows all expenses again
- [ ] If an invalid date range is provided (start_date > end_date), an error message is displayed
- [ ] If no expenses exist within the date range, a message is displayed ("No expenses in this date range")
- [ ] The page displays the active date range in the transaction history header (e.g., "Transactions (Jul 1 - Jul 31, 2026)")
- [ ] The database query uses parameterised queries with `?` placeholders for all date values
- [ ] Transactions are sorted by date in descending order (most recent first)
