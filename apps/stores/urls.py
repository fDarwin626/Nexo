# apps/stores/urls.py
from django.urls import path
from . import  views

app_name = 'stores'

urlpatterns = [
    # New entry point — must be logged in
    path('become-seller/', views.seller_register_start, name='seller_register_start'),
    # Keep step1 for reference but entry is now become-seller
    path('register/step2/', views.seller_register_step2, name='seller_register_step2'),
    path('register/step3/', views.seller_register_step3, name='seller_register_step3'),
    path('register/step4/', views.seller_register_step4, name='seller_register_step4'),
    path('register/payment-callback/', views.seller_payment_callback, name='seller_payment_callback'),
    path('register/complete/', views.onboarding_complete, name='onboarding_complete'),
]