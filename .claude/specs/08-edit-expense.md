# Spec: Edit Expense

## Overview
This feature allows users to modify existing expenses they've created. Users can access an edit form for any expense, update the amount, category, date, and description, and save the changes back to the database. This feature enables expense management and correction after initial entry — a necessary complement to the Add Expense feature built in Step 7.

## Depends on
- Step 2: Registration
- Step 3: Login and Logout
- Step 4: Profile Page
- Step 7: Add Expense

## Routes
- `GET /expenses/<id>/edit` — render form to edit an expense with pre-filled values — logged-in only
- `POST /expenses/<id>/edit` — validate and save edited expense, redirect to profile — logged-in only

## Database changes
No database changes. The `expenses` table already has all necessary columns:
- `id` (primary key)
- `user_id` (foreign key to users)
- `amount` (REAL)
- `category` (TEXT)
- `date` (TEXT, YYYY-MM-DD)
- `description` (TEXT, optional)

## Templates
- **Create:** `templates/expenses/edit.html` — edit expense form, pre-filled with existing expense data
- **Modify:** None

## Files to change
- `app.py` — implement GET and POST handlers for `/expenses/<id>/edit` route

## Files to create
- `templates/expenses/edit.html` — edit expense form template

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders in SQL)
- Passwords hashed with werkzeug (N/A for this feature)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Enforce ownership: users can only edit expenses they created
- Validate all input (amount, category, date format, description length if any)
- Return 404 if expense ID does not exist
- Return 403 if expense exists but belongs to a different user
- Reuse the `CATEGORY_MAPPING` and validation helpers from `add_expense()` for consistency

## Definition of done
- [ ] User can navigate to `/expenses/<id>/edit` for a valid expense they own
- [ ] GET request renders a form pre-filled with the expense's current amount, category, date, and description
- [ ] Form has the same category dropdown, date picker, and validation as the add expense form
- [ ] User can modify any field (amount, category, date, description)
- [ ] POST request validates input with the same rules as add expense (amount must be positive, category must be valid, date must be YYYY-MM-DD)
- [ ] On validation error, form re-renders with error message and retains user input
- [ ] On success, expense is updated in the database and user is redirected to `/profile`
- [ ] User cannot access or edit expenses belonging to other users (403 response or redirect)
- [ ] Invalid expense ID returns 404
- [ ] Form styling matches the add expense form
- [ ] Template extends `base.html`
