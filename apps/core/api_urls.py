# apps/core/api_urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.api_views import (
    api_register, api_login, api_logout, api_profile
)
from apps.products.api_views import (
    api_product_list, api_product_detail,
    api_category_list, api_submit_review
)
from apps.orders.api_views import (
    api_cart, api_cart_add, api_cart_update,
    api_cart_remove, api_order_list, api_order_detail
)
from apps.notifications.api_views import (
    api_notifications, api_mark_all_read
)

urlpatterns = [
    # ── AUTH ─────────────────────────────────────────────────
    path('auth/register/', api_register, name='api_register'),
    path('auth/login/', api_login, name='api_login'),
    path('auth/logout/', api_logout, name='api_logout'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='api_token_refresh'),
    path('auth/profile/', api_profile, name='api_profile'),

    # ── PRODUCTS ─────────────────────────────────────────────
    path('products/', api_product_list, name='api_products'),
    path('products/<slug:product_slug>/', api_product_detail, name='api_product_detail'),
    path('categories/', api_category_list, name='api_categories'),

    # ── REVIEWS ──────────────────────────────────────────────
    path('reviews/<int:order_item_id>/', api_submit_review, name='api_submit_review'),

    # ── CART ─────────────────────────────────────────────────
    path('cart/', api_cart, name='api_cart'),
    path('cart/add/', api_cart_add, name='api_cart_add'),
    path('cart/<int:item_id>/update/', api_cart_update, name='api_cart_update'),
    path('cart/<int:item_id>/remove/', api_cart_remove, name='api_cart_remove'),

    # ── ORDERS ───────────────────────────────────────────────
    path('orders/', api_order_list, name='api_orders'),
    path('orders/<str:order_ref>/', api_order_detail, name='api_order_detail'),

    # ── NOTIFICATIONS ────────────────────────────────────────
    path('notifications/', api_notifications, name='api_notifications'),
    path('notifications/mark-all-read/', api_mark_all_read, name='api_mark_all_read'),
]