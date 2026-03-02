web: gunicorn bbc_chama.wsgi:application
worker: celery -A bbc_chama worker -l info
beat: celery -A bbc_chama beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
