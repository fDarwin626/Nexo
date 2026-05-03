from django.shortcuts import render
# apps/core/views.py
from django.shortcuts import render
from django.http import HttpResponse




def error_404(request, exception):
    """Custom 404 page — branded Nexo page"""
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    """Custom 500 page — branded Nexo page"""
    return render(request, 'errors/500.html', status=500)