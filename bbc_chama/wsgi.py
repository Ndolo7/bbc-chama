import os
from django.core.wsgi import get_wsgi_application

django_env = os.environ.get('DJANGO_ENV', 'dev')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'bbc_chama.settings.{django_env}')

application = get_wsgi_application()
