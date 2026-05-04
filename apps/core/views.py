# apps/core/views.py
# ─────────────────────────────────────────────────────────────
# CORE VIEWS
# homepage          — general marketplace (all products)
# marketplace       — browse with filters + search
# category_browse   — browse by category
# search            — PostgreSQL full text search
# toggle_currency   — switch NGN/USD
# wishlist_toggle   — add/remove from wishlist
# error_404/500     — branded error pages
# ─────────────────────────────────────────────────────────────

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count
from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank
)
from apps.products.models import Product, Category, Wishlist
from apps.stores.models import SellerProfile, FeaturedListing
from .models import ExchangeRate, SiteSettings


def get_exchange_rate():
    """Gets current active exchange rate for USD display"""
    try:
        rate = ExchangeRate.objects.filter(is_active=True).first()
        return float(rate.usd_to_ngn) if rate else 1650.0
    except Exception:
        return 1650.0


def homepage(request):
    """
    Main marketplace homepage.
    Shows featured stores, new arrivals, flash sales.
    All products from all approved sellers.
    Admin products always visible.
    """
    # Featured stores (paid promotion)
    featured_stores = SellerProfile.objects.filter(
        is_approved=True,
        status='active',
        featured_listings__listing_type='homepage',
        featured_listings__is_active=True,
    ).distinct()[:8]

    # New arrivals
    new_arrivals = Product.objects.filter(
        is_active=True,
        seller__is_approved=True,
        seller__status='active',
    ).order_by('-created_at')[:12]

    # Flash sale products
    from django.utils import timezone
    now = timezone.now()
    flash_sales = Product.objects.filter(
        is_active=True,
        is_flash_sale=True,
        flash_sale_start__lte=now,
        flash_sale_end__gte=now,
        seller__is_approved=True,
        seller__status='active',
    ).order_by('flash_sale_end')[:8]

    # Top categories
    categories = Category.objects.filter(
        is_active=True,
        parent=None,
    ).order_by('order')[:12]

    # Exchange rate for currency toggle
    exchange_rate = get_exchange_rate()

    return render(request, 'core/homepage.html', {
        'featured_stores': featured_stores,
        'new_arrivals': new_arrivals,
        'flash_sales': flash_sales,
        'categories': categories,
        'exchange_rate': exchange_rate,
    })


def marketplace(request):
    """
    General marketplace — all products with filters.
    Filters: category, price range, condition,
             store, rating, delivery type, in stock only
    Sort: newest, price low/high, top rated, most reviewed
    """
    products = Product.objects.filter(
        is_active=True,
        seller__is_approved=True,
        seller__status='active',
    ).select_related('seller', 'category').prefetch_related('images')

    # ── FILTERS ──────────────────────────────────────────────
    category_slug = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    condition = request.GET.get('condition')
    store_slug = request.GET.get('store')
    min_rating = request.GET.get('rating')
    in_stock = request.GET.get('in_stock')
    search_query = request.GET.get('q')

    if category_slug:
        try:
            category = Category.objects.get(slug=category_slug)
            # Include subcategories
            subcategory_ids = list(
                category.subcategories.values_list('id', flat=True)
            )
            subcategory_ids.append(category.id)
            products = products.filter(
                category_id__in=subcategory_ids
            )
        except Category.DoesNotExist:
            pass

    if min_price:
        try:
            products = products.filter(base_price__gte=float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            products = products.filter(base_price__lte=float(max_price))
        except ValueError:
            pass

    if condition:
        products = products.filter(condition=condition)

    if store_slug:
        products = products.filter(seller__store_slug=store_slug)

    if min_rating:
        try:
            products = products.filter(
                rating_avg__gte=float(min_rating)
            )
        except ValueError:
            pass

    # ── SEARCH ───────────────────────────────────────────────
    if search_query:
        # PostgreSQL Full Text Search
        search_vector = SearchVector('name', weight='A') + \
                       SearchVector('description', weight='B')
        search_q = SearchQuery(search_query)
        products = products.annotate(
            rank=SearchRank(search_vector, search_q)
        ).filter(rank__gte=0.1).order_by('-rank')
    else:
        # ── SORTING ──────────────────────────────────────────
        sort = request.GET.get('sort', 'newest')
        if sort == 'price_low':
            products = products.order_by('base_price')
        elif sort == 'price_high':
            products = products.order_by('-base_price')
        elif sort == 'top_rated':
            products = products.order_by('-rating_avg')
        elif sort == 'most_reviewed':
            products = products.order_by('-rating_count')
        else:
            products = products.order_by('-created_at')

    # Featured products appear first
    featured = products.filter(is_featured=True)
    regular = products.filter(is_featured=False)
    products = list(featured) + list(regular)

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(products, 24)
    page = request.GET.get('page', 1)
    products_page = paginator.get_page(page)

    # All categories for filter sidebar
    categories = Category.objects.filter(
        is_active=True,
        parent=None,
    ).prefetch_related('subcategories')

    exchange_rate = get_exchange_rate()

    return render(request, 'core/marketplace.html', {
        'products': products_page,
        'categories': categories,
        'exchange_rate': exchange_rate,
        'current_filters': {
            'category': category_slug,
            'min_price': min_price,
            'max_price': max_price,
            'condition': condition,
            'store': store_slug,
            'rating': min_rating,
            'q': search_query,
            'sort': request.GET.get('sort', 'newest'),
        }
    })


def category_browse(request, category_slug):
    """Browse products in a specific category"""
    category = get_object_or_404(
        Category,
        slug=category_slug,
        is_active=True
    )

    # Include subcategories
    subcategory_ids = list(
        category.subcategories.values_list('id', flat=True)
    )
    subcategory_ids.append(category.id)

    products = Product.objects.filter(
        is_active=True,
        category_id__in=subcategory_ids,
        seller__is_approved=True,
        seller__status='active',
    ).select_related('seller').prefetch_related('images')

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(products, 24)
    page = request.GET.get('page', 1)
    products_page = paginator.get_page(page)

    exchange_rate = get_exchange_rate()

    return render(request, 'core/category.html', {
        'category': category,
        'products': products_page,
        'exchange_rate': exchange_rate,
        'subcategories': category.subcategories.filter(is_active=True),
    })


def toggle_currency(request):
    """
    Toggles user currency preference between NGN and USD.
    Saved to session — persists across pages.
    """
    current = request.session.get('currency', 'NGN')
    new_currency = 'USD' if current == 'NGN' else 'NGN'
    request.session['currency'] = new_currency

    # If logged in — save preference to user model
    if request.user.is_authenticated:
        request.user.currency_preference = new_currency
        request.user.save(update_fields=['currency_preference'])

    # Redirect back to where they came from
    next_url = request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)


@login_required
def wishlist_toggle(request, product_id):
    """
    Add or remove product from wishlist.
    POST only.
    Returns JSON for AJAX calls from Alpine.js.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    product = get_object_or_404(Product, pk=product_id, is_active=True)

    existing = Wishlist.objects.filter(
        user=request.user,
        product=product
    ).first()

    if existing:
        existing.delete()
        in_wishlist = False
        message = 'Removed from wishlist'
    else:
        Wishlist.objects.create(
            user=request.user,
            product=product,
            price_at_save=product.effective_price,
        )
        in_wishlist = True
        message = 'Added to wishlist'

    # Return JSON for Alpine.js to update heart icon
    return JsonResponse({
        'in_wishlist': in_wishlist,
        'message': message,
    })


@login_required
def wishlist_page(request):
    """Shows user's full wishlist"""
    wishlist_items = Wishlist.objects.filter(
        user=request.user
    ).select_related(
        'product__seller'
    ).prefetch_related(
        'product__images'
    ).order_by('-created_at')

    exchange_rate = get_exchange_rate()

    return render(request, 'core/wishlist.html', {
        'wishlist_items': wishlist_items,
        'exchange_rate': exchange_rate,
    })


def error_404(request, exception):
    """Custom 404 page"""
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    """Custom 500 page"""
    return render(request, 'errors/500.html', status=500)