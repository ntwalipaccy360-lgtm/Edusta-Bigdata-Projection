# EduStat - Student Performance Analytics Platform

## Overview
EduStat is a full-stack Django web application for monitoring student performance, identifying at-risk students, and leveraging machine learning for predictive analytics (pass/fail predictions).

## Architecture

- **Backend**: Django 5.1 (Python)
- **Database**: SQLite (dev), PostgreSQL (production via dj-database-url)
- **ML Stack**: scikit-learn, XGBoost, pandas, numpy
- **Frontend**: Tailwind CSS (v4, pre-compiled), Vanilla JavaScript
- **Static Files**: Served via WhiteNoise

## Project Structure

```
edustat/             - Django project config (settings, URLs, WSGI)
  settings/
    base.py          - Shared settings
    development.py   - Dev settings (SQLite, ALLOWED_HOSTS=*)
    production.py    - Production settings (gunicorn, PostgreSQL)
performance/         - Main app (ML models, analytics, student data)
  ml_models/         - Training pipeline and saved .pkl models
  services/          - Data import and analytics business logic
  management/        - Custom Django commands (train_engine, generate_data)
accounts/            - User authentication, user management
templates/           - HTML templates
  base.html          - Sidebar navigation with active state highlighting
  accounts/          - login, user_management, create_user
  performance/       - overview, risk_tracker, graduation_analytics, insights, ai_diagnostics
static/              - Static assets
  dist/css/style.css - Compiled Tailwind CSS
```

## Running Locally

**Settings module**: `DJANGO_SETTINGS_MODULE=edustat.settings.development`
**Port**: 5000 (webview)

## Navigation (Sidebar)
- Overview → /performance/
- Risk Tracker → /performance/risk-tracker/
- System Insights → /performance/insights/
- Graduation → /performance/graduation/
- Data Management → /performance/management/
- User Management → /accounts/users/ (admins only)

## Default Credentials
- **Username**: admin
- **Password**: admin123

## Creating New Users
- Log in as admin → click "User Management" in sidebar → "Create New User"
- Only superusers can create accounts

## Data
- Departments: IT, SE, CS, MGMT (and more)
- 950 academic records across 2023/2024 and 2025/2026 years
- 620 students

## Workflow
- **Start application**: `DJANGO_SETTINGS_MODULE=edustat.settings.development python manage.py runserver 0.0.0.0:5000`

## Deployment
- Target: autoscale
- Run: gunicorn with `edustat.wsgi:application` on port 5000
- Uses `edustat.settings.production` with ALLOWED_HOSTS for `.replit.app`

## Key Dependencies
- django==5.1.1, gunicorn, whitenoise, psycopg2-binary
- pandas, numpy, scikit-learn, xgboost, scipy, matplotlib, seaborn
- reportlab, python-docx, pypdf (document generation)
