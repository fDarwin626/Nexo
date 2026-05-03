# config/settings/prod.py
# ─────────────────────────────────────────────────────────────
# PRODUCTION SETTINGS
# These settings only apply when deployed on Render/PythonAnywhere
# ─────────────────────────────────────────────────────────────

from .base import *   # import everything from base.py first
import dj_database_url

# ── DEBUG ────────────────────────────────────────────────────
DEBUG = False

# ── ALLOWED HOSTS ────────────────────────────────────────────
# Add your real domain here when deployed
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# ── DATABASE ─────────────────────────────────────────────────
# Production PostgreSQL — URL comes from Render environment variable
DATABASES = {
    'default': dj_database_url.config(
        default=env('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True,   # Render requires SSL on database connections
    )
}

# ── SECURITY HEADERS ─────────────────────────────────────────
# These headers protect users in production
SECURE_BROWSER_XSS_FILTER = True                  # blocks XSS attacks
SECURE_CONTENT_TYPE_NOSNIFF = True                # stops MIME type sniffing
SECURE_HSTS_SECONDS = 31536000                    # forces HTTPS for 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True                        # redirects HTTP to HTTPS
SESSION_COOKIE_SECURE = True                      # cookies only over HTTPS
CSRF_COOKIE_SECURE = True                         # CSRF only over HTTPS
X_FRAME_OPTIONS = 'DENY'                          # blocks clickjacking

# ── CORS IN PROD ─────────────────────────────────────────────
# Only allow your actual frontend domain
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS')

# ── STATIC FILES ─────────────────────────────────────────────
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'