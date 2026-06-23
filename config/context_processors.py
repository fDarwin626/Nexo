# apps/core/context_processor.py
from apps.products.models import Category
from apps.orders.models import Cart

def global_context(request):
    """
    Injected into every template automatically
    Providers: all_category, cart_count
    :param request:
    :return:
    """
    # Category for mega dropdown
    all_categories = Category.objects.filter(
        is_active = True,
        parent__isnull = True,
    ).prefetch_related('subcategories').order_by('order', 'name')

    # Cart count
    cart_count = 0
    if request.user.is_authenticated:
        try:
            cart = request.user.cart
            cart_count = cart.total_items
        except Exception:
            cart_count = 0
    return        {
        "all_categories": all_categories,
        "cart_count": cart_count,
    }