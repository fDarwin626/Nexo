# apps/products/api_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import Product, ProductSKU, Category, Review


@api_view(['GET'])
@permission_classes([AllowAny])
def api_product_list(request):
    """
    Browse all products — marketplace.
    Supports: ?q=search, ?category=slug, ?min_price=, ?max_price=, ?page=
    """
    products = Product.objects.filter(
        is_active=True,
        seller__status='active',
        seller__is_approved=True,
    ).select_related('seller', 'category').prefetch_related('images')

    # Search
    q = request.GET.get('q', '').strip()
    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(description__icontains=q)
        )

    # Category filter
    category_slug = request.GET.get('category', '').strip()
    if category_slug:
        products = products.filter(category__slug=category_slug)

    # Price filter
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
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

    # Pagination — manual since we're using function views
    from django.core.paginator import Paginator
    page_num = request.GET.get('page', 1)
    paginator = Paginator(products.order_by('-created_at'), 20)
    page = paginator.get_page(page_num)

    data = []
    for p in page:
        primary_image = p.images.filter(is_primary=True).first()
        data.append({
            'id': p.pk,
            'name': p.name,
            'slug': p.slug,
            'base_price': float(p.base_price),
            'effective_price': float(p.effective_price),
            'discount_percent': p.discount_percent,
            'rating_avg': float(p.rating_avg),
            'rating_count': p.rating_count,
            'condition': p.condition,
            'is_flash_sale': p.is_flash_sale,
            'primary_image': primary_image.image.url if primary_image else None,
            'seller': {
                'id': p.seller.pk,
                'store_name': p.seller.store_name,
                'store_slug': p.seller.store_slug,
            },
            'category': {
                'id': p.category.pk,
                'name': p.category.name,
                'slug': p.category.slug,
            },
        })

    return Response({
        'count': paginator.count,
        'total_pages': paginator.num_pages,
        'current_page': page.number,
        'results': data,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def api_product_detail(request, product_slug):
    """Full product detail — all SKUs, images, reviews"""
    product = get_object_or_404(
        Product,
        slug=product_slug,
        is_active=True,
        seller__status='active',
        seller__is_approved=True,
    )

    images = [
        {
            'id': img.pk,
            'url': img.image.url,
            'is_primary': img.is_primary,
            'order': img.order,
        }
        for img in product.images.all().order_by('order')
    ]

    skus = []
    for sku in product.skus.filter(is_active=True).prefetch_related('variant_options__variant_type'):
        skus.append({
            'id': sku.pk,
            'sku_code': sku.sku_code,
            'stock': sku.stock,
            'price': float(sku.effective_price),
            'variant_options': [
                {
                    'type': opt.variant_type.name,
                    'value': opt.value,
                }
                for opt in sku.variant_options.all()
            ]
        })

    reviews = []
    for r in product.reviews.select_related('buyer').order_by('-created_at')[:10]:
        reviews.append({
            'id': r.pk,
            'buyer_name': r.buyer.get_short_name(),
            'rating': r.rating,
            'comment': r.comment,
            'photo': r.photo.url if r.photo else None,
            'seller_reply': r.seller_reply,
            'replied_at': r.replied_at,
            'created_at': r.created_at,
        })

    # Wishlist check
    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = product.wishlisted_by.filter(
            user=request.user
        ).exists()

    return Response({
        'id': product.pk,
        'name': product.name,
        'slug': product.slug,
        'description': product.description,
        'condition': product.condition,
        'base_price': float(product.base_price),
        'effective_price': float(product.effective_price),
        'discount_percent': product.discount_percent,
        'is_flash_sale': product.is_flash_sale,
        'flash_sale_price': float(product.flash_sale_price) if product.flash_sale_price else None,
        'flash_sale_end': product.flash_sale_end,
        'rating_avg': float(product.rating_avg),
        'rating_count': product.rating_count,
        'total_stock': product.total_stock,
        'images': images,
        'skus': skus,
        'reviews': reviews,
        'in_wishlist': in_wishlist,
        'seller': {
            'id': product.seller.pk,
            'store_name': product.seller.store_name,
            'store_slug': product.seller.store_slug,
            'rating_avg': float(product.seller.rating_avg),
            'logo': product.seller.logo.url if product.seller.logo else None,
        },
        'category': {
            'id': product.category.pk,
            'name': product.category.name,
            'slug': product.category.slug,
        },
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def api_category_list(request):
    """All active categories"""
    categories = Category.objects.filter(
        is_active=True,
        parent__isnull=True,
    ).prefetch_related('subcategories')

    data = []
    for cat in categories:
        data.append({
            'id': cat.pk,
            'name': cat.name,
            'slug': cat.slug,
            'icon': cat.icon,
            'subcategories': [
                {
                    'id': sub.pk,
                    'name': sub.name,
                    'slug': sub.slug,
                    'icon': sub.icon,
                }
                for sub in cat.subcategories.filter(is_active=True)
            ]
        })

    return Response({'results': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_submit_review(request, order_item_id):
    """Submit a review for a delivered order item"""
    from apps.orders.models import OrderItem
    from .models import Review
    from django.db import transaction

    order_item = get_object_or_404(
        OrderItem,
        pk=order_item_id,
        seller_order__order__buyer=request.user,
    )

    if not order_item.can_review:
        return Response(
            {'error': 'You cannot review this item yet or have already reviewed it'},
            status=status.HTTP_400_BAD_REQUEST
        )

    rating = request.data.get('rating')
    comment = request.data.get('comment', '').strip()

    try:
        rating = int(rating)
        if not 1 <= rating <= 5:
            raise ValueError
    except (TypeError, ValueError):
        return Response(
            {'error': 'Rating must be between 1 and 5'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not comment:
        return Response(
            {'error': 'Comment is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    product = order_item.sku.product if order_item.sku else None
    if not product:
        return Response(
            {'error': 'Product no longer exists'},
            status=status.HTTP_400_BAD_REQUEST
        )

    with transaction.atomic():
        review = Review.objects.create(
            product=product,
            buyer=request.user,
            order_item=order_item,
            rating=rating,
            comment=comment,
        )
        # Update product rating
        from django.db.models import Avg, Count
        result = product.reviews.aggregate(avg=Avg('rating'), count=Count('id'))
        product.rating_avg = result['avg'] or 0
        product.rating_count = result['count'] or 0
        product.save(update_fields=['rating_avg', 'rating_count'])

    return Response({
        'message': 'Review submitted successfully',
        'review_id': review.pk,
    }, status=status.HTTP_201_CREATED)