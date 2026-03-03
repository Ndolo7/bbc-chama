from .base import *  # noqa: F401, F403
from decouple import config

import dj_database_url

DEBUG = False

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')

# ── Database (PostgreSQL) ────────────────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.parse(config('DATABASE_URL'))
}

# ── Email (Brevo API) ────────────────────────────────────────────────────────
EMAIL_BACKEND = 'anymail.backends.brevo.EmailBackend'

# ── Security ─────────────────────────────────────────────────────────────────
# SSL is terminated at the Nginx/load-balancer level, so Django itself does
# not need to redirect HTTP→HTTPS. Set SECURE_SSL_REDIRECT=True only if
# Django is exposed directly to the internet without a reverse proxy.
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
