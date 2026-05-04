# apps/accounts/tasks.py
# ─────────────────────────────────────────────────────────────
# ACCOUNTS CELERY TASKS
# reset_pod_allowances — resets POD monthly limits on 1st of month
# ─────────────────────────────────────────────────────────────

from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def reset_pod_allowances():
    """
    Runs on 1st of every month at midnight.
    Resets POD count for all users.
    Monthly strikes (2 = suspended for month) also reset.
    Cumulative strikes (3 = permanent revocation) do NOT reset.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Reset monthly POD count for all users
    updated = User.objects.filter(
        pod_count_this_month__gt=0
    ).update(pod_count_this_month=0)

    # Clear monthly suspension (pod_suspended_until)
    # Only if suspension date has passed
    from django.utils import timezone
    User.objects.filter(
        pod_suspended_until__isnull=False,
        pod_suspended_until__lt=timezone.now().date(),
    ).update(pod_suspended_until=None)

    logger.info(
        f'reset_pod_allowances: reset POD counts for {updated} users'
    )
    return f'Reset POD allowances for {updated} users'