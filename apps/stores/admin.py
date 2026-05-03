# apps/stores/admin.py
from django.contrib import admin
from .models import SellerProfile, Subscription, DeliveryZone, FeaturedListing


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = [
        'store_name', 'user', 'account_type',
        'status', 'is_approved', 'rating_avg',
        'strike_count', 'created_at'
    ]
    list_filter = ['status', 'is_approved', 'account_type', 'allow_pod']
    search_fields = ['store_name', 'user__email', 'fw_subaccount_id']
    readonly_fields = [
        'store_slug', 'fw_subaccount_id', 'fw_subaccount_code',
        'rating_avg', 'rating_count', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'seller', 'plan', 'status',
        'start_date', 'end_date', 'days_remaining'
    ]
    list_filter = ['plan', 'status']
    search_fields = ['seller__store_name', 'fw_transaction_ref']
    readonly_fields = ['created_at']

    def days_remaining(self, obj):
        return f'{obj.days_remaining} days'
    days_remaining.short_description = 'Days Left'


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ['seller', 'state', 'fee', 'estimated_days', 'is_active']
    list_filter = ['state', 'is_active']
    search_fields = ['seller__store_name', 'state']


@admin.register(FeaturedListing)
class FeaturedListingAdmin(admin.ModelAdmin):
    list_display = [
        'seller', 'listing_type', 'is_active',
        'starts_at', 'ends_at'
    ]
    list_filter = ['listing_type', 'is_active']
    search_fields = ['seller__store_name']