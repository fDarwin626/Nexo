# apps/orders/api_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import Cart, CartItem, Order, SellerOrder


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_cart(request):
    """Get current user cart"""
    cart, _ = Cart.objects.get_or_create(user=request.user)

    items = []
    for item in cart.items.select_related(
        'sku__product__seller', 'sku__product'
    ).prefetch_related('sku__variant_options', 'sku__product__images'):
        primary_image = item.sku.product.images.filter(is_primary=True).first()
        items.append({
            'id': item.pk,
            'sku_id': item.sku.pk,
            'product_name': item.sku.product.name,
            'product_slug': item.sku.product.slug,
            'variant_description': ', '.join(
                opt.value for opt in item.sku.variant_options.all()
            ),
            'quantity': item.quantity,
            'unit_price': float(item.price_snapshot),
            'line_total': float(item.line_total),
            'stock_available': item.sku.stock,
            'primary_image': primary_image.image.url if primary_image else None,
            'seller_name': item.sku.product.seller.store_name,
        })

    return Response({
        'total_items': cart.total_items,
        'subtotal': float(cart.subtotal),
        'items': items,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_cart_add(request):
    """
    Add item to cart.
    Body: { sku_id: int, quantity: int }
    """
    from apps.products.models import ProductSKU

    sku_id = request.data.get('sku_id')
    quantity = int(request.data.get('quantity', 1))

    if not sku_id:
        return Response(
            {'error': 'sku_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    sku = get_object_or_404(ProductSKU, pk=sku_id, is_active=True)

    if sku.stock < quantity:
        return Response(
            {'error': f'Only {sku.stock} units available'},
            status=status.HTTP_400_BAD_REQUEST
        )

    cart, _ = Cart.objects.get_or_create(user=request.user)

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        sku=sku,
        defaults={
            'quantity': quantity,
            'price_snapshot': sku.effective_price,
        }
    )

    if not created:
        cart_item.quantity += quantity
        cart_item.save(update_fields=['quantity'])

    return Response({
        'message': 'Added to cart',
        'cart_total_items': cart.total_items,
    }, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def api_cart_update(request, item_id):
    """Update cart item quantity. Body: { quantity: int }"""
    cart = get_object_or_404(Cart, user=request.user)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)

    quantity = request.data.get('quantity')
    try:
        quantity = int(quantity)
        if quantity < 1:
            raise ValueError
    except (TypeError, ValueError):
        return Response(
            {'error': 'Quantity must be a positive integer'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if item.sku.stock < quantity:
        return Response(
            {'error': f'Only {item.sku.stock} units available'},
            status=status.HTTP_400_BAD_REQUEST
        )

    item.quantity = quantity
    item.save(update_fields=['quantity'])

    return Response({'message': 'Cart updated'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_cart_remove(request, item_id):
    """Remove item from cart"""
    cart = get_object_or_404(Cart, user=request.user)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    item.delete()
    return Response({'message': 'Item removed'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_order_list(request):
    """Get all orders for logged in buyer"""
    orders = Order.objects.filter(
        buyer=request.user
    ).prefetch_related(
        'seller_orders__items'
    ).order_by('-created_at')

    data = []
    for order in orders:
        data.append({
            'id': order.pk,
            'order_ref': order.order_ref,
            'payment_method': order.payment_method,
            'payment_status': order.payment_status,
            'total_amount': float(order.total_amount),
            'created_at': order.created_at,
            'seller_orders': [
                {
                    'id': so.pk,
                    'seller_name': so.seller.store_name,
                    'status': so.status,
                    'seller_payout': float(so.seller_payout),
                    'items': [
                        {
                            'product_name': item.product_name,
                            'variant_description': item.variant_description,
                            'quantity': item.quantity,
                            'unit_price': float(item.unit_price),
                            'line_total': float(item.line_total),
                            'can_review': item.can_review,
                            'order_item_id': item.pk,
                        }
                        for item in so.items.all()
                    ]
                }
                for so in order.seller_orders.all()
            ]
        })

    return Response({'results': data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_order_detail(request, order_ref):
    """Get single order detail"""
    order = get_object_or_404(
        Order,
        order_ref=order_ref,
        buyer=request.user,
    )

    seller_orders = []
    for so in order.seller_orders.prefetch_related('items').all():
        seller_orders.append({
            'id': so.pk,
            'seller_name': so.seller.store_name,
            'seller_slug': so.seller.store_slug,
            'status': so.status,
            'delivery_fee': float(so.delivery_fee),
            'seller_payout': float(so.seller_payout),
            'tracking_number': so.tracking_number,
            'shipped_at': so.shipped_at,
            'delivered_at': so.delivered_at,
            'items': [
                {
                    'id': item.pk,
                    'product_name': item.product_name,
                    'product_sku_code': item.product_sku_code,
                    'variant_description': item.variant_description,
                    'quantity': item.quantity,
                    'unit_price': float(item.unit_price),
                    'line_total': float(item.line_total),
                    'can_review': item.can_review,
                }
                for item in so.items.all()
            ]
        })

    return Response({
        'id': order.pk,
        'order_ref': order.order_ref,
        'payment_method': order.payment_method,
        'payment_status': order.payment_status,
        'delivery_address': order.delivery_address,
        'delivery_state': order.delivery_state,
        'delivery_city': order.delivery_city,
        'subtotal': float(order.subtotal),
        'total_delivery_fee': float(order.total_delivery_fee),
        'discount_amount': float(order.discount_amount),
        'total_amount': float(order.total_amount),
        'created_at': order.created_at,
        'seller_orders': seller_orders,
    })