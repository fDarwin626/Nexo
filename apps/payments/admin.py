# apps/payments/admin.py
from django.contrib import admin
from .models import PaymentLog, ReserveFund, ReserveFundLog


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    list_display = [
        'fw_reference', 'payment_type', 'status',
        'amount', 'order_created', 'created_at'
    ]
    list_filter = ['payment_type', 'status', 'order_created']
    search_fields = ['fw_reference', 'buyer__email', 'order__order_ref']
    readonly_fields = [
        'fw_reference', 'fw_transaction_id', 'raw_webhook',
        'webhook_received_at', 'created_at', 'updated_at'
    ]
    # Prevent any editing of payment logs
    # They are immutable audit records
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ReserveFund)
class ReserveFundAdmin(admin.ModelAdmin):
    list_display = ['balance', 'alert_threshold', 'updated_at']
    readonly_fields = ['updated_at']


@admin.register(ReserveFundLog)
class ReserveFundLogAdmin(admin.ModelAdmin):
    list_display = [
        'transaction_type', 'amount',
        'balance_after', 'reference', 'created_at'
    ]
    list_filter = ['transaction_type']
    readonly_fields = ['created_at']