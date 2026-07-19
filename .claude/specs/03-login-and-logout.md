# Spec: Login and Logout

## Overview
Step 03 implements user authentication and session management. Users can log in with their email and password, and their session is maintained across pages until they log out. This is a critical stepping stone before implementing the expense dashboard in Step 04, as all protected routes will require an authenticated session.

## Depends on
- **Step 01 — Database Setup**: `database/db.py` must define `get_db()`, `init_db()`, and seed sample users
- **Step 02 — Registration**: Users table must exist with `id`, `email`, `password_hash`, `created_at` columns; `POST /register` must work and store users securely

## Routes

- `POST /login` — authenticate a user by email/password, create session, redirect to dashboard or profile (public)
- `GET /logout` — clear session, redirect to landing page (logged-in only)

Both routes inherit GET behavior from existing routes; only POST and GET /logout are implemented here.

## Database changes

No new tables or columns. Assumes `users` table from Step 02 with:
- `id` (primary key)
- `email` (unique)
- `password_hash` (hashed with werkzeug)
- `created_at`

## Templates

- **Modify:** `login.html` — add form with POST action to `/login`, fields: email, password
- **Modify:** `base.html` — add navigation bar showing logged-in user; link to `/logout` if session exists; show "Register | Login" if not
- **Modify:** `landing.html` — optional: hide "Sign up / Log in" button if user is logged in

## Files to change

- `app.py` — add `POST /login` handler, modify `GET /logout` handler, add session setup
- `templates/login.html` — add form and styling
- `templates/base.html` — add header/nav with conditional logout link
- `templates/landing.html` — optional: conditional CTAs based on login state

## Files to create

None.

## New dependencies

No new pip packages; Flask session support is built-in with `from flask import session`.

## Rules for implementation

- Use Flask's built-in `session` object for storing user ID; set `SECRET_KEY` on app before use
- All form submissions must be `POST` with `method="POST"` in template
- Password verification must use `werkzeug.security.check_password_hash()` — never plain text comparison
- Parameterized queries only (`?` placeholders); never f-strings or string concatenation in SQL
- Redirect after POST (POST/Redirect/GET pattern) to prevent double-submission
- All HTML templates must extend `base.html`
- Use `url_for()` for all internal links; never hardcode paths like `/login`
- Session timeout or persistence can be left as Flask defaults for now
- Authentication state must be checked with `if "user_id" in session` before allowing protected routes

## Definition of done

- [ ] User can fill login form on GET `/login` and see email + password fields
- [ ] Submitting login form sends POST request to `/login`
- [ ] Correct email/password combo authenticates user, creates session, redirects to `/profile` (or dashbard)
- [ ] Wrong email/password shows error message on login page (or 401 Unauthorized)
- [ ] Logged-in user sees their email in the navigation bar
- [ ] Clicking "Log out" clears session and redirects to landing page
- [ ] Accessing protected routes (e.g., `/profile`, `/expenses/*`) without session redirects to `/login`
- [ ] All forms use POST method with `url_for()`
- [ ] No passwords are logged or exposed in error messages
- [ ] No new pip packages added; all Flask builtins used
