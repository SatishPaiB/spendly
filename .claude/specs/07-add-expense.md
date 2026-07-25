# Spec: Add Expense

## Overview
Add Expense is Step 7 of Spendly's core expense tracking workflow. Users need a way to record new expenses with amount, category, date, and optional description. This feature provides a form-based interface for creating expenses and stores them in the database linked to the logged-in user.

## Depends on
- Step 2: Registration (users must exist)
- Step 3: Login and Logout (authentication required)
- Step 4: Profile (expense storage and display)
- Database: Expenses table must exist with `id, user_id, amount, category, date, description, created_at` columns

## Routes
- `GET /expenses/add` — Display expense creation form — logged-in users only
- `POST /expenses/add` — Handle expense form submission and create expense — logged-in users only

## Database changes
No new tables or schema changes needed. Uses existing `expenses` table and `CATEGORY_MAPPING` from app.py.

## Templates
**Create:**
- `templates/expenses/add.html` — Form template for creating a new expense

**Modify:**
- None

## Files to change
- `app.py` — Implement GET and POST routes for `/expenses/add`

## Files to create
- `templates/expenses/add.html` — Expense creation form template

## New dependencies
No new dependencies. Uses existing Flask, werkzeug, and SQLite.

## Rules for implementation

### Code style
- Python: PEP 8, snake_case for all variables and functions
- Templates: Jinja2 with `url_for()` for all internal links — never hardcode URLs
- No new pip packages without explicit approval
- Use `@login_required` decorator from existing codebase

### Database
- Always use parameterized queries with `?` placeholders — never f-strings in SQL
- Use `get_db()` helper function for database connections
- No SQLAlchemy ORM — raw SQL only

### Form validation
- Server-side validation only (no client-side validation)
- Validate required fields: amount, category, date
- Validate amount is a positive number
- Validate date format is YYYY-MM-DD using existing `is_valid_date()` function
- Validate category is one of the predefined categories from `CATEGORY_MAPPING`
- Description is optional — allow empty/null
- Re-render form with error message on validation failure (match existing error pattern from register/login)

### Template & styling
- Template must extend `base.html`
- Use existing form classes: `form-group`, `form-input`, `btn-submit`
- Use existing CSS variables for colors (--ink, --paper, --accent, etc.) — never hardcode hex values
- Match styling of register.html and login.html
- Page title block: "Add Expense — Spendly"

### Behavior
- Only logged-in users can access (protect with `@login_required`)
- On successful expense creation: redirect to `/profile` (match registration pattern)
- On validation error: re-render form with error message and preserve user input
- Expense date defaults to today (form can show date picker)
- Expense created_at is set to current timestamp automatically

## Definition of done
- [ ] GET `/expenses/add` returns 200 with form rendered (logged-in user)
- [ ] GET `/expenses/add` redirects to login for unauthorized users
- [ ] POST `/expenses/add` with valid data creates expense and redirects to profile
- [ ] POST `/expenses/add` with invalid amount shows error message
- [ ] POST `/expenses/add` with invalid date format shows error message
- [ ] POST `/expenses/add` with invalid category shows error message
- [ ] POST `/expenses/add` with missing required fields shows error message
- [ ] Form pre-fills with user input after validation error (except amount if invalid)
- [ ] Expense appears in profile page after creation
- [ ] All category options from `CATEGORY_MAPPING` are available in form dropdown
- [ ] Page title is "Add Expense — Spendly"
- [ ] Form styling matches register/login pages
- [ ] No new dependencies added to requirements.txt
