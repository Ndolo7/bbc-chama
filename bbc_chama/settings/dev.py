from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
    'demo': DEMO_DATABASE,  # noqa: F405
}

# Print emails to console in development instead of calling Brevo
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
