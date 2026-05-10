# apps/dashboard/decorators.py
from functools import wraps
from django.shortcuts import redirect


def seller_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/auth/login/')
        try:
            profile = request.user.seller_profile
            if not profile.is_approved or profile.status != 'active':
                return redirect('/')
        except Exception:
            return redirect('/')
        return view_func(request, *args, **kwargs)
    return wrapper