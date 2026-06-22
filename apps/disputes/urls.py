# apps/disputes/urls.py
from django.urls import path
from . import views

app_name = 'disputes'

urlpatterns = [
    # Buyer
    path('open/<int:seller_order_id>/', views.open_dispute, name='open'),
    path('<int:dispute_id>/', views.dispute_detail, name='detail'),
    path('my/', views.my_disputes, name='my_disputes'),

    # Admin
    path('admin/all/', views.admin_dispute_list, name='admin_list'),
    path('admin/<int:dispute_id>/', views.admin_dispute_detail, name='admin_detail'),
    path('admin/<int:dispute_id>/message/', views.admin_send_message, name='admin_message'),
    path('admin/<int:dispute_id>/resolve/', views.admin_resolve_dispute, name='admin_resolve'),
    path('admin/<int:dispute_id>/strike/', views.admin_issue_strike, name='admin_strike'),
]