# config/settings/base.py
# ─────────────────────────────────────────────────────────────
# BASE SETTINGS — shared between dev and prod
# Both dev.py and prod.py import everything from here
# and only override what they need to change
# ─────────────────────────────────────────────────────────────

import environ
import os
from pathlib import Path

# ── PATH SETUP ───────────────────────────────────────────────
# Build paths inside the project like: BASE_DIR / 'subdir'
# BASE_DIR points to the nexo/ root folder where manage.py lives
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── ENVIRONMENT VARIABLES ────────────────────────────────────
# This reads our .env file so we never hardcode secrets in code
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

# ── SECURITY ─────────────────────────────────────────────────
# SECRET_KEY comes from .env — never hardcoded here
SECRET_KEY = env('SECRET_KEY')

# Email verification link expires in 15 minutes (900 seconds)
PASSWORD_RESET_TIMEOUT = 900

# Password reset = 10 minutes handled at view level
EMAIL_VERIFICATION_TIMEOUT = 900   # 15 mins
PASSWORD_RESET_TIMEOUT_SECONDS = 600  # 10 mins

# ── APPLICATION DEFINITION ───────────────────────────────────
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',        # required by django-allauth
    'django.contrib.humanize',     # formats numbers nicely eg ₦850,000
    'django.contrib.postgres'
]

THIRD_PARTY_APPS = [
    'rest_framework',              # Django REST Framework — API layer
    'rest_framework_simplejwt',    # JWT auth for Flutter mobile app
    'allauth',                     # Social login base
    'allauth.account',             # Allauth account management
    'allauth.socialaccount',       # Social account base
    'allauth.socialaccount.providers.google',  # Google OAuth
    'corsheaders',                 # Allows Flutter app to call our API
    'cloudinary',                  # Cloudinary SDK
    'cloudinary_storage',          # Makes Django use Cloudinary for uploads
    'django_celery_beat',          # Stores Celery schedules in database
    'django_filters',              # Filtering for DRF API
    'drf_spectacular',             # Auto API documentation
]

LOCAL_APPS = [
    'apps.accounts',               # Auth, profiles, banning
    'apps.stores',                 # Seller storefronts, subscriptions
    'apps.products',               # Products, variants, categories
    'apps.orders',                 # Cart, checkout, orders
    'apps.payments',               # Flutterwave, webhooks, audit
    'apps.disputes',               # Disputes, strikes, compensation
    'apps.dashboard',              # Seller + admin dashboards
    'apps.notifications',          # Email + in-app notifications
    'apps.core',                   # Homepage, search, currency, legal
]

# Django reads INSTALLED_APPS as one combined list
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── MIDDLEWARE ───────────────────────────────────────────────
# Middleware runs on every request/response in order
# ORDER MATTERS — do not rearrange these
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # serves static files in prod
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',        # CORS must be before CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',    # CSRF protection on all POST requests
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # prevents clickjacking
    'allauth.account.middleware.AccountMiddleware', # required by allauth
]

# ── URL CONFIGURATION ────────────────────────────────────────
ROOT_URLCONF = 'config.urls'

# ── TEMPLATES ────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],   # our templates/ folder
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.global_context',
            ],
        },
    },
]

# ── WSGI ─────────────────────────────────────────────────────
WSGI_APPLICATION = 'config.wsgi.application'

# ── PASSWORD VALIDATION ──────────────────────────────────────
# Django validates passwords against these rules
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── INTERNATIONALISATION ─────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'      # Nigerian timezone — all timestamps in WAT
USE_I18N = True
USE_TZ = True

# ── STATIC FILES ─────────────────────────────────────────────
# Static files = our CSS, JS, images we write
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']   # where we put our static files
STATIC_ROOT = BASE_DIR / 'staticfiles'     # where collectstatic puts them for prod
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── MEDIA FILES ──────────────────────────────────────────────
# Media = user uploaded files (local dev only — prod uses Cloudinary)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── DEFAULT PRIMARY KEY ──────────────────────────────────────
# Use BigAutoField for all models by default
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── CUSTOM USER MODEL ────────────────────────────────────────
# We use our own User model instead of Django's default
# This is defined in apps/accounts/models.py (Section 2)
AUTH_USER_MODEL = 'accounts.User'

# ── SITE ID ──────────────────────────────────────────────────
# Required by django-allauth
SITE_ID = 1

# ── AUTHENTICATION BACKENDS ──────────────────────────────────
# Tells Django to use both its own auth AND allauth for Google login
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ── DJANGO ALLAUTH CONFIG ────────────────────────────────────
ACCOUNT_LOGIN_METHODS = {'email'}          # login with email not username
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'   # must verify email before login
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[Nexo] '  # prefix on all auth emails
LOGIN_REDIRECT_URL = '/'                   # after login go to homepage
LOGOUT_REDIRECT_URL = '/'                  # after logout go to homepage
LOGIN_URL = '/auth/login/'
# Tell allauth we don't use username field at all
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
SOCIALACCOUNT_QUERY_EMAIL = True

# ── GOOGLE OAUTH ─────────────────────────────────────────────
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'CLIENT_ID': env('GOOGLE_CLIENT_ID', default=''),
        'SECRET': env('GOOGLE_CLIENT_SECRET', default=''),
        'OAUTH_PKCE_ENABLED': True,
    }
}

# When user logs in with Google:
# Auto-create account if email doesn't exist
# Auto-verify email — Google already verified it
# Skip additional signup form
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'

# ── DJANGO REST FRAMEWORK ────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Rate limiting — protects our API from abuse
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',    # guests — 100 requests per hour
        'user': '1000/hour',   # logged in users — 1000 per hour
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ── JWT SETTINGS ─────────────────────────────────────────────
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),   # access token expires in 1hr
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),      # refresh token lasts 7 days
    'ROTATE_REFRESH_TOKENS': True,                    # new refresh token on every use
    'BLACKLIST_AFTER_ROTATION': True,                 # old refresh tokens are blacklisted
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ── CLOUDINARY ───────────────────────────────────────────────
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': env('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': env('CLOUDINARY_API_KEY'),
    'API_SECRET': env('CLOUDINARY_API_SECRET'),
}
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# ── EMAIL ────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=465)
EMAIL_USE_TLS = False
EMAIL_USE_SSL = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='Nexo <nexo@nexo.ng>')

# ── CELERY ───────────────────────────────────────────────────
# Celery handles background tasks — subscription checks,
# auto-delete products, send emails, etc
CELERY_BROKER_URL = env('REDIS_URL')           # Redis as message broker
CELERY_RESULT_BACKEND = env('REDIS_URL')       # Redis stores task results
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Lagos'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# ── CORS ─────────────────────────────────────────────────────
# Allows Flutter mobile app to call our API
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

# ── FLUTTERWAVE ──────────────────────────────────────────────
FLUTTERWAVE_PUBLIC_KEY = env('FLUTTERWAVE_PUBLIC_KEY')
FLUTTERWAVE_SECRET_KEY = env('FLUTTERWAVE_SECRET_KEY')
FLUTTERWAVE_ENCRYPTION_KEY = env('FLUTTERWAVE_ENCRYPTION_KEY')

# ── FRONTEND URL ─────────────────────────────────────────────
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:8000')

# ── NEXO BUSINESS SETTINGS ───────────────────────────────────
# Commission thresholds (monthly revenue in NGN)
COMMISSION_TIERS = [
    (0,          500_000,   0),    # ₦0 – ₦500k     → 0% commission
    (500_000,    2_000_000, 3),    # ₦500k – ₦2M    → 3% commission
    (2_000_000,  10_000_000, 4),   # ₦2M – ₦10M     → 4% commission
    (10_000_000, float('inf'), 5), # ₦10M+           → 5% commission (max)
]

# Product restock window in days before auto-delete
PRODUCT_RESTOCK_DAYS = 14

# POD (Pay on Delivery) monthly limits per account age
POD_LIMITS = {
    'new': 2,          # account under 3 months
    'established': 5,  # account 3+ months
    'vip': 8,          # high order count, zero strikes
}