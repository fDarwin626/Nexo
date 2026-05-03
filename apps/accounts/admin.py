from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, BanRecord
from django.contrib import admin


# apps/accounts/admin.py


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin for our User model.
    Makes it manageable from Django admin panel.
    """
    list_display = [
        'email', 'full_name', 'role',
        'is_email_verified', 'ban_status',
        'fraud_score', 'date_joined'
    ]
    list_filter = ['role', 'is_email_verified', 'ban_status', 'is_active']
    search_fields = ['email', 'full_name', 'phone']
    ordering = ['-date_joined']

    fieldsets = (
        ('Login Info', {
            'fields': ('email', 'password')
        }),
        ('Personal Info', {
            'fields': ('full_name', 'phone', 'role')
        }),
        ('Status', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'is_email_verified'
            )
        }),
        ('Fraud & Ban', {
            'fields': (
                'ban_status', 'fraud_score', 'ban_reason',
                'banned_at', 'device_fingerprint'
            )
        }),
        ('Pay on Delivery', {
            'fields': (
                'pod_count_this_month', 'pod_strikes',
                'pod_suspended_until'
            )
        }),
        ('Preferences', {
            'fields': ('currency_preference',)
        }),
        ('Timestamps', {
            'fields': ('date_joined', 'last_login'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'full_name', 'role',
                'password1', 'password2'
            ),
        }),
    )

    # Tell Django admin which field is the username equivalent
    # Since we replaced username with email
    readonly_fields = ['date_joined', 'last_login']


@admin.register(BanRecord)
class BanRecordAdmin(admin.ModelAdmin):
    list_display = [
        'original_account', 'ban_type',
        'is_honeypot', 'appeal_status', 'created_at'
    ]
    list_filter = ['ban_type', 'is_honeypot', 'appeal_status']
    search_fields = ['original_account__email', 'device_fingerprint']
    readonly_fields = ['created_at', 'updated_at']