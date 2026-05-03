# apps/notifications/models.py
# ─────────────────────────────────────────────────────────────
# NOTIFICATIONS MODELS
# Notification     — in-app notification per user
# EmailLog         — every email sent logged here
# ─────────────────────────────────────────────────────────────

from django.db import models
from django.conf import settings


class Notification(models.Model):
    """
    In-app notifications — the bell icon in navbar.
    Every event that needs user attention creates one of these.

    Buyer notifications:
    - Order confirmed, shipped, delivered
    - Dispute status update
    - Refund processed
    - Price drop on wishlist item

    Seller notifications:
    - New order received
    - Dispute opened against them
    - Strike issued
    - Subscription expiring (30d/7d/1d)
    - Low stock alert
    - Product auto-deleted

    Admin notifications:
    - New seller pending approval
    - Dispute escalated
    - Reserve fund low
    - Suspicious payment flagged
    """

    class NotificationType(models.TextChoices):
        # ── BUYER ────────────────────────────────────────────
        ORDER_CONFIRMED     = 'order_confirmed',     'Order Confirmed'
        ORDER_SHIPPED       = 'order_shipped',       'Order Shipped'
        ORDER_DELIVERED     = 'order_delivered',     'Order Delivered'
        ORDER_CANCELLED     = 'order_cancelled',     'Order Cancelled'
        DISPUTE_UPDATE      = 'dispute_update',      'Dispute Status Update'
        REFUND_PROCESSED    = 'refund_processed',    'Refund Processed'
        PRICE_DROP          = 'price_drop',          'Price Drop on Wishlist'
        REVIEW_REMINDER     = 'review_reminder',     'Leave a Review'
        POD_ALLOWANCE_LOW   = 'pod_allowance_low',   'POD Allowance Running Low'

        # ── SELLER ───────────────────────────────────────────
        NEW_ORDER           = 'new_order',           'New Order Received'
        DISPUTE_OPENED      = 'dispute_opened',      'Dispute Opened Against You'
        STRIKE_ISSUED       = 'strike_issued',       'Strike Issued'
        SUB_EXPIRING_30     = 'sub_expiring_30',     'Subscription Expiring in 30 Days'
        SUB_EXPIRING_7      = 'sub_expiring_7',      'Subscription Expiring in 7 Days'
        SUB_EXPIRING_1      = 'sub_expiring_1',      'Subscription Expiring Tomorrow'
        SUB_EXPIRED         = 'sub_expired',         'Subscription Expired'
        STORE_SUSPENDED     = 'store_suspended',     'Store Suspended'
        LOW_STOCK           = 'low_stock',           'Product Low Stock'
        PRODUCT_DELETED     = 'product_deleted',     'Product Auto-Deleted'
        NEW_REVIEW          = 'new_review',          'New Product Review'
        PAYOUT_PROCESSED    = 'payout_processed',    'Payout Processed'
        FEATURED_EXPIRING   = 'featured_expiring',   'Featured Listing Expiring'

        # ── ADMIN ────────────────────────────────────────────
        SELLER_PENDING      = 'seller_pending',      'New Seller Pending Approval'
        DISPUTE_ESCALATED   = 'dispute_escalated',   'Dispute Escalated to Admin'
        RESERVE_FUND_LOW    = 'reserve_fund_low',    'Reserve Fund Below Threshold'
        STRIKE_THRESHOLD    = 'strike_threshold',    'Seller Reached Strike Threshold'
        SUSPICIOUS_PAYMENT  = 'suspicious_payment',  'Suspicious Payment Flagged'
        APPEAL_SUBMITTED    = 'appeal_submitted',    'Ban Appeal Submitted'
        WEBHOOK_FAILED      = 'webhook_failed',      'Payment Webhook Failed'

    # ── RECIPIENT ────────────────────────────────────────────
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    # ── CONTENT ──────────────────────────────────────────────
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices
    )
    title = models.CharField(
        max_length=100,
        help_text='Short title shown in notification bell dropdown'
    )
    message = models.TextField(
        help_text='Full notification message'
    )
    # Optional link — clicking notification takes user here
    link = models.CharField(
        max_length=255,
        blank=True,
        help_text='URL to navigate to when notification clicked'
    )

    # ── STATUS ───────────────────────────────────────────────
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # ── RELATED OBJECTS ──────────────────────────────────────
    # Generic references so we can link to any related object
    # eg order_ref for order notifications
    related_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='ID of related object eg order ID, dispute ID'
    )
    related_object_type = models.CharField(
        max_length=50,
        blank=True,
        help_text='Type of related object eg order, dispute, product'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.recipient.email} — {self.title}'

    def mark_read(self):
        """Mark notification as read"""
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class EmailLog(models.Model):
    """
    Every email sent by the platform logged here.
    Useful for:
    - Debugging email delivery issues
    - Preventing duplicate emails
    - Audit trail for compliance

    Celery tasks check this before sending
    subscription warning emails to avoid duplicates.
    """

    class EmailStatus(models.TextChoices):
        SENT    = 'sent',    'Sent Successfully'
        FAILED  = 'failed',  'Failed to Send'
        PENDING = 'pending', 'Pending'

    recipient_email = models.EmailField()
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='email_logs'
    )
    subject = models.CharField(max_length=255)
    # Email type matches NotificationType for consistency
    email_type = models.CharField(
        max_length=30,
        help_text='Type of email — matches notification type'
    )
    status = models.EmailStatus if hasattr(
        models, 'EmailStatus'
    ) else models.CharField(
        max_length=10,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING
    )
    status = models.CharField(
        max_length=10,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING
    )
    # Error message if failed
    error_message = models.TextField(blank=True)
    # Reference to related object eg order_ref
    reference = models.CharField(max_length=100, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Email Log'
        verbose_name_plural = 'Email Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient_email', 'email_type']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.email_type} → {self.recipient_email} ({self.status})'