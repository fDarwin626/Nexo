# apps/payments/models.py
# ─────────────────────────────────────────────────────────────
# PAYMENTS MODELS
# PaymentLog       — every payment event logged (audit trail)
# ReserveFund      — platform compensation pool
# ReserveFundLog   — every transaction in/out of reserve fund
# ─────────────────────────────────────────────────────────────

from django.db import models
from django.conf import settings


class PaymentLog(models.Model):
    """
    Every payment event is logged here — success or failure.
    This is our audit trail and fraud detection source.

    Every Flutterwave webhook received gets stored here
    BEFORE we process it — so even if processing fails
    we have a record of what Flutterwave sent us.

    Idempotency: fw_reference is unique — if same webhook
    arrives twice (Flutterwave retries) we detect the duplicate
    and skip processing the second time.
    """

    class PaymentType(models.TextChoices):
        PURCHASE    = 'purchase',    'Product Purchase'
        SUBSCRIPTION = 'subscription', 'Seller Subscription'
        FEATURED    = 'featured',    'Featured Listing'
        REFUND      = 'refund',      'Refund'
        PAYOUT      = 'payout',      'Seller Payout'

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        SUCCESS   = 'success',   'Success'
        FAILED    = 'failed',    'Failed'
        REVERSED  = 'reversed',  'Reversed'
        DISPUTED  = 'disputed',  'Disputed'

    # ── FLUTTERWAVE DATA ─────────────────────────────────────
    # fw_reference is unique — prevents duplicate processing
    fw_reference = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text='Flutterwave transaction reference — unique per transaction'
    )
    fw_transaction_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Flutterwave internal transaction ID'
    )

    # ── RELATIONSHIPS ────────────────────────────────────────
    # Both nullable — payment may exist before order is created
    # eg webhook arrives before our order creation completes
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_logs'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_logs'
    )

    # ── PAYMENT DETAILS ──────────────────────────────────────
    payment_type = models.CharField(
        max_length=15,
        choices=PaymentType.choices,
        default=PaymentType.PURCHASE
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Amount in NGN'
    )
    currency = models.CharField(
        max_length=3,
        default='NGN',
        help_text='Currency code — NGN or USD'
    )

    # ── FRAUD DETECTION ──────────────────────────────────────
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP address of buyer at payment time'
    )
    device_fingerprint = models.CharField(
        max_length=255,
        blank=True,
        help_text='FingerprintJS hash at payment time'
    )

    # ── WEBHOOK DATA ─────────────────────────────────────────
    # Full raw webhook stored — useful for debugging
    # and replaying failed webhooks
    raw_webhook = models.JSONField(
        null=True,
        blank=True,
        help_text='Complete raw webhook payload from Flutterwave'
    )
    webhook_received_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When webhook arrived at our server'
    )

    # ── ORDER CREATION TRACKING ──────────────────────────────
    # Tracks if our order was successfully created
    # after payment confirmed.
    # If False after success status → admin needs to investigate
    order_created = models.BooleanField(
        default=False,
        help_text='True once order successfully created after payment'
    )

    # ── FAILURE DETAILS ──────────────────────────────────────
    failure_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text='Reason for failure from Flutterwave'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payment Log'
        verbose_name_plural = 'Payment Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['fw_reference']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_type']),
            models.Index(fields=['buyer']),
            models.Index(fields=['order_created', 'status']),
        ]

    def __str__(self):
        return f'{self.fw_reference} — {self.status} (₦{self.amount})'


class ReserveFund(models.Model):
    """
    Platform compensation pool.
    A small % of every Pay Now transaction feeds this fund.
    Used to compensate buyers when sellers can't or won't pay.

    Only one ReserveFund record exists — the singleton pattern.
    All transactions are logged in ReserveFundLog.
    """

    # Current balance in NGN
    balance = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text='Current reserve fund balance in NGN'
    )
    # Alert admin when balance falls below this threshold
    alert_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=50_000.00,
        help_text='Alert admin when balance drops below this amount'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Reserve Fund'
        verbose_name_plural = 'Reserve Fund'

    def __str__(self):
        return f'Reserve Fund — ₦{self.balance:,.2f}'


class ReserveFundLog(models.Model):
    """
    Every transaction in or out of the reserve fund.
    Provides complete audit trail for the compensation pool.
    """

    class TransactionType(models.TextChoices):
        CONTRIBUTION  = 'contribution',  'Contribution (% of sale)'
        DISBURSEMENT  = 'disbursement',  'Disbursement (buyer compensation)'
        MANUAL_ADD    = 'manual_add',    'Manual Addition (admin)'
        MANUAL_DEDUCT = 'manual_deduct', 'Manual Deduction (admin)'

    reserve_fund = models.ForeignKey(
        ReserveFund,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    transaction_type = models.CharField(
        max_length=15,
        choices=TransactionType.choices
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Amount in NGN — positive for additions, negative for deductions'
    )
    balance_after = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text='Reserve fund balance after this transaction'
    )
    # Reference to the order or dispute that triggered this
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text='Order ref or dispute ID that triggered this transaction'
    )
    note = models.TextField(
        blank=True,
        help_text='Admin note explaining this transaction'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Admin who made this transaction — null for automatic contributions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Reserve Fund Log'
        verbose_name_plural = 'Reserve Fund Logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.transaction_type} — ₦{self.amount} ({self.created_at.date()})'