# apps/core/admin.py
from django.contrib import admin
from .models import Coupon, CouponUsage, ExchangeRate, SiteSettings


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'seller', 'discount_type',
        'discount_value', 'uses_count',
        'max_uses', 'is_active', 'valid_until'
    ]
    list_filter = ['discount_type', 'is_active']
    search_fields = ['code', 'seller__store_name']
    readonly_fields = [
        'code', 'uses_count',
        'budget_used', 'created_at', 'updated_at'
    ]


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = [
        'coupon', 'user', 'order',
        'discount_amount', 'used_at'
    ]
    search_fields = ['coupon__code', 'user__email']
    readonly_fields = ['used_at']

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['usd_to_ngn', 'is_active', 'set_by', 'created_at']
    readonly_fields = ['created_at']


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'platform_name', 'maintenance_mode',
        'reserve_fund_percent', 'updated_at'
    ]
    readonly_fields = ['updated_at']

    def has_add_permission(self, request):
        # Only one SiteSettings row allowed
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Never delete site settings
        return False