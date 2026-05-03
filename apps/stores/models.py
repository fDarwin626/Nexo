# apps/stores/models.py
# ─────────────────────────────────────────────────────────────
# STORES MODELS
# SellerProfile    — the seller's store and business details
# Subscription     — rental plan (1m/6m/12m/24m)
# DeliveryZone     — which states the seller delivers to + fees
# FeaturedListing  — paid promotion slots
# ─────────────────────────────────────────────────────────────

from django.db import models
from django.utils.text import slugify
from django.conf import settings
import uuid


class SellerProfile(models.Model):
    """
    Every seller has one SellerProfile linked to their User account.
    This holds everything about their store — branding, payment
    details, Flutterwave subaccount, subscription status etc.
    """

    class AccountType(models.TextChoices):
        INDIVIDUAL = 'individual', 'Individual (BVN only)'
        BUSINESS   = 'business',   'Business (CAC registered)'

    class StoreStatus(models.TextChoices):
        PENDING   = 'pending',   'Pending Approval'
        ACTIVE    = 'active',    'Active'
        SUSPENDED = 'suspended', 'Suspended'
        EXPIRED   = 'expired',   'Subscription Expired'
        BANNED    = 'banned',    'Permanently Banned'

    # ── CORE RELATIONSHIP ────────────────────────────────────
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_profile',
        help_text='The user account this store belongs to'
    )

    # ── STORE IDENTITY ───────────────────────────────────────
    store_name = models.CharField(
        max_length=100,
        unique=True,
        help_text='Public name of the store eg Nike Store Lagos'
    )
    store_slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True,
        help_text='URL-friendly version of store name eg nike-store-lagos'
    )
    store_description = models.TextField(
        blank=True,
        help_text='Short bio shown on storefront eg Lagos-based Nike dealer'
    )
    logo = models.ImageField(
        upload_to='stores/logos/',
        blank=True,
        null=True,
        help_text='Store logo — shown on storefront and product cards'
    )

    # ── STOREFRONT CUSTOMISATION ─────────────────────────────
    # These are the fields sellers control (their 35%)
    banner_image = models.ImageField(
        upload_to='stores/banners/',
        blank=True,
        null=True,
        help_text='Campaign banner image shown at top of store page'
    )
    banner_headline = models.CharField(
        max_length=60,
        blank=True,
        help_text='Bold headline text on banner eg Premium Nike Footwear'
    )
    banner_subtext = models.CharField(
        max_length=120,
        blank=True,
        help_text='Secondary text eg Free delivery within Lagos'
    )
    banner_bg_color = models.CharField(
        max_length=7,
        default='#111118',
        help_text='Background color of banner in hex eg #FF4D00'
    )
    banner_accent_color = models.CharField(
        max_length=7,
        default='#FF4D00',
        help_text='Accent color for text highlights and buttons on banner'
    )

    # ── WHATSAPP ─────────────────────────────────────────────
    whatsapp_number = models.CharField(
        max_length=20,
        blank=True,
        help_text='Nigerian number with country code eg 2348012345678'
    )

    # ── BUSINESS VERIFICATION ────────────────────────────────
    account_type = models.CharField(
        max_length=10,
        choices=AccountType.choices,
        default=AccountType.INDIVIDUAL
    )
    bvn_verified = models.BooleanField(
        default=False,
        help_text='BVN verified via Flutterwave onboarding'
    )
    cac_number = models.CharField(
        max_length=20,
        blank=True,
        help_text='CAC registration number for business accounts'
    )
    cac_verified = models.BooleanField(
        default=False,
        help_text='CAC number verified by admin'
    )

    # ── BANK DETAILS ─────────────────────────────────────────
    bank_account_number = models.CharField(max_length=10, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    account_name = models.CharField(
        max_length=255,
        blank=True,
        help_text='Name on the bank account — must match BVN/CAC'
    )

    # ── FLUTTERWAVE SUBACCOUNT ───────────────────────────────
    # Created automatically when seller completes onboarding
    # Money goes directly here on every sale
    fw_subaccount_id = models.CharField(
        max_length=100,
        blank=True,
        help_text='Flutterwave subaccount ID — auto-created on approval'
    )
    fw_subaccount_code = models.CharField(
        max_length=100,
        blank=True,
        help_text='Flutterwave subaccount code used in payment splits'
    )

    # ── STORE STATUS ─────────────────────────────────────────
    status = models.CharField(
        max_length=10,
        choices=StoreStatus.choices,
        default=StoreStatus.PENDING
    )
    is_approved = models.BooleanField(
        default=False,
        help_text='Admin must approve before store goes live'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_stores',
        help_text='Admin who approved this store'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(
        blank=True,
        help_text='Reason shown to seller if application rejected'
    )

    # ── VACATION MODE ────────────────────────────────────────
    is_on_vacation = models.BooleanField(
        default=False,
        help_text='Store visible but cart disabled during vacation'
    )
    vacation_return_date = models.DateField(
        null=True,
        blank=True,
        help_text='Shown to buyers as expected return date'
    )

    # ── PAY ON DELIVERY ──────────────────────────────────────
    allow_pod = models.BooleanField(
        default=True,
        help_text='Seller can disable POD for their store entirely'
    )

    # ── STRIKE COUNT ─────────────────────────────────────────
    strike_count = models.PositiveIntegerField(
        default=0,
        help_text='Dispute strikes. 3 = suspension, 4 = permanent ban'
    )

    # ── RATINGS ──────────────────────────────────────────────
    # Auto-calculated from all product reviews
    # Never set manually
    rating_avg = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        help_text='Auto-calculated average of all product ratings'
    )
    rating_count = models.PositiveIntegerField(
        default=0,
        help_text='Total number of reviews across all products'
    )

    # ── COMMISSION ───────────────────────────────────────────
    current_commission_rate = models.PositiveIntegerField(
        default=0,
        help_text='Current commission % based on monthly revenue threshold'
    )
    monthly_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text='Running total for current month — reset by Celery monthly'
    )

    # ── TIMESTAMPS ───────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Seller Profile'
        verbose_name_plural = 'Seller Profiles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['store_slug']),
            models.Index(fields=['status']),
            models.Index(fields=['is_approved']),
        ]

    def __str__(self):
        return f'{self.store_name} ({self.status})'

    def save(self, *args, **kwargs):
        # Auto-generate slug from store name on first save
        if not self.store_slug:
            self.store_slug = slugify(self.store_name)
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return (
            self.is_approved and
            self.status == self.StoreStatus.ACTIVE and
            not self.is_on_vacation
        )

    @property
    def whatsapp_url(self):
        """Generates wa.me link with pre-filled message"""
        if self.whatsapp_number:
            return f'https://wa.me/{self.whatsapp_number}'
        return None


class Subscription(models.Model):
    """
    Seller subscription plans.
    Like renting a shop — pay for your space, space stays active.
    Celery checks daily and handles expiry automatically.
    """

    class Plan(models.TextChoices):
        MONTHLY    = '1m',  'Starter (1 Month)'
        BIANNUAL   = '6m',  'Standard (6 Months)'
        ANNUAL     = '12m', 'Pro (1 Year)'
        BIENNIAL   = '24m', 'Elite (2 Years)'

    class Status(models.TextChoices):
        ACTIVE    = 'active',    'Active'
        EXPIRED   = 'expired',   'Expired'
        CANCELLED = 'cancelled', 'Cancelled'

    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    plan = models.CharField(max_length=3, choices=Plan.choices)
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Amount paid in NGN'
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE
    )

    # ── DATES ────────────────────────────────────────────────
    start_date = models.DateField()
    end_date = models.DateField()

    # ── PAYMENT REFERENCE ────────────────────────────────────
    fw_transaction_ref = models.CharField(
        max_length=100,
        unique=True,
        help_text='Flutterwave transaction reference for this payment'
    )

    # ── WARNING EMAILS SENT FLAGS ────────────────────────────
    # Celery checks these to avoid sending duplicate warning emails
    warning_30_sent = models.BooleanField(default=False)
    warning_7_sent  = models.BooleanField(default=False)
    warning_1_sent  = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['end_date']),
        ]

    def __str__(self):
        return f'{self.seller.store_name} — {self.plan} ({self.status})'

    @property
    def days_remaining(self):
        from django.utils import timezone
        delta = self.end_date - timezone.now().date()
        return max(delta.days, 0)

    @property
    def urgency_level(self):
        """
        Used by frontend to colour the countdown bar:
        green  = more than 30 days
        yellow = 7-30 days
        red    = under 7 days
        """
        days = self.days_remaining
        if days > 30:
            return 'green'
        elif days > 7:
            return 'yellow'
        else:
            return 'red'


class DeliveryZone(models.Model):
    """
    Seller defines which states they deliver to and the fee.
    Only same state + bordering states allowed.
    Validated at checkout against STATE_BORDERS config.
    """

    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='delivery_zones'
    )
    state = models.CharField(
        max_length=50,
        help_text='Nigerian state this zone covers eg Lagos'
    )
    fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text='Delivery fee in NGN for this state'
    )
    estimated_days = models.PositiveIntegerField(
        default=1,
        help_text='Estimated delivery days eg 1 for same day, 2 for next day'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Delivery Zone'
        verbose_name_plural = 'Delivery Zones'
        # Seller can only have one zone per state
        unique_together = ['seller', 'state']
        ordering = ['state']

    def __str__(self):
        return f'{self.seller.store_name} → {self.state} (₦{self.fee})'


class FeaturedListing(models.Model):
    """
    Sellers pay to appear at the top of search results
    and category pages.
    Shows a subtle 'Sponsored' badge — honest, not spammy.
    """

    class ListingType(models.TextChoices):
        HOMEPAGE = 'homepage', 'Homepage Featured Store'
        STORE   = 'store',   'Featured Store'
        PRODUCT = 'product', 'Featured Product'

    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='featured_listings'
    )
    listing_type = models.CharField(
        max_length=10,
        choices=ListingType.choices
    )
    # If listing_type is product — link to specific product
    # If listing_type is store — this is null
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='featured_listings'
    )
    amount_paid = models.DecimalField(max_digits=8, decimal_places=2)
    fw_transaction_ref = models.CharField(max_length=100, unique=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Featured Listing'
        verbose_name_plural = 'Featured Listings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'ends_at']),
        ]

    def __str__(self):
        return f'{self.seller.store_name} — {self.listing_type} featured'