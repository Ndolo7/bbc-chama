import os
from celery import Celery
from celery.schedules import crontab

django_env = os.environ.get('DJANGO_ENV', 'dev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'bbc_chama.settings.{django_env}')

app = Celery('bbc_chama')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Scheduled tasks (EAT = UTC+3, so hour=5 in UTC equals 08:00 EAT)
app.conf.beat_schedule = {
    # Daily 08:00 EAT: remind non-payers between 3rd–15th of month
    'daily-contribution-reminder': {
        'task': 'chama.tasks.send_monthly_reminders',
        'schedule': crontab(hour=5, minute=0),
    },
    # 1st of month 08:00 EAT: send previous month's report
    'monthly-report': {
        'task': 'chama.tasks.send_monthly_report',
        'schedule': crontab(day_of_month=1, hour=5, minute=0),
    },
    # 28th of month 08:00 EAT: end-of-month heads-up reminder
    'end-of-month-reminder': {
        'task': 'chama.tasks.send_end_of_month_reminder',
        'schedule': crontab(day_of_month=28, hour=5, minute=0),
    },
}
