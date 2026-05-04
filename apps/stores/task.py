# apps/stores/tasks.py
# ─────────────────────────────────────────────────────────────
# STORES CELERY TASKS
# check_subscription_expiry  — warns + expires subscriptions
# cleanup_expired_sellers    — deletes accounts 60 days after expiry
# reset_monthly_revenue      — resets seller revenue counters monthly
# ─────────────────────────────────────────────────────────────

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_subscription_expiry():
    """
    Runs daily at midnight.
    Checks all active subscriptions:
    - 30 days left → warning email
    - 7 days left  → urgent email
    - 1 day left   → critical email
    - Expired      → store goes invisible
    """
    from .models import Subscription, SellerProfile
    from django.core.mail import send_mail
    from django.conf import settings

    today = timezone.now().date()
    processed = 0

    for sub in Subscription.objects.filter(
        status=Subscription.Status.ACTIVE
    ).select_related('seller__user'):

        days_left = (sub.end_date - today).days
        seller = sub.seller
        user = seller.user

        # ── 30 DAY WARNING ───────────────────────────────────
        if days_left == 30 and not sub.warning_30_sent:
            _send_subscription_warning(
                user, seller, days_left, 'green'
            )
            sub.warning_30_sent = True
            sub.save(update_fields=['warning_30_sent'])
            processed += 1

        # ── 7 DAY WARNING ────────────────────────────────────
        elif days_left == 7 and not sub.warning_7_sent:
            _send_subscription_warning(
                user, seller, days_left, 'yellow'
            )
            sub.warning_7_sent = True
            sub.save(update_fields=['warning_7_sent'])
            processed += 1

        # ── 1 DAY WARNING ────────────────────────────────────
        elif days_left == 1 and not sub.warning_1_sent:
            _send_subscription_warning(
                user, seller, days_left, 'red'
            )
            sub.warning_1_sent = True
            sub.save(update_fields=['warning_1_sent'])
            processed += 1

        # ── EXPIRED ──────────────────────────────────────────
        elif days_left <= 0 and sub.status == Subscription.Status.ACTIVE:
            sub.status = Subscription.Status.EXPIRED
            sub.save(update_fields=['status'])

            # Hide store + all products
            seller.status = SellerProfile.StoreStatus.EXPIRED
            seller.is_approved = False
            seller.save(update_fields=['status', 'is_approved'])

            # Notify seller
            _notify_subscription_expired(user, seller)
            processed += 1

            logger.info(
                f'Subscription expired for store '
                f'"{seller.store_name}" — store hidden'
            )

    logger.info(
        f'check_subscription_expiry: processed {processed} subscriptions'
    )
    return f'Processed {processed} subscriptions'


@shared_task
def cleanup_expired_sellers():
    """
    Runs weekly on Monday at 2am.
    Deletes seller accounts expired for more than 60 days.
    Seller was warned multiple times before this point.
    """
    from .models import Subscription

    cutoff_date = timezone.now().date() - timedelta(days=60)

    expired_old = Subscription.objects.filter(
        status=Subscription.Status.EXPIRED,
        end_date__lt=cutoff_date,
    ).select_related('seller__user')

    deleted_count = 0
    for sub in expired_old:
        seller = sub.seller
        user = seller.user
        store_name = seller.store_name

        # Final notification before deletion
        _notify_account_deleted(user, store_name)

        # Delete user account (cascades to seller profile, products etc)
        user.delete()
        deleted_count += 1

        logger.info(
            f'Auto-deleted seller account: '
            f'"{store_name}" — 60 days after expiry'
        )

    logger.info(
        f'cleanup_expired_sellers: deleted {deleted_count} accounts'
    )
    return f'Deleted {deleted_count} expired seller accounts'


@shared_task
def reset_monthly_revenue():
    """
    Runs on 1st of every month at midnight.
    Resets monthly_revenue counter for all sellers.
    Used for commission tier calculation.
    """
    from .models import SellerProfile

    SellerProfile.objects.all().update(monthly_revenue=0)
    logger.info('reset_monthly_revenue: all seller monthly revenues reset')
    return 'Monthly revenues reset'


# ── HELPER FUNCTIONS ─────────────────────────────────────────

def _send_subscription_warning(user, seller, days_left, urgency):
    """Sends subscription expiry warning email to seller"""
    from django.core.mail import send_mail
    from django.conf import settings
    from apps.notifications.models import Notification

    if urgency == 'green':
        subject = f'Your Nexo store renews in {days_left} days'
        urgency_text = 'Heads up'
    elif urgency == 'yellow':
        subject = f'Action needed — Nexo store expires in {days_left} days'
        urgency_text = 'Important'
    else:
        subject = f'URGENT — Your Nexo store expires TOMORROW'
        urgency_text = 'Critical'

    message = (
        f'Hi {user.get_short_name()},\n\n'
        f'{urgency_text}: Your store "{seller.store_name}" subscription '
        f'expires in {days_left} day(s).\n\n'
        f'Renew now to keep your store visible to buyers:\n'
        f'{settings.FRONTEND_URL}/store/become-seller/\n\n'
        f'If you do not renew:\n'
        f'- Your store will become invisible to buyers\n'
        f'- After 60 days your account will be deleted\n\n'
        f'The Nexo Team'
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )

    # Also create in-app notification
    notif_type = {
        'green': 'sub_expiring_30',
        'yellow': 'sub_expiring_7',
        'red': 'sub_expiring_1',
    }[urgency]

    Notification.objects.create(
        recipient=user,
        notification_type=notif_type,
        title=subject,
        message=f'Your store subscription expires in {days_left} day(s). Renew now.',
        link='/store/renew/',
    )


def _notify_subscription_expired(user, seller):
    """Notifies seller their subscription expired"""
    from django.core.mail import send_mail
    from django.conf import settings
    from apps.notifications.models import Notification

    send_mail(
        subject='Your Nexo store is now offline',
        message=(
            f'Hi {user.get_short_name()},\n\n'
            f'Your store "{seller.store_name}" subscription has expired. '
            f'Your store is now hidden from buyers.\n\n'
            f'Renew your subscription to go live again:\n'
            f'{settings.FRONTEND_URL}/store/renew/\n\n'
            f'Note: If you do not renew within 60 days, '
            f'your account will be permanently deleted.\n\n'
            f'The Nexo Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )

    Notification.objects.create(
        recipient=user,
        notification_type='sub_expired',
        title='Your store subscription has expired',
        message=(
            f'Your store "{seller.store_name}" is now offline. '
            f'Renew your subscription to go live again.'
        ),
        link='/store/renew/',
    )


def _notify_account_deleted(user, store_name):
    """Final email before account deletion"""
    from django.core.mail import send_mail
    from django.conf import settings

    send_mail(
        subject='Your Nexo account has been deleted',
        message=(
            f'Hi {user.get_short_name()},\n\n'
            f'Your Nexo seller account and store "{store_name}" '
            f'have been permanently deleted due to 60 days of '
            f'inactivity after subscription expiry.\n\n'
            f'You are welcome to create a new account anytime.\n\n'
            f'The Nexo Team'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )