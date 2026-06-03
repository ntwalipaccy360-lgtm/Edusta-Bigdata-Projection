---
name: Kiosk design
description: Public student self-service kiosk at /performance/kiosk/ — no login required, auto-clearing.
---

## URL
`/performance/kiosk/` — registered in `performance/urls.py`. No `@login_required`. POST form with `student_id` field.

## Template
`templates/performance/kiosk.html` — standalone (does NOT extend base.html), dark navy background (`#0a0f2e`), Rwanda flag gradient bar at top. After a successful lookup, a 30-second countdown JS timer auto-redirects back to the blank form.

## Lookup logic
Searches `Student.objects.filter(student_id__iexact=sid)` — case insensitive. Shows GPA, avg score, CA, attendance, course table, and prediction badge.

**Why:** Physical kiosk devices need no session management and must self-clear for privacy. Standalone template avoids sidebar/auth UI leaking into a public display.
