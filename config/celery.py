# config/celery.py
# ─────────────────────────────────────────────────────────────
# CELERY CONFIGURATION
# Celery is our background task runner.
# Handles: subscription checks, product auto-delete,
# email sending, price drop alerts, POD resets etc.
# ─────────────────────────────────────────────────────────────

import os
from celery import Celery
from celery.schedules import crontab

# Tell Celery which Django settings to use
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

app = Celery('nexo')

# Read Celery config from Django settings
# All Celery settings in settings.py start with CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
# Looks for tasks.py in every app
app.autodiscover_tasks()

# ── SCHEDULED TASKS (Celery Beat) ────────────────────────────
# These run automatically on schedule
app.conf.beat_schedule = {

    # Check subscriptions daily at midnight WAT
    'check-subscriptions-daily': {
        'task': 'apps.stores.tasks.check_subscription_expiry',
        'schedule': crontab(hour=0, minute=0),
    },

    # Check out-of-stock products daily at 1am WAT
    'check-product-restock-daily': {
        'task': 'apps.products.tasks.check_restock_deadlines',
        'schedule': crontab(hour=1, minute=0),
    },

    # Reset POD monthly allowances on 1st of every month
    'reset-pod-monthly': {
        'task': 'apps.accounts.tasks.reset_pod_allowances',
        'schedule': crontab(hour=0, minute=0, day_of_month=1),
    },

    # Check price drops for wishlists daily at 9am WAT
    'check-price-drops-daily': {
        'task': 'apps.products.tasks.check_price_drops',
        'schedule': crontab(hour=9, minute=0),
    },

    # Auto-delete expired seller accounts (60 days after expiry)
    'cleanup-expired-sellers-weekly': {
        'task': 'apps.stores.tasks.cleanup_expired_sellers',
        'schedule': crontab(hour=2, minute=0, day_of_week=1),
    },

    # Reset monthly seller revenue counters
    'reset-seller-monthly-revenue': {
        'task': 'apps.stores.tasks.reset_monthly_revenue',
        'schedule': crontab(hour=0, minute=0, day_of_month=1),
    },
}