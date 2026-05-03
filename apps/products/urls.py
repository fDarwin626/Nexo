# apps/products/urls.py
from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # Product management (seller)
    path('add/', views.product_create, name='create'),
    path('<int:product_id>/images/', views.add_product_images, name='add_images'),
    path('<int:product_id>/edit/', views.product_edit, name='edit'),
    path('<int:product_id>/delete/', views.product_delete, name='delete'),
    path('<int:product_id>/restock/', views.restock_product, name='restock'),

    # Public product detail page
    path('<slug:product_slug>/', views.product_detail, name='detail'),

    # AJAX
    path('api/category/<int:category_id>/variants/',
         views.get_category_variants, name='category_variants'),
]