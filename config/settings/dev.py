# config/settings/dev.py
# ─────────────────────────────────────────────────────────────
# DEVELOPMENT SETTINGS
# These settings are for your local machine only
# Never use these in production
# ─────────────────────────────────────────────────────────────

from .base import *  # import everything from base.py first

# ── DEBUG ────────────────────────────────────────────────────
# True in dev — shows detailed error pages
# NEVER True in production — exposes your code to the world
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# ── DATABASE ─────────────────────────────────────────────────
# Local PostgreSQL database for development
import dj_database_url
DATABASES = {
    'default': dj_database_url.config(
        default=env('DATABASE_URL'),
        conn_max_age=600,
    )
}

# ── EMAIL IN DEV ─────────────────────────────────────────────
# In development print emails to terminal instead of actually sending
# This way you can see verification emails without a real email setup yet
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
DEFAULT_CHARSET = 'utf-8'

# ── DJANGO DEBUG TOOLBAR (optional but useful) ───────────────
INTERNAL_IPS = ['127.0.0.1']

# ── CORS IN DEV ──────────────────────────────────────────────
# Allow all origins in development — locked down in prod
CORS_ALLOW_ALL_ORIGINS = True