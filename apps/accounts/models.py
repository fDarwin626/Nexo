from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

# apps/accounts/models.py
# ─────────────────────────────────────────────────────────────
# ACCOUNTS MODELS
# Custom User model using email as the login field
# Supports three roles: buyer, seller, admin
# Includes fraud scoring and ban system
# ────────────────────────────────────────────────────────────


class CustomUserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        """
        Creates a regular buyer account.
        Called when someone registers on the site.
        """
        if not email:
            raise ValueError('Email address is required')

        # normalize_email lowercases the domain part
        # so Test@GMAIL.COM becomes Test@gmail.com
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        # set_password hashes the password — never stored as plain text
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Creates an admin account.
        Called when you run: python manage.py createsuperuser
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_email_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Nexo's custom User model.

    AbstractBaseUser gives us: password, last_login, is_active
    PermissionsMixin gives us: is_superuser, groups, user_permissions

    We add everything else Nexo needs on top.
    """

    # ── ROLE CHOICES ─────────────────────────────────────────
    class Role(models.TextChoices):
        BUYER = 'buyer', 'Buyer'
        SELLER = 'seller', 'Seller'
        ADMIN = 'admin', 'Admin'

    # ── BAN TYPE CHOICES ─────────────────────────────────────
    class BanType(models.TextChoices):
        NONE = 'none', 'Not Banned'
        SHADOW = 'shadow', 'Shadow Banned'  # payment spins forever
        HARD = 'hard', 'Hard Banned'  # account blocked
        PERMANENT = 'permanent', 'Permanently Banned'

    # ── CORE FIELDS ──────────────────────────────────────────
    email = models.EmailField(
        unique=True,
        help_text='Used as the login identifier instead of username'
    )
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.BUYER
    )

    # ── STATUS FLAGS ─────────────────────────────────────────
    is_active = models.BooleanField(
        default=True,
        help_text='Uncheck to deactivate account without deleting'
    )
    is_staff = models.BooleanField(
        default=False,
        help_text='Allows access to Django admin panel'
    )
    is_email_verified = models.BooleanField(
        default=False,
        help_text='User must verify email before buying or selling'
    )

    # ── FRAUD & BAN SYSTEM ───────────────────────────────────
    device_fingerprint = models.CharField(
        max_length=255,
        blank=True,
        help_text='FingerprintJS hash — used for relation banning'
    )
    ban_status = models.CharField(
        max_length=10,
        choices=BanType.choices,
        default=BanType.NONE
    )
    fraud_score = models.PositiveIntegerField(
        default=0,
        help_text='Increases on failed payment attempts. >=5 shadow ban, >=8 hard ban'
    )
    ban_reason = models.TextField(
        blank=True,
        help_text='Internal note explaining why this account was banned'
    )
    banned_at = models.DateTimeField(null=True, blank=True)

    # ── PAY ON A DELIVERY SYSTEM ───────────────────────────────
    pod_count_this_month = models.PositiveIntegerField(
        default=0,
        help_text='Resets every month via Celery task'
    )
    pod_strikes = models.PositiveIntegerField(
        default=0,
        help_text='Cumulative POD strikes. 3 = permanent POD revocation'
    )
    pod_suspended_until = models.DateField(
        null=True,
        blank=True,
        help_text='POD suspended until this date after 2 monthly strikes'
    )

    # ── CURRENCY PREFERENCE ──────────────────────────────────
    currency_preference = models.CharField(
        max_length=3,
        default='NGN',
        choices=[('NGN', 'Nigerian Naira'), ('USD', 'US Dollar')]
    )

    # ── TIMESTAMPS ───────────────────────────────────────────
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── MANAGER ──────────────────────────────────────────────
    objects = CustomUserManager()

    # ── AUTH CONFIG ──────────────────────────────────────────
    # Tell Django to use email as the login field
    # instead of the default username field
    USERNAME_FIELD = 'email'

    # Fields prompted when running createsuperuser
    # email and password are always asked — REQUIRED_FIELDS
    # is for additional fields
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']
        indexes = [
            # Index on email for fast login lookups
            models.Index(fields=['email']),
            # Index on role for fast filtering
            models.Index(fields=['role']),
            # Index on ban_status for fraud checks
            models.Index(fields=['ban_status']),
        ]

    def __str__(self):
        return f'{self.email} ({self.get_role_display()})'

    # ── HELPER PROPERTIES ────────────────────────────────────
    @property
    def is_buyer(self):
        return self.role == self.Role.BUYER

    @property
    def is_seller(self):
        return self.role == self.Role.SELLER

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_banned(self):
        return self.ban_status != self.BanType.NONE

    @property
    def is_shadow_banned(self):
        return self.ban_status == self.BanType.SHADOW

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split()[0] if self.full_name else self.email


class BanRecord(models.Model):
    """
    Tracks every ban and its relationships.

    When a user is banned we store their device fingerprint.
    If they create a new account on the same device —
    we detect it and create a child ban linked to this record.
    The original banned account becomes a honeypot.
    """

    class BanType(models.TextChoices):
        SHADOW = 'shadow', 'Shadow Banned'
        HARD = 'hard', 'Hard Banned'
        PERMANENT = 'permanent', 'Permanently Banned'

    class AppealStatus(models.TextChoices):
        NONE = 'none', 'No Appeal'
        PENDING = 'pending', 'Appeal Pending'
        APPROVED = 'approved', 'Appeal Approved'
        DENIED = 'denied', 'Appeal Denied'

    # The original banned account
    original_account = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ban_records'
    )

    # Device fingerprint from FingerprintJS
    # Stored separately so we can detect same device even
    # if original account is deleted
    device_fingerprint = models.CharField(max_length=255, db_index=True)

    ban_type = models.CharField(max_length=10, choices=BanType.choices)

    # Is this account now a honeypot?
    # Honeypot = looks active but logs everything
    # Any device that logs into it gets child-banned
    is_honeypot = models.BooleanField(
        default=False,
        help_text='If True, any device logging into this account gets banned'
    )

    # Links child bans back to the original ban
    # eg: User A banned → creates new account → that new account
    # is a child ban pointing back to original
    parent_ban = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_bans'
    )

    ban_reason = models.TextField()
    appeal_status = models.CharField(
        max_length=10,
        choices=AppealStatus.choices,
        default=AppealStatus.NONE
    )
    appeal_note = models.TextField(
        blank=True,
        help_text='Admin notes on the appeal decision'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ban Record'
        verbose_name_plural = 'Ban Records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['device_fingerprint']),
            models.Index(fields=['ban_type']),
        ]

    def __str__(self):
        return f'Ban: {self.original_account} — {self.ban_type}'