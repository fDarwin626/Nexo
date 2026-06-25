# apps/orders/views.py
# ─────────────────────────────────────────────────────────────
# ORDERS VIEWS
# cart_detail      — view cart contents
# cart_add         — add item to cart
# cart_remove      — remove item from cart
# cart_update      — update item quantity
# checkout         — checkout page
# order_confirm    — after payment confirmed
# order_detail     — view single order
# order_list       — buyer's order history
# ─────────────────────────────────────────────────────────────

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import json
import requests
from .models import Cart, CartItem, Order, SellerOrder, OrderItem
from apps.products.models import ProductSKU, Product
from apps.stores.models import SellerProfile, DeliveryZone
from apps.payments.models import PaymentLog
from apps.core.models import Coupon, CouponUsage
from decimal import Decimal

# ── CART HELPERS ─────────────────────────────────────────────

def get_or_create_cart(request):
    """
    Gets existing cart or creates new one.
    Logged in users: cart linked to user account
    Guests: cart linked to session key
    On login: guest cart merges into user cart
    """
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(
            user=request.user
        )
    else:
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()

        session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(
            session_key=session_key,
            user=None,
        )
    return cart


def merge_guest_cart(request, user):
    """
    Called on login — merges guest cart into user cart.
    If same SKU exists in both → add quantities together.
    Guest cart deleted after merge.
    """
    if not request.session.session_key:
        return

    try:
        guest_cart = Cart.objects.get(
            session_key=request.session.session_key,
            user=None,
        )
    except Cart.DoesNotExist:
        return

    user_cart, created = Cart.objects.get_or_create(user=user)

    # Merge items
    for guest_item in guest_cart.items.all():
        existing = user_cart.items.filter(
            sku=guest_item.sku
        ).first()

        if existing:
            # Add quantities together
            existing.quantity += guest_item.quantity
            existing.save(update_fields=['quantity'])
        else:
            # Move item to user cart
            guest_item.cart = user_cart
            guest_item.save(update_fields=['cart'])

    # Delete empty guest cart
    guest_cart.delete()


def get_delivery_fee(seller, buyer_state, delivery_type):
    """
    Gets delivery fee for a seller to a buyer's state.
    Returns 0 for pickup, fee amount for door delivery.
    Returns None if seller doesn't deliver to that state.
    """
    if delivery_type == 'pickup':
        return 0

    # Check state border validation
    from apps.core.utils import can_deliver
    if not can_deliver(seller.user.profile_state if hasattr(
        seller.user, 'profile_state'
    ) else '', buyer_state):
        return None

    zone = DeliveryZone.objects.filter(
        seller=seller,
        state=buyer_state,
        is_active=True,
    ).first()

    if zone:
        return zone.fee
    return None


# ── CART VIEWS ───────────────────────────────────────────────

def cart_detail(request):
    """Shows cart contents"""
    cart = get_or_create_cart(request)
    items = cart.items.select_related(
        'sku__product__seller',
    ).prefetch_related(
        'sku__variant_options',
        'sku__product__images',
    ).all()

    # Group by seller for display
    from collections import defaultdict
    items_by_seller = defaultdict(list)
    for item in items:
        items_by_seller[item.sku.product.seller].append(item)

    # Exchange rate
    from apps.core.views import get_exchange_rate
    exchange_rate = get_exchange_rate()

    return render(request, 'orders/cart.html', {
        'cart': cart,
        'items': items,
        'items_by_seller': dict(items_by_seller),
        'exchange_rate': exchange_rate,
    })


@require_POST
def cart_add(request, sku_id):
    """
    Add a SKU to cart.
    If already in cart → increment quantity.
    Validates stock availability.
    Returns JSON for Alpine.js cart drawer.
    """
    sku = get_object_or_404(ProductSKU, pk=sku_id, is_active=True)

    # Check product is available
    if not sku.product.is_active:
        return JsonResponse({
            'success': False,
            'error': 'This product is no longer available'
        }, status=400)

    # Check stock
    if sku.stock <= 0:
        return JsonResponse({
            'success': False,
            'error': 'This item is out of stock'
        }, status=400)

    # Check seller store is active
    if not sku.product.seller.is_approved or \
       sku.product.seller.status != 'active':
        return JsonResponse({
            'success': False,
            'error': 'This store is currently unavailable'
        }, status=400)

    quantity = int(request.POST.get('quantity', 1))
    cart = get_or_create_cart(request)

    existing_item = cart.items.filter(sku=sku).first()
    if existing_item:
        new_quantity = existing_item.quantity + quantity
        if new_quantity > sku.stock:
            return JsonResponse({
                'success': False,
                'error': f'Only {sku.stock} units available'
            }, status=400)
        existing_item.quantity = new_quantity
        existing_item.save(update_fields=['quantity'])
    else:
        if quantity > sku.stock:
            return JsonResponse({
                'success': False,
                'error': f'Only {sku.stock} units available'
            }, status=400)
        CartItem.objects.create(
            cart=cart,
            sku=sku,
            quantity=quantity,
            price_snapshot=sku.effective_price,
        )

    return JsonResponse({
        'success': True,
        'cart_count': cart.total_items,
        'message': f'{sku.product.name} added to cart',
    })


@require_POST
def cart_remove(request, item_id):
    """Remove an item from cart"""
    cart = get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)
    item.delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': cart.total_items,
        })

    messages.success(request, 'Item removed from cart')
    return redirect('orders:cart')


@require_POST
def cart_update(request, item_id):
    """Update cart item quantity"""
    cart = get_or_create_cart(request)
    item = get_object_or_404(CartItem, pk=item_id, cart=cart)

    quantity = int(request.POST.get('quantity', 1))

    if quantity <= 0:
        item.delete()
        return JsonResponse({
            'success': True,
            'removed': True,
            'cart_count': cart.total_items,
        })

    if quantity > item.sku.stock:
        return JsonResponse({
            'success': False,
            'error': f'Only {item.sku.stock} units available',
        }, status=400)

    item.quantity = quantity
    item.save(update_fields=['quantity'])

    return JsonResponse({
        'success': True,
        'line_total': float(item.line_total),
        'cart_total': float(cart.subtotal),
        'cart_count': cart.total_items,
    })


# ── CHECKOUT VIEWS ───────────────────────────────────────────

@login_required
def checkout(request):
    """
    Checkout page.
    Shows order summary, delivery address,
    coupon field, payment method selection.
    """
    cart = get_or_create_cart(request)

    if cart.total_items == 0:
        messages.warning(request, 'Your cart is empty.')
        return redirect('orders:cart')

    # Get items grouped by seller
    items_by_seller = cart.get_items_by_seller()

    if request.method == 'POST':
        # Collect checkout data
        delivery_type = request.POST.get('delivery_type', 'door')
        delivery_address = request.POST.get('delivery_address', '')
        delivery_state = request.POST.get('delivery_state', '')
        delivery_city = request.POST.get('delivery_city', '')
        payment_method = request.POST.get('payment_method', 'pay_now')
        coupon_code = request.POST.get('coupon_code', '').strip().upper()

        # Validate delivery state
        if delivery_type == 'door' and not delivery_state:
            messages.error(request, 'Please select your delivery state.')
            return redirect('orders:checkout')

        # Calculate totals
        subtotal = cart.subtotal
        total_delivery_fee = Decimal('0')
        discount_amount = Decimal('0')
        coupon = None

        # Calculate delivery fees per seller
        delivery_fees = {}
        for seller, items in items_by_seller.items():
            if delivery_type == 'door':
                fee = DeliveryZone.objects.filter(
                    seller=seller,
                    state=delivery_state,
                    is_active=True,
                ).first()
                delivery_fees[seller.pk] = float(
                    fee.fee if fee else 0
                )
                total_delivery_fee += Decimal(str(delivery_fees[seller.pk]))
            else:
                delivery_fees[seller.pk] = 0

        # Validate and apply coupon
        if coupon_code:
            try:
                coupon = Coupon.objects.get(
                    code=coupon_code,
                    is_active=True,
                )
                if not coupon.is_valid:
                    messages.error(
                        request,
                        'This coupon has expired or reached its usage limit.'
                    )
                    coupon = None
                elif coupon.min_order_amount and \
                     subtotal < coupon.min_order_amount:
                    messages.error(
                        request,
                        f'Minimum order of ₦{coupon.min_order_amount:,.0f} '
                        f'required for this coupon.'
                    )
                    coupon = None
                else:
                    discount_amount = coupon.calculate_discount(subtotal)
            except Coupon.DoesNotExist:
                messages.error(request, 'Invalid coupon code.')

        # Check POD eligibility
        if payment_method == 'pod':
            if not _check_pod_eligibility(request.user):
                messages.error(
                    request,
                    'You are not eligible for Pay on Delivery. '
                    'Either your monthly limit is reached or '
                    'your POD privilege has been revoked.'
                )
                payment_method = 'pay_now'

        total_amount = subtotal + total_delivery_fee - discount_amount

        # Store checkout data in session for payment step
        request.session['checkout_data'] = {
            'delivery_type': delivery_type,
            'delivery_address': delivery_address,
            'delivery_state': delivery_state,
            'delivery_city': delivery_city,
            'payment_method': payment_method,
            'coupon_code': coupon_code,
            'subtotal': float(subtotal),
            'total_delivery_fee': float(total_delivery_fee),
            'discount_amount': float(discount_amount),
            'total_amount': float(total_amount),
            'delivery_fees': {str(k): float(v) for k, v in delivery_fees.items()},  # ← fix keys too
        }

        if payment_method == 'pay_now':
            return redirect('orders:initiate_payment')
        else:
            return redirect('orders:create_pod_order')

    # GET — show checkout form
    from apps.core.views import get_exchange_rate
    exchange_rate = get_exchange_rate()

    # Nigerian states for delivery dropdown
    nigerian_states = [
        'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi',
        'Bayelsa', 'Benue', 'Borno', 'Cross River', 'Delta',
        'Ebonyi', 'Edo', 'Ekiti', 'Enugu', 'FCT', 'Gombe',
        'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi',
        'Kogi', 'Kwara', 'Lagos', 'Nasarawa', 'Niger', 'Ogun',
        'Ondo', 'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto',
        'Taraba', 'Yobe', 'Zamfara',
    ]

    return render(request, 'orders/checkout.html', {
        'cart': cart,
        'items_by_seller': items_by_seller,
        'exchange_rate': exchange_rate,
        'nigerian_states': nigerian_states,
        'flutterwave_public_key': settings.FLUTTERWAVE_PUBLIC_KEY,
    })


def initiate_payment(request):
    """
    Builds Flutterwave payment payload and
    renders payment page with FW checkout modal.
    """
    checkout_data = request.session.get('checkout_data')
    if not checkout_data:
        return redirect('orders:checkout')

    cart = get_or_create_cart(request)
    if cart.total_items == 0:
        return redirect('orders:cart')

    # Generate unique transaction reference
    tx_ref = f'NXO-{request.user.pk}-{int(timezone.now().timestamp())}'
    request.session['payment_tx_ref'] = tx_ref

    # Build subaccounts for split payment
    subaccounts = _build_payment_subaccounts(
        cart,
        checkout_data['delivery_fees'],
        checkout_data['discount_amount'],
    )

    payment_data = {
        'tx_ref': tx_ref,
        'amount': checkout_data['total_amount'],
        'currency': 'NGN',
        'redirect_url': request.build_absolute_uri(
            '/orders/payment-callback/'
        ),
        'customer': {
            'email': request.user.email,
            'name': request.user.full_name,
            'phonenumber': request.user.phone or '',
        },
        'customizations': {
            'title': 'Nexo Marketplace',
            'description': f'Order payment — {cart.total_items} item(s)',
        },
        'subaccounts': subaccounts,
        'meta': {
            'user_id': request.user.pk,
            'cart_items': cart.total_items,
        }
    }

    return render(request, 'orders/payment.html', {
        'payment_data': json.dumps(payment_data),
        'flutterwave_public_key': settings.FLUTTERWAVE_PUBLIC_KEY,
        'total_amount': checkout_data['total_amount'],
    })


def payment_callback(request):
    """
    Flutterwave redirects here after payment.
    Parses response, verifies payment, creates order atomically.
    """
    import urllib.parse

    response_data = request.GET.get('response')
    if response_data:
        try:
            decoded = urllib.parse.unquote(response_data)
            data = json.loads(decoded)
            status = data.get('status')
            tx_ref = data.get('txRef') or data.get('tx_ref')
            transaction_id = data.get('id') or data.get('transaction_id')
        except Exception:
            status = tx_ref = transaction_id = None
    else:
        status = request.GET.get('status')
        tx_ref = request.GET.get('tx_ref')
        transaction_id = request.GET.get('transaction_id')

    print(f'=== ORDER PAYMENT CALLBACK ===')
    print(f'status: {status}, tx_ref: {tx_ref}, id: {transaction_id}')

    if status != 'successful':
        messages.error(
            request,
            f'Payment was not successful. Please try again.'
        )
        return redirect('orders:checkout')

    # Verify with Flutterwave
    verified = _verify_payment(transaction_id)
    print(f'VERIFIED: {verified}')

    if not verified:
        messages.error(
            request,
            'Payment verification failed. '
            'Contact support if you were charged.'
        )
        return redirect('orders:checkout')

    # Prevent duplicate order creation
    if Order.objects.filter(fw_transaction_ref=tx_ref).exists():
        order = Order.objects.get(fw_transaction_ref=tx_ref)
        messages.info(request, 'Order already processed.')
        return redirect('orders:order_detail', order_ref=order.order_ref)

    # Get checkout data from session
    checkout_data = request.session.get('checkout_data')
    if not checkout_data:
        messages.error(
            request,
            'Session expired. Your payment was received. '
            f'Contact support with reference: {tx_ref}'
        )
        return redirect('/')

    cart = get_or_create_cart(request)

    # Create order atomically
    try:
        order = _create_order_from_cart(
            request, cart, checkout_data, tx_ref
        )
    except Exception as e:
        print(f'ORDER CREATION ERROR: {e}')
        # Log to PaymentLog for admin investigation
        PaymentLog.objects.create(
            fw_reference=tx_ref or 'UNKNOWN',
            buyer=request.user,
            amount=checkout_data.get('total_amount', 0),
            status='success',
            order_created=False,
            failure_reason=str(e),
        )
        messages.error(
            request,
            'Payment received but order creation failed. '
            f'Contact support with reference: {tx_ref}'
        )
        return redirect('/')

    # Clear cart and session data
    cart.items.all().delete()
    for key in ['checkout_data', 'payment_tx_ref']:
        request.session.pop(key, None)

    messages.success(
        request,
        f'Order {order.order_ref} placed successfully!'
    )
    return redirect('orders:order_detail', order_ref=order.order_ref)


def create_pod_order(request):
    """
    Creates order for Pay on Delivery — no payment processing.
    Order created immediately with PENDING_CASH status.
    """
    checkout_data = request.session.get('checkout_data')
    if not checkout_data:
        return redirect('orders:checkout')

    cart = get_or_create_cart(request)
    if cart.total_items == 0:
        return redirect('orders:cart')

    try:
        order = _create_order_from_cart(
            request, cart, checkout_data, None
        )
    except Exception as e:
        messages.error(request, f'Error creating order: {str(e)}')
        return redirect('orders:checkout')

    # Increment POD count for user
    request.user.pod_count_this_month += 1
    request.user.save(update_fields=['pod_count_this_month'])

    # Clear cart
    cart.items.all().delete()
    for key in ['checkout_data']:
        request.session.pop(key, None)

    messages.success(
        request,
        f'Order {order.order_ref} placed! '
        'Please have cash ready for delivery.'
    )
    return redirect('orders:order_detail', order_ref=order.order_ref)


@login_required
def order_detail(request, order_ref):
    """Shows single order details"""
    order = get_object_or_404(
        Order,
        order_ref=order_ref,
        buyer=request.user,
    )
    seller_orders = order.seller_orders.prefetch_related(
        'items__sku__variant_options',
        'items__sku__product__images',
    ).all()

    return render(request, 'orders/order_detail.html', {
        'order': order,
        'seller_orders': seller_orders,
    })


@login_required
def order_list(request):
    """Shows buyer's order history"""
    orders = Order.objects.filter(
        buyer=request.user
    ).order_by('-created_at')

    return render(request, 'orders/order_list.html', {
        'orders': orders,
    })


# ── HELPER FUNCTIONS ─────────────────────────────────────────

def _check_pod_eligibility(user):
    """
    Checks if user is eligible for POD.
    Returns True if eligible, False if not.
    """
    from django.utils import timezone

    # Permanently revoked
    if user.pod_strikes >= 3:
        return False

    # Currently suspended
    if user.pod_suspended_until and \
       user.pod_suspended_until >= timezone.now().date():
        return False

    # Check monthly limit based on account age
    from datetime import date
    account_age_months = (
        date.today() - user.date_joined.date()
    ).days // 30

    if account_age_months < 3:
        limit = settings.POD_LIMITS['new']
    elif user.pod_strikes == 0 and \
         Order.objects.filter(buyer=user).count() >= 10:
        limit = settings.POD_LIMITS['vip']
    else:
        limit = settings.POD_LIMITS['established']

    return user.pod_count_this_month < limit


def _build_payment_subaccounts(cart, delivery_fees, discount_amount):
    """
    Builds Flutterwave subaccounts array for split payment.
    Each seller gets their portion automatically.
    Platform commission deducted based on threshold.
    """
    subaccounts = []
    items_by_seller = cart.get_items_by_seller()

    for seller, items in items_by_seller.items():
        if not seller.fw_subaccount_code:
            continue

        # Calculate seller's subtotal
        seller_subtotal = sum(
            item.price_snapshot * item.quantity
            for item in items
        )
        seller_delivery = delivery_fees.get(seller.pk, 0)
        seller_total = float(seller_subtotal) + seller_delivery

        # Calculate commission
        commission_rate = _get_commission_rate(
            seller.monthly_revenue + seller_subtotal
        )
        commission_amount = seller_total * (commission_rate / 100)
        seller_payout = seller_total - commission_amount

        subaccounts.append({
            'id': seller.fw_subaccount_code,
            'transaction_charge_type': 'flat_subaccount',
            'transaction_charge': seller_payout,
        })

    return subaccounts


def _get_commission_rate(monthly_revenue):
    """Returns commission rate based on monthly revenue threshold"""
    for min_val, max_val, rate in settings.COMMISSION_TIERS:
        if min_val <= monthly_revenue < max_val:
            return rate
    return 5  # Max commission


@transaction.atomic
def _create_order_from_cart(request, cart, checkout_data, tx_ref):
    """
    Creates Order + SellerOrders + OrderItems atomically.
    All or nothing — if any step fails everything rolls back.
    Stock deducted here.
    """
    payment_method = checkout_data['payment_method']

    # Determine payment status
    if payment_method == 'pay_now':
        payment_status = Order.PaymentStatus.CONFIRMED
    else:
        payment_status = Order.PaymentStatus.PENDING_CASH

    # Create master order
    order = Order.objects.create(
        buyer=request.user,
        payment_method=payment_method,
        payment_status=payment_status,
        delivery_type=checkout_data['delivery_type'],
        delivery_address=checkout_data.get('delivery_address', ''),
        delivery_state=checkout_data.get('delivery_state', ''),
        delivery_city=checkout_data.get('delivery_city', ''),
        subtotal=checkout_data['subtotal'],
        total_delivery_fee=checkout_data['total_delivery_fee'],
        discount_amount=checkout_data['discount_amount'],
        total_amount=checkout_data['total_amount'],
        fw_transaction_ref=tx_ref or '',
    )

    # Handle coupon
    coupon_code = checkout_data.get('coupon_code')
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code=coupon_code, is_active=True)
            order.coupon = coupon
            order.save(update_fields=['coupon'])
            # Record coupon usage
            CouponUsage.objects.create(
                coupon=coupon,
                user=request.user,
                order=order,
                discount_amount=checkout_data['discount_amount'],
            )
            # Increment coupon usage count
            coupon.uses_count += 1
            coupon.save(update_fields=['uses_count'])
        except Coupon.DoesNotExist:
            pass

    # Create SellerOrder per seller + OrderItems
    items_by_seller = cart.get_items_by_seller()
    delivery_fees = checkout_data.get('delivery_fees', {})

    for seller, items in items_by_seller.items():
        seller_subtotal = sum(
            item.price_snapshot * item.quantity
            for item in items
        )
        seller_delivery = delivery_fees.get(str(seller.pk), 0)

        # Calculate commission
        commission_rate = _get_commission_rate(
            seller.monthly_revenue + seller_subtotal
        )
        commission_amount = float(seller_subtotal) * (commission_rate / 100)
        seller_payout = float(seller_subtotal) + seller_delivery - commission_amount

        # Determine seller order status
        if payment_method == 'pay_now':
            seller_status = SellerOrder.Status.PAYMENT_CONFIRMED
        else:
            seller_status = SellerOrder.Status.PENDING

        seller_order = SellerOrder.objects.create(
            order=order,
            seller=seller,
            status=seller_status,
            subtotal=seller_subtotal,
            delivery_fee=seller_delivery,
            commission_rate=commission_rate,
            commission_amount=commission_amount,
            seller_payout=seller_payout,
        )

        # Create order items + deduct stock
        for item in items:
            # Build variant description snapshot
            variant_desc = ' + '.join([
                f'{opt.variant_type.name}: {opt.value}'
                for opt in item.sku.variant_options.all()
            ])

            OrderItem.objects.create(
                seller_order=seller_order,
                sku=item.sku,
                quantity=item.quantity,
                unit_price=item.price_snapshot,
                product_name=item.sku.product.name,
                product_sku_code=item.sku.sku_code,
                variant_description=variant_desc,
            )

            # Deduct stock atomically
            # select_for_update locks the row preventing race conditions
            sku = ProductSKU.objects.select_for_update().get(
                pk=item.sku.pk
            )
            if sku.stock < item.quantity:
                raise ValueError(
                    f'Insufficient stock for {item.sku.product.name}. '
                    f'Only {sku.stock} available.'
                )
            sku.stock -= item.quantity
            sku.save(update_fields=['stock'])

            # Update seller monthly revenue
            seller.monthly_revenue += seller_subtotal
            seller.save(update_fields=['monthly_revenue'])

            # Trigger product visibility check via Celery
            try:
                from apps.products.task import update_product_visibility
                update_product_visibility.delay(item.sku.product.pk)
            except Exception:
                # Redis not running in dev? run synchronously instead
                from apps.products.task import update_product_visibility
                update_product_visibility(item.sku.product.pk)

    # Log payment
    if tx_ref:
        PaymentLog.objects.create(
            fw_reference=tx_ref,
            buyer=request.user,
            order=order,
            payment_type='purchase',
            status='success',
            amount=checkout_data['total_amount'],
            order_created=True,
        )

    return order


def _verify_payment(transaction_id):
    """Verifies payment with Flutterwave API"""
    if not transaction_id:
        return False
    try:
        response = requests.get(
            f'https://api.flutterwave.com/v3/transactions/{transaction_id}/verify',
            headers={
                'Authorization': f'Bearer {settings.FLUTTERWAVE_SECRET_KEY}',
            },
            timeout=30,
        )
        data = response.json()
        return (
            data.get('status') == 'success' and
            data.get('data', {}).get('status') == 'successful'
        )
    except Exception:
        return False

