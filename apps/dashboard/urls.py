# apps/dashboard/urls.py
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Seller Dashboard
    path('seller/', views.seller_dashboard_home, name='seller'),
    path('seller/products/', views.seller_products, name='seller_products'),
    path('seller/orders/', views.seller_orders, name='seller_orders'),
    path('seller/orders/<int:order_id>/ship/', views.mark_shipped, name='mark_shipped'),
    path('seller/orders/<int:order_id>/deliver/', views.mark_delivered, name='mark_delivered'),
    path('seller/coupons/', views.seller_coupons, name='seller_coupons'),
    path('seller/coupons/create/', views.create_coupon, name='create_coupon'),
    path('seller/coupons/<int:coupon_id>/deactivate/', views.deactivate_coupon, name='deactivate_coupon'),
    path('seller/subscription/', views.seller_subscription, name='seller_subscription'),
    path('seller/settings/', views.seller_store_settings, name='seller_settings'),
    path('seller/delivery/', views.seller_delivery_zones, name='seller_delivery'),
    path('seller/delivery/<int:zone_id>/delete/', views.delete_delivery_zone, name='delete_delivery_zone'),
    path('seller/revenue/', views.seller_revenue, name='seller_revenue'),
    path('seller/disputes/', views.seller_disputes, name='seller_disputes'),
    path('seller/disputes/<int:dispute_id>/', views.seller_dispute_detail, name='seller_dispute_detail'),

    # Admin Dashboard
    path('admin/', views.admin_dashboard, name='admin'),
]