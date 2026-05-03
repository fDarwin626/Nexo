# apps/core/models.py
# ─────────────────────────────────────────────────────────────
# CORE MODELS
# Coupon       — discount codes (seller + platform-wide)
# CouponUsage  — tracks who used which coupon
# ExchangeRate — admin-set NGN/USD rate
# SiteSettings — global platform settings (singleton)
# ─────────────────────────────────────────────────────────────

from django.db import models
from django.conf import settings
import uuid


class Coupon(models.Model):
    """
    Discount codes — two types:

    1. Seller coupon (seller is set):
       - Only works on that seller's products
       - Seller creates via their dashboard
       - Code auto-generated (eg NK7X2-P9QM4)
       - 5% to 50% discount

    2. Platform coupon (seller is null):
       - Works across entire marketplace
       - Only admin can create
       - Admin absorbs the cost fully
       - Has budget_cap to prevent unlimited liability
    """

    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage Off'
        FIXED      = 'fixed',      'Fixed Amount Off'

    # ── OWNERSHIP ────────────────────────────────────────────
    # null = platform-wide coupon (admin only)
    # set  = seller-specific coupon
    seller = models.ForeignKey(
        'stores.SellerProfile',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='coupons',
        help_text='Leave null for platform-wide coupons'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='coupons_created'
    )

    # ── CODE ─────────────────────────────────────────────────
    # Auto-generated on save — seller never types it manually
    code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text='Auto-generated unique code eg NK7X2-P9QM4'
    )

    # ── DISCOUNT ─────────────────────────────────────────────
    discount_type = models.CharField(
        max_length=10,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text='Percentage (5-50) or fixed NGN amount'
    )

    # ── RESTRICTIONS ─────────────────────────────────────────
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Minimum order amount in NGN to use this coupon'
    )
    max_uses = models.PositiveIntegerField(
        default=100,
        help_text='Maximum total uses before coupon deactivates'
    )
    uses_count = models.PositiveIntegerField(
        default=0,
        help_text='Current total uses — auto-incremented on each use'
    )
    max_uses_per_user = models.PositiveIntegerField(
        default=1,
        help_text='How many times one user can use this coupon'
    )

    # ── PLATFORM COUPON BUDGET CAP ───────────────────────────
    # Only relevant for platform-wide coupons (seller=null)
    # Prevents admin from accidentally losing too much money
    # When total discount given reaches this cap → coupon deactivates
    budget_cap = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Platform coupons only — auto-deactivates when total discount hits this'
    )
    budget_used = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text='Total discount amount given so far'
    )

    # ── VALIDITY ─────────────────────────────────────────────
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
            models.Index(fields=['seller']),
        ]

    def __str__(self):
        if self.seller:
            return f'{self.code} — {self.seller.store_name} ({self.discount_value}%)'
        return f'{self.code} — Platform Wide ({self.discount_value}%)'

    def save(self, *args, **kwargs):
        # Auto-generate coupon code on first save
        if not self.code:
            self.code = self._generate_code()
        super().save(*args, **kwargs)

    def _generate_code(self):
        """
        Generates unique code like NK7X2-P9QM4
        Keeps generating until unique one found
        """
        while True:
            raw = uuid.uuid4().hex[:10].upper()
            code = f'{raw[:5]}-{raw[5:]}'
            if not Coupon.objects.filter(code=code).exists():
                return code

    @property
    def is_valid(self):
        """Check if coupon is currently usable"""
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from or now > self.valid_until:
            return False
        if self.uses_count >= self.max_uses:
            return False
        if self.budget_cap and self.budget_used >= self.budget_cap:
            return False
        return True

    def calculate_discount(self, order_amount):
        """
        Returns discount amount in NGN for a given order amount.
        Returns 0 if minimum order not met.
        """
        if self.min_order_amount and order_amount < self.min_order_amount:
            return 0
        if self.discount_type == self.DiscountType.PERCENTAGE:
            return order_amount * (self.discount_value / 100)
        return min(self.discount_value, order_amount)


class CouponUsage(models.Model):
    """
    Tracks every use of a coupon.
    Used to:
    - Enforce max_uses_per_user limit
    - Track budget_used for platform coupons
    - Audit trail for discount usage
    """

    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name='usages'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coupon_usages'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='coupon_usages'
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Actual NGN amount discounted on this order'
    )
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Coupon Usage'
        verbose_name_plural = 'Coupon Usages'
        ordering = ['-used_at']

    def __str__(self):
        return f'{self.coupon.code} used by {self.user.email}'


class ExchangeRate(models.Model):
    """
    Admin-set NGN/USD exchange rate.
    All prices stored in NGN.
    USD display = NGN price ÷ this rate.

    Admin updates manually — no external API dependency.
    Simple, reliable, zero rate-limit issues.

    Only one active rate at a time.
    History kept for audit trail.
    """

    usd_to_ngn = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='How many NGN = 1 USD eg 1650.00'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Only one rate should be active at a time'
    )
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='exchange_rates_set'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Exchange Rate'
        verbose_name_plural = 'Exchange Rates'
        ordering = ['-created_at']

    def __str__(self):
        return f'$1 = ₦{self.usd_to_ngn} ({"active" if self.is_active else "inactive"})'

    def save(self, *args, **kwargs):
        # When new rate set as active
        # deactivate all previous rates
        if self.is_active:
            ExchangeRate.objects.filter(
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class SiteSettings(models.Model):
    """
    Global platform settings — singleton pattern.
    Only one row ever exists in this table.
    Admin manages via Django admin.

    Contains:
    - Platform name, tagline
    - Maintenance mode toggle
    - Reserve fund contribution %
    - Max featured stores on homepage
    - POD limits per account tier
    """

    # ── PLATFORM IDENTITY ────────────────────────────────────
    platform_name = models.CharField(max_length=50, default='Nexo')
    platform_tagline = models.CharField(
        max_length=100,
        default='Nigerian Marketplace // Converge & Sell'
    )
    support_email = models.EmailField(default='support@nexo.ng')
    support_whatsapp = models.CharField(max_length=20, blank=True)

    # ── MAINTENANCE ──────────────────────────────────────────
    maintenance_mode = models.BooleanField(
        default=False,
        help_text='If True — site shows maintenance page to all non-admin users'
    )
    maintenance_message = models.TextField(
        blank=True,
        default='Nexo is undergoing scheduled maintenance. Back shortly!'
    )

    # ── RESERVE FUND ─────────────────────────────────────────
    reserve_fund_percent = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.00,
        help_text='% of every Pay Now transaction that goes to reserve fund eg 1.00 = 1%'
    )

    # ── FEATURED LISTINGS ────────────────────────────────────
    max_homepage_featured_stores = models.PositiveIntegerField(
        default=8,
        help_text='Maximum store cards shown in homepage featured section'
    )

    # ── SUBSCRIPTION PRICES (NGN) ────────────────────────────
    sub_price_1m = models.DecimalField(
        max_digits=10, decimal_places=2, default=5_000.00,
        help_text='1 month subscription price in NGN'
    )
    sub_price_6m = models.DecimalField(
        max_digits=10, decimal_places=2, default=25_000.00,
        help_text='6 month subscription price in NGN'
    )
    sub_price_12m = models.DecimalField(
        max_digits=10, decimal_places=2, default=45_000.00,
        help_text='12 month subscription price in NGN'
    )
    sub_price_24m = models.DecimalField(
        max_digits=10, decimal_places=2, default=80_000.00,
        help_text='24 month subscription price in NGN'
    )

    # ── POD LIMITS ───────────────────────────────────────────
    pod_limit_new = models.PositiveIntegerField(
        default=2,
        help_text='POD orders per month for new accounts (0-3 months)'
    )
    pod_limit_established = models.PositiveIntegerField(
        default=5,
        help_text='POD orders per month for established accounts (3m+)'
    )
    pod_limit_vip = models.PositiveIntegerField(
        default=8,
        help_text='POD orders per month for VIP buyers'
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='site_settings_updated'
    )

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return f'Nexo Site Settings (updated {self.updated_at.date()})'

    @classmethod
    def get_settings(cls):
        """
        Always returns the one SiteSettings instance.
        Creates it if it doesn't exist yet.
        Use this everywhere instead of SiteSettings.objects.first()
        """
        settings_obj, created = cls.objects.get_or_create(pk=1)
        return settings_obj