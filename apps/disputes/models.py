# apps/disputes/models.py
# ─────────────────────────────────────────────────────────────
# DISPUTES MODELS
# Dispute        — buyer opens against seller after bad order
# DisputeMessage — admin↔seller chat thread per dispute
# SellerStrike   — strike record issued to seller
# ─────────────────────────────────────────────────────────────

from django.db import models
from django.conf import settings


class Dispute(models.Model):
    """
    Buyer opens a dispute against a seller after a bad experience.

    Flow:
    1. Buyer opens dispute with evidence
    2. Seller gets 48hrs to respond
    3. Seller accepts → refund/replacement
    4. Seller refuses → escalates to admin
    5. Admin reviews both sides → binding decision
    6. Admin can issue strike, force refund, suspend store

    Only one dispute allowed per SellerOrder.
    """

    class Reason(models.TextChoices):
        BROKEN         = 'broken',         'Item Arrived Broken/Damaged'
        WRONG_ITEM     = 'wrong_item',     'Wrong Item Received'
        NOT_DESCRIBED  = 'not_described',  'Not as Described'
        NOT_DELIVERED  = 'not_delivered',  'Item Not Delivered'
        MISSING_PARTS  = 'missing_parts',  'Missing Parts/Accessories'

    class Status(models.TextChoices):
        OPEN             = 'open',             'Open — Awaiting Seller Response'
        SELLER_RESPONDED = 'seller_responded', 'Seller Responded'
        ESCALATED        = 'escalated',        'Escalated to Admin'
        RESOLVED_REFUND  = 'resolved_refund',  'Resolved — Refund Issued'
        RESOLVED_KEPT    = 'resolved_kept',    'Resolved — Buyer Keeps Item'
        RESOLVED_REPLACE = 'resolved_replace', 'Resolved — Replacement Sent'
        CLOSED           = 'closed',           'Closed'

    # ── RELATIONSHIPS ────────────────────────────────────────
    seller_order = models.OneToOneField(
        'orders.SellerOrder',
        on_delete=models.CASCADE,
        related_name='dispute',
        help_text='One dispute per seller order maximum'
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='disputes_raised'
    )
    seller = models.ForeignKey(
        'stores.SellerProfile',
        on_delete=models.CASCADE,
        related_name='disputes_received'
    )

    # ── DISPUTE DETAILS ──────────────────────────────────────
    reason = models.CharField(
        max_length=20,
        choices=Reason.choices
    )
    description = models.TextField(
        help_text='Buyer describes what went wrong in detail'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN
    )

    # ── EVIDENCE ─────────────────────────────────────────────
    evidence_photo_1 = models.ImageField(
        upload_to='disputes/evidence/',
        null=True,
        blank=True
    )
    evidence_photo_2 = models.ImageField(
        upload_to='disputes/evidence/',
        null=True,
        blank=True
    )
    evidence_photo_3 = models.ImageField(
        upload_to='disputes/evidence/',
        null=True,
        blank=True
    )
    evidence_video_url = models.URLField(
        blank=True,
        help_text='Optional video evidence link'
    )

    # ── SELLER RESPONSE ──────────────────────────────────────
    seller_response = models.TextField(
        blank=True,
        help_text='Seller response to the dispute'
    )
    seller_responded_at = models.DateTimeField(null=True, blank=True)

    # ── ADMIN RESOLUTION ─────────────────────────────────────
    admin_decision = models.TextField(
        blank=True,
        help_text='Admin final binding decision'
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='disputes_resolved',
        help_text='Admin who resolved this dispute'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    # ── COMPENSATION ─────────────────────────────────────────
    compensation_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Compensation amount issued to buyer in NGN'
    )
    compensation_source = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('seller',       'From Seller Payout'),
            ('reserve_fund', 'From Platform Reserve Fund'),
            ('both',         'Split Between Seller and Fund'),
        ],
        help_text='Where compensation money came from'
    )
    refund_fw_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text='Flutterwave refund transaction reference'
    )

    # ── DEADLINE ─────────────────────────────────────────────
    # Seller has 48 hours to respond
    # Celery checks this and auto-escalates if missed
    seller_response_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text='48hr deadline for seller to respond before auto-escalation'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dispute'
        verbose_name_plural = 'Disputes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['seller']),
            models.Index(fields=['buyer']),
        ]

    def __str__(self):
        return f'Dispute — {self.seller_order.order.order_ref} ({self.status})'

    @property
    def is_overdue(self):
        """True if seller missed their 48hr response window"""
        from django.utils import timezone
        if self.seller_response_deadline:
            return (
                self.status == self.Status.OPEN and
                timezone.now() > self.seller_response_deadline
            )
        return False


class DisputeMessage(models.Model):
    """
    Admin ↔ Seller chat thread per dispute.

    Rules:
    - Admin initiates — seller cannot start a thread
    - Seller can only REPLY to admin messages
    - All messages stored permanently as evidence
    - Thread auto-closes when dispute resolved

    This is NOT a general chat system.
    It only exists in the context of a dispute.
    """

    class SenderType(models.TextChoices):
        ADMIN  = 'admin',  'Admin'
        SELLER = 'seller', 'Seller'

    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dispute_messages'
    )
    sender_type = models.CharField(
        max_length=10,
        choices=SenderType.choices,
        help_text='Whether message is from admin or seller'
    )
    message = models.TextField()
    # Optional attachment — seller can upload counter-evidence
    attachment = models.ImageField(
        upload_to='disputes/messages/',
        null=True,
        blank=True
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Dispute Message'
        verbose_name_plural = 'Dispute Messages'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender_type} — Dispute {self.dispute.id} — {self.created_at}'


class SellerStrike(models.Model):
    """
    Strike record issued to a seller after dispute resolution.

    Strike ladder:
    1 strike  → Warning
    2 strikes → Forced refund from pending payouts
    3 strikes → Store suspended
    4 strikes → Permanent ban

    Strikes are permanent — never removed automatically.
    Only admin can remove a strike manually in exceptional cases.
    """

    class StrikeLevel(models.TextChoices):
        WARNING   = 'warning',   'Warning (Strike 1)'
        FORCED    = 'forced',    'Forced Refund (Strike 2)'
        SUSPENDED = 'suspended', 'Store Suspended (Strike 3)'
        BANNED    = 'banned',    'Permanently Banned (Strike 4)'

    seller = models.ForeignKey(
        'stores.SellerProfile',
        on_delete=models.CASCADE,
        related_name='strikes'
    )
    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        related_name='strikes'
    )
    level = models.CharField(
        max_length=10,
        choices=StrikeLevel.choices
    )
    reason = models.TextField(
        help_text='Detailed reason for this strike'
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='strikes_issued',
        help_text='Admin who issued this strike'
    )
    # Action taken as result of this strike
    action_taken = models.TextField(
        blank=True,
        help_text='eg Store suspended, ₦50,000 deducted from payout'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Seller Strike'
        verbose_name_plural = 'Seller Strikes'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.seller.store_name} — Strike {self.level}'