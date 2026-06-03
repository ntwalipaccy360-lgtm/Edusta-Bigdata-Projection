---
name: Role-based dashboards
description: How the 4-role system works — UserProfile model, context processor, router, and sidebar logic.
---

## Roles
- `system_admin` — superuser flag OR profile.role='system_admin'; sees admin_system.html with user/system health panel
- `school_admin` — sees full analytics (overview.html, risk tracker, graduation, insights, data mgmt)
- `teacher` — sees staff_dashboard.html (class list, risk tracker, students, graduation)
- `student` — sees student_dashboard.html (personal grades only)

## Router
`performance/views.py` → `_get_user_role(user)` → `analytics_dashboard()` dispatches to correct private function.

## Context processor
`accounts/context_processors.user_role` injects `user_role` string into every template. Added to `TEMPLATES.context_processors` in `edustat/settings/base.py`.

## Sidebar
`templates/base.html` uses `{% if user_role == 'system_admin' %}...{% elif %}` blocks — each role sees only its own nav items.

**Why:** Role separation prevents students from accessing analytics, and prevents teachers from accessing system admin functions. Context processor is cleaner than repeating `user.profile.role` in every template with exception handling.

## UserProfile model
`accounts/models.py` — `UserProfile` OneToOneField on User. Signal `create_or_update_user_profile` auto-creates profile on User creation. Existing users need manual backfill via shell.
