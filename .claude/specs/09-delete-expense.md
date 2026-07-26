# Spec: Delete Expense

## Overview
This feature allows users to permanently remove expenses they've created. Users can delete an expense via a button in the transaction list with a confirmation prompt to prevent accidental deletions. This feature completes the full CRUD lifecycle for expenses — users can now add, view, edit, and delete their transactions as needed.

## Depends on
- Step 2: Registration
- Step 3: Login and Logout
- Step 4: Profile Page
- Step 7: Add Expense
- Step 8: Edit Expense

## Routes
- `POST /expenses/<id>/delete` — delete an expense, with ownership and existence checks — logged-in only

No GET route for delete — deletions happen via form submission only, not by navigating to a URL.

## Database changes
No new tables or columns. The feature uses `DELETE FROM expenses WHERE id = ? AND user_id = ?` to remove the row.

## Templates
- **Create:** None
- **Modify:** `templates/profile.html` — add a delete button/form in the Actions cell alongside the edit link

## Files to change
- `app.py` — implement POST handler for `/expenses/<id>/delete` route
- `templates/profile.html` — add delete button/form in Actions column

## Files to create
None (but may add `static/js/confirm-delete.js` if a custom confirmation modal is desired; optional).

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders in SQL)
- Passwords hashed with werkzeug (N/A for this feature)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Delete action must be form-based (POST, not a plain `<a>` link) to prevent accidental deletion via browser prefetch or crawlers
- Enforce ownership: users can only delete expenses they created
- Return 404 if expense ID does not exist
- Return 403 if expense exists but belongs to a different user
- Redirect to `/profile` after successful deletion
- Provide a confirmation before deletion (either via form button with `onclick` confirmation dialog or via a separate JavaScript handler)
- Reuse existing validation patterns from add_expense and edit_expense for consistency

## Definition of done
- [ ] User can see a delete button/form in the Actions column on the profile page
- [ ] Clicking the delete button triggers a confirmation prompt
- [ ] User can confirm or cancel the deletion
- [ ] On confirmation, the expense is permanently removed from the database
- [ ] User is redirected to `/profile` after successful deletion
- [ ] Invalid expense ID returns 404
- [ ] User cannot delete expenses belonging to other users (403 response)
- [ ] Unauthenticated users are redirected to login (via @login_required)
- [ ] On profile page, the transaction row no longer appears after deletion (without page refresh)
- [ ] The stats (total spent, transaction count, top category) update correctly after deletion
- [ ] Delete button styling matches the Edit button styling (reuse .btn-ghost or similar class)
