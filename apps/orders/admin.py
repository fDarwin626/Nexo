# apps/orders/admin.py
from django.contrib import admin
from .models import Cart, CartItem, Order, SellerOrder, OrderItem


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'session_key', 'total_items', 'created_at']
    search_fields = ['user__email', 'session_key']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'sku', 'quantity', 'price_snapshot', 'added_at']
    search_fields = ['sku__product__name']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_ref', 'buyer_name', 'payment_method',
        'payment_status', 'total_amount', 'created_at'
    ]
    list_filter = ['payment_method', 'payment_status', 'delivery_type']
    search_fields = ['order_ref', 'buyer__email', 'guest_email']
    readonly_fields = ['order_ref', 'created_at', 'updated_at']


@admin.register(SellerOrder)
class SellerOrderAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'seller', 'status',
        'subtotal', 'seller_payout', 'created_at'
    ]
    list_filter = ['status']
    search_fields = ['order__order_ref', 'seller__store_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'product_name', 'quantity',
        'unit_price', 'line_total'
    ]
    search_fields = ['product_name', 'product_sku_code']
    readonly_fields = ['created_at']