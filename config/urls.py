# config/urls.py
# ─────────────────────────────────────────────────────────────
# MASTER URL CONFIGURATION
# This is the root URL file — every app's URLs branch from here
# Think of this as the main road that splits into smaller roads
# ─────────────────────────────────────────────────────────────
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    # ── DJANGO ADMIN ─────────────────────────────────────────
    # Your Django admin panel
    path('admin/', admin.site.urls),

    # ── AUTHENTICATION ────────────────────────────────────────
    # Handles login, logout, register, password reset
    # Google OAuth etc — all via django-allauth
    path('auth/social/', include('allauth.urls')),

    # ── OUR APPS ─────────────────────────────────────────────
    # Each app manages its own URLs internally

    # Core — homepage, marketplace, search, wishlist
    path('', include('apps.core.urls')),

    # Accounts -- custom register, profile, email verify
    path('auth/', include('apps.accounts.urls')),

    # Stores — seller storefronts /store/nike/
    path('store/', include('apps.stores.urls')),

    # Products — product detail pages
    path('products/', include('apps.products.urls')),

    # Orders — cart, checkout, order tracking
    path('orders/', include('apps.orders.urls')),

    # Payments — Flutterwave webhooks, payment verify
    path('payments/', include('apps.payments.urls')),

    # Disputes — open dispute, track dispute
    path('disputes/', include('apps.disputes.urls')),

    # Dashboard — seller dashboard, admin dashboard
    path('dashboard/', include('apps.dashboard.urls')),

    # Notifications — mark read, list notifications
    path('notifications/', include('apps.notifications.urls')),

    # ── REST API ──────────────────────────────────────────────
    # All Flutter mobile app endpoints live under /api/v1/
    # Versioned so future app updates don't break old clients
    path('api/v1/', include('apps.core.api_urls')),

    # ── API DOCUMENTATION ─────────────────────────────────────
    # Auto-generated Swagger UI — useful for Flutter development
    # Only accessible in development (locked in prod settings)
    path('api/schema/', include([
        path('', __import__('drf_spectacular.views', fromlist=['SpectacularAPIView']).SpectacularAPIView.as_view(),
             name='schema'),
        path('swagger/',
             __import__('drf_spectacular.views', fromlist=['SpectacularSwaggerView']).SpectacularSwaggerView.as_view(
                 url_name='schema'), name='swagger-ui'),
    ])),

]

# ── MEDIA FILES IN DEVELOPMENT ────────────────────────────────
# In development Django serves uploaded files directly
# In production Cloudinary handles this instead
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )

# ── CUSTOM ERROR PAGES ────────────────────────────────────────
# These point to our branded Nexo error pages
# Templates go in templates/errors/404.html etc
handler404 = 'apps.core.views.error_404'
handler500 = 'apps.core.views.error_500'
