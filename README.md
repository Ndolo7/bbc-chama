# BBC Chama

Internal Django app for tracking chama contributions, parsing payment SMS messages, and sending automated reminder/report emails.

## Features

- Member management (active/inactive members)
- Contribution tracking by month (one contribution per member per month)
- SMS parsing for:
  - M-Pesa confirmation messages
  - M-Pesa App payment messages
  - Cytonn deposit confirmations
- Dashboard with monthly status and charts
- Member-level and year-level reports
- Automated email jobs with Celery:
  - Reminder window (3rd-15th)
  - End-of-month reminder (28th)
  - Monthly report (1st of month)

## Tech Stack

- Python 3.11
- Django 5
- Celery + Redis
- PostgreSQL (production) / SQLite (development)
- Django Anymail (Brevo)
- Docker + Docker Compose

## Project Layout

- `bbc_chama/` Django project config (`settings/dev.py`, `settings/prod.py`, `celery.py`)
- `chama/` main app (models, views, parser, tasks, templates)
- `docker-compose.yml` local/dev multi-service stack
- `docker-compose.prod.yml` production stack
- `nginx/nginx.conf` reverse proxy config for production

## Environment Variables

Main variables used by this project:

- `DJANGO_ENV` (`dev` or `prod`)
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `CELERY_BROKER_URL`
- `BREVO_API_KEY`
- `DEFAULT_FROM_EMAIL`
- `ADMIN_EMAIL`

Notes:

- `dev` settings use SQLite and console email backend.
- `prod` settings use `DATABASE_URL` and Brevo email backend.
- `DJANGO_ENV` defaults to `dev` if not set.

## Local Development (Without Docker)

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set environment:

```bash
export DJANGO_ENV=dev
export SECRET_KEY="change-me"
```

4. Run migrations:

```bash
python manage.py migrate
```

5. Create admin user:

```bash
python manage.py createsuperuser
```

6. (Optional) Seed initial members:

```bash
python manage.py seed_members \
  --email-ndolo ndolo@example.com \
  --email-njau njau@example.com \
  --email-patrick patrick@example.com \
  --email-timothy timothy@example.com \
  --target 5000
```

7. Start server:

```bash
python manage.py runserver
```

Open:

- App: `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`

## Running Celery Locally

Start Redis, then run worker and beat in separate terminals:

```bash
celery -A bbc_chama worker -l info
celery -A bbc_chama beat -l info
```

Scheduled tasks are defined in [`bbc_chama/celery.py`](bbc_chama/celery.py).

## Docker (Local/Server)

Ensure a `.env` file exists with the variables listed above, then:

Bring up all services:

```bash
docker compose up -d
```

Run migrations:

```bash
docker compose exec web python manage.py migrate
```

Create superuser:

```bash
docker compose exec web python manage.py createsuperuser
```

The default compose stack starts:

- `web` (Django)
- `db` (PostgreSQL)
- `redis`
- `worker` (Celery worker)
- `beat` (Celery beat)

Open: `http://127.0.0.1:8001/`

## Production Notes

- Use `DJANGO_ENV=prod`.
- Set `DATABASE_URL` to PostgreSQL.
- Configure Brevo via `BREVO_API_KEY`.
- Ensure `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` are correct.
- Static files are collected at container startup (`entrypoint.sh`).

## Business Rules

- Each member can have at most one contribution per month.
- Contribution month is inferred as the month before the transaction date in parsed SMS flows.
- Monthly target comes from `MonthlyTarget` records, falling back to `CHAMA_MONTHLY_TARGET` in settings.

## CI/CD

GitHub Actions (`.github/workflows/ci-cd.yml`) runs:

- Lint + Django system checks on PRs/pushes to `main`
- Docker image build and push to GHCR on `main`
- VPS deploy via SSH on successful main-branch build
