# apps/disputes/admin.py
from django.contrib import admin
from .models import Dispute, DisputeMessage, SellerStrike


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = [
        'seller_order', 'buyer', 'seller',
        'reason', 'status', 'created_at'
    ]
    list_filter =  [
        'seller_order__order__order_ref',
        'buyer__email',
        'seller__store_name'
    ]
    readonly_fields = [
        'created_at', 'updated_at',
        'seller_responded_at', 'resolved_at'
    ]

@admin.register(DisputeMessage)
class DisputeMessageAdmin(admin.ModelAdmin):
    list_display = [
        'dispute', 'sender_type',
        'sender', 'is_read', 'created_at'
    ]
    list_filter = ['sender_type', 'is_read']
    readonly_fields = ['created_at']


@admin.register(SellerStrike)
class SellerStrikeAdmin(admin.ModelAdmin):
    list_display = [
        'seller', 'level', 'dispute',
        'issued_by', 'created_at'
    ]
    list_filter = ['level']
    search_fields = ['seller__store_name']
    readonly_fields = ['created_at']
