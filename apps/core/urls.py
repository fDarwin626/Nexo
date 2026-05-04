# apps/core/urls.py
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Homepage — main marketplace
    path('', views.homepage, name='homepage'),

    # Marketplace browse + search
    path('marketplace/', views.marketplace, name='marketplace'),

    # Category browse
    path('category/<slug:category_slug>/', views.category_browse, name='category'),

    # Currency toggle
    path('currency/toggle/', views.toggle_currency, name='toggle_currency'),

    # Wishlist
    path('wishlist/', views.wishlist_page, name='wishlist'),
    path('wishlist/toggle/<int:product_id>/', views.wishlist_toggle, name='wishlist_toggle'),
]