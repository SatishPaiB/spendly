# Spec: Registration

## Overview
Implement the user registration flow that allows new users to create an account.
This feature validates user input, hashes passwords securely, stores new users in the database, and handles duplicate email errors.
Registration is a prerequisite for the login system (Step 3) and all protected pages that follow.

## Depends on
- Step 1: Database Setup — requires `users` table and `get_db()`, `init_db()`, `seed_db()` functions

## Routes
- `POST /register` — Accept registration form submission, validate input, create user account, redirect to login or show error — public

## Database changes
No new tables or columns. Uses existing `users` table created in Step 1.

## Templates
- **Modify:** `register.html` — already has a POST form with fields for name, email, password; implementation must display form errors if present

## Files to change
- `app.py` — add POST /register route handler
- `database/db.py` — add `create_user()` helper function

## Files to create
None

## New dependencies
No new dependencies. Uses `werkzeug.security.generate_password_hash` (already imported in `database/db.py`).

## Rules for implementation
- No SQLAlchemy or ORMs — use raw sqlite3
- Parameterised queries only — never use f-strings in SQL
- Passwords must be hashed with `werkzeug.security.generate_password_hash()`
- Email validation: check that email doesn't already exist in database before inserting
- Input validation: check that name, email, and password are non-empty strings
- Password constraint: must be at least 8 characters
- Error handling: use `abort(400)` for client errors (bad input), render template with error message for duplicate email
- All templates must extend `base.html`
- Successful registration redirects to `/login` with a redirect response (HTTP 302)

## Definition of done
- [ ] POST /register route exists and handles form submission
- [ ] Form fields (name, email, password) are validated before database insert
- [ ] Password length is at least 8 characters; error shown if too short
- [ ] Email uniqueness is enforced; duplicate email shows error message (not a 500)
- [ ] Password is hashed before storage using `werkzeug.security.generate_password_hash()`
- [ ] Successful registration redirects to `/login`
- [ ] Form errors (if any) are re-rendered on `/register` template with error message visible
- [ ] `create_user()` function exists in `database/db.py` and uses parameterized queries
- [ ] No raw string concatenation in SQL queries
- [ ] App starts without errors
- [ ] All validation runs before database inserts
