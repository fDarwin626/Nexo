# apps/orders/urls.py
from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Cart
    path('cart/', views.cart_detail, name='cart'),
    path('cart/add/<int:sku_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:item_id>/', views.cart_remove, name='cart_remove'),
    path('cart/update/<int:item_id>/', views.cart_update, name='cart_update'),

    # Checkout
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/payment/', views.initiate_payment, name='initiate_payment'),
    path('payment-callback/', views.payment_callback, name='payment_callback'),
    path('checkout/pod/', views.create_pod_order, name='create_pod_order'),

    # Orders
    path('', views.order_list, name='order_list'),
    path('<str:order_ref>/', views.order_detail, name='order_detail'),
]