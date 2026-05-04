# apps/dashboard/urls.py
from django.urls import path
from django.http import HttpResponse

app_name = 'dashboard'

def seller_placeholder(request):
    return HttpResponse('<h1>Seller Dashboard — Coming Soon (Section 8)</h1>')

def admin_placeholder(request):
    return HttpResponse('<h1>Admin Dashboard — Coming Soon (Section 9)</h1>')

urlpatterns = [
    path('seller/', seller_placeholder, name='seller'),
    path('admin/', admin_placeholder, name='admin'),
]