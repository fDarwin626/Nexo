# apps/dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count, Q

from .decorators import seller_required
from apps.stores.models import SellerProfile, Subscription, DeliveryZone
from apps.products.models import Product, ProductSKU
from apps.orders.models import SellerOrder
from apps.core.models import Coupon
from apps.disputes.models import Dispute
from apps.core.utils import STATE_BORDERS


# ─────────────────────────────────────────────────────────────
# SELLER DASHBOARD HOME
# ─────────────────────────────────────────────────────────────

@login_required
@seller_required
def seller_dashboard_home(request):
    seller = request.user.seller_profile

    # Subscription
    active_sub = seller.subscriptions.filter(
        status='active'
    ).order_by('-created_at').first()

    # Revenue
    all_time_revenue = seller.seller_orders.filter(
        status__in=[
            SellerOrder.Status.DELIVERED,
            SellerOrder.Status.DELIVERED_PAID,
            SellerOrder.Status.COMPLETED,
        ]
    ).aggregate(total=Sum('seller_payout'))['total'] or 0

    # Recent orders (last 5)
    recent_orders = seller.seller_orders.select_related(
        'order'
    ).order_by('-created_at')[:5]

    # Low stock products (total_stock > 0 but any SKU <= 3)
    low_stock_skus = ProductSKU.objects.filter(
        product__seller=seller,
        product__is_active=True,
        stock__gt=0,
        stock__lte=3,
    ).select_related('product')[:5]

    # Quick stats
    total_products = seller.products.filter(is_active=True).count()
    active_orders = seller.seller_orders.filter(
        status__in=['pending', 'payment_confirmed', 'processing', 'shipped', 'out_for_delivery']
    ).count()
    open_disputes = Dispute.objects.filter(
        seller=seller,
        status__in=['open', 'seller_responded', 'escalated']
    ).count()

    return render(request, 'dashboard/seller/home.html', {
        'seller': seller,
        'active_sub': active_sub,
        'all_time_revenue': all_time_revenue,
        'recent_orders': recent_orders,
        'low_stock_skus': low_stock_skus,
        'total_products': total_products,
        'active_orders': active_orders,
        'open_disputes': open_disputes,
    })


# ─────────────────────────────────────────────────────────────
# SELLER PRODUCTS
# ─────────────────────────────────────────────────────────────

@login_required
@seller_required
def seller_products(request):
    seller = request.user.seller_profile
    search = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')

    products = seller.products.prefetch_related('skus', 'images').order_by('-created_at')

    if search:
        products = products.filter(name__icontains=search)

    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'out_of_stock':
        products = products.filter(is_active=False, restock_deadline__isnull=False)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)

    # Tag each product with a status label for the template
    for product in products:
        stock = product.total_stock
        if not product.is_active and product.restock_deadline:
            product.status_label = 'pending-delete'
        elif stock == 0:
            product.status_label = 'out-of-stock'
        elif stock <= 3:
            product.status_label = 'low-stock'
        else:
            product.status_label = 'active'

    return render(request, 'dashboard/seller/products.html', {
        'seller': seller,
        'products': products,
        'search': search,
        'status_filter': status_filter,
    })


# ─────────────────────────────────────────────────────────────
# SELLER ORDERS
# ─────────────────────────────────────────────────────────────

@login_required
@seller_required
def seller_orders(request):
    seller = request.user.seller_profile
    status_filter = request.GET.get('status', '')

    orders = seller.seller_orders.select_related(
        'order'
    ).prefetch_related('items').order_by('-created_at')

    if status_filter:
        orders = orders.filter(status=status_filter)

    return render(request, 'dashboard/seller/orders.html', {
        'seller': seller,
        'orders': orders,
        'status_filter': status_filter,
        'status_choices': SellerOrder.Status.choices,
    })


@login_required
@seller_required
def mark_shipped(request, order_id):
    seller = request.user.seller_profile
    seller_order = get_object_or_404(SellerOrder, pk=order_id, seller=seller)

    if request.method == 'POST':
        tracking = request.POST.get('tracking_number', '').strip()

        if seller_order.status not in ['payment_confirmed', 'processing']:
            messages.error(request, 'This order cannot be marked as shipped.')
            return redirect('dashboard:seller_orders')

        seller_order.status = SellerOrder.Status.SHIPPED
        seller_order.tracking_number = tracking
        seller_order.shipped_at = timezone.now()
        seller_order.save(update_fields=['status', 'tracking_number', 'shipped_at'])

        messages.success(request, f'Order marked as shipped.')

    return redirect('dashboard:seller_orders')


@login_required
@seller_required
def mark_delivered(request, order_id):
    seller = request.user.seller_profile
    seller_order = get_object_or_404(SellerOrder, pk=order_id, seller=seller)

    if request.method == 'POST':
        is_pod = seller_order.order.payment_method == 'pod'

        if seller_order.status not in ['shipped', 'out_for_delivery']:
            messages.error(request, 'This order cannot be marked as delivered.')
            return redirect('dashboard:seller_orders')

        if is_pod:
            seller_order.status = SellerOrder.Status.DELIVERED_PAID
        else:
            seller_order.status = SellerOrder.Status.DELIVERED

        seller_order.delivered_at = timezone.now()
        seller_order.save(update_fields=['status', 'delivered_at'])

        messages.success(request, 'Order marked as delivered.')

    return redirect('dashboard:seller_orders')


# ─────────────────────────────────────────────────────────────
# SELLER COUPONS
# ─────────────────────────────────────────────────────────────

@login_required
@seller_required
def seller_coupons(request):
    seller = request.user.seller_profile
    coupons = seller.coupons.order_by('-created_at')

    return render(request, 'dashboard/seller/coupons.html', {
        'seller': seller,
        'coupons': coupons,
    })


@login_required
@seller_required
def create_coupon(request):
    seller = request.user.seller_profile

    if request.method == 'POST':
        discount_value = request.POST.get('discount_value')
        min_order = request.POST.get('min_order_amount') or None
        max_uses = request.POST.get('max_uses', 100)
        valid_from = request.POST.get('valid_from')
        valid_until = request.POST.get('valid_until')

        # Validate discount range
        try:
            discount_value = float(discount_value)
            if not 5 <= discount_value <= 50:
                messages.error(request, 'Discount must be between 5% and 50%.')
                return redirect('dashboard:create_coupon')
        except (TypeError, ValueError):
            messages.error(request, 'Invalid discount value.')
            return redirect('dashboard:create_coupon')

        Coupon.objects.create(
            seller=seller,
            created_by=request.user,
            discount_type='percentage',
            discount_value=discount_value,
            min_order_amount=min_order,
            max_uses=max_uses,
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=True,
        )

        messages.success(request, 'Coupon created successfully.')
        return redirect('dashboard:seller_coupons')

    return render(request, 'dashboard/seller/create_coupon.html', {
        'seller': seller,
    })


@login_required
@seller_required
def deactivate_coupon(request, coupon_id):
    seller = request.user.seller_profile
    coupon = get_object_or_404(Coupon, pk=coupon_id, seller=seller)

    if request.method == 'POST':
        coupon.is_active = False
        coupon.save(update_fields=['is_active'])
        messages.success(request, f'Coupon {coupon.code} deactivated.')

    return redirect('dashboard:seller_coupons')


# ─────────────────────────────────────────────────────────────
# SELLER SUBSCRIPTION
# ─────────────────────────────────────────────────────────────

@login_required
@seller_required
def seller_subscription(request):
    seller = request.user.seller_profile
    active_sub = seller.subscriptions.filter(
        status='active'
    ).order_by('-created_at').first()

    all_subs = seller.subscriptions.order_by('-created_at')

    return render(request, 'dashboard/seller/subscription.html', {
        'seller': seller,
        'active_sub': active_sub,
        'all_subs': all_subs,
    })


# ─────────────────────────────────────────────────────────────
# SELLER STORE SETTINGS
# ─────────────────────────────────────────────────────────────
@login_required
@seller_required
def seller_store_settings(request):
    seller = request.user.seller_profile
    from apps.stores.models import StorefrontImage
    from django.utils import timezone as tz
    from datetime import timedelta

    storefront_images = StorefrontImage.objects.filter(is_active=True)

    if request.method == 'POST':
        action = request.POST.get('action', 'settings')

        # ── HEADER IMAGE SELECTION ──
        if action == 'select_header':
            image_id = request.POST.get('image_id')
            if image_id:
                try:
                    img = StorefrontImage.objects.get(pk=image_id, is_active=True)
                    seller.header_image = img
                    seller.save(update_fields=['header_image'])
                    messages.success(request, 'Header image updated.')
                except StorefrontImage.DoesNotExist:
                    messages.error(request, 'Image not found.')
            return redirect('dashboard:seller_settings')

        # ── STORE NAME CHANGE ──
        new_store_name = request.POST.get('store_name', '').strip()
        if new_store_name and new_store_name != seller.store_name:
            # Check 3-month rule
            if seller.store_name_last_changed:
                days_since = (tz.now() - seller.store_name_last_changed).days
                if days_since < 90:
                    days_left = 90 - days_since
                    messages.error(
                        request,
                        f'Store name can only be changed once every 3 months. '
                        f'{days_left} days remaining.'
                    )
                    return redirect('dashboard:seller_settings')
            from django.utils.text import slugify
            seller.store_name = new_store_name
            seller.store_slug = slugify(new_store_name)
            seller.store_name_last_changed = tz.now()

        # ── OTHER SETTINGS ──
        seller.store_description = request.POST.get('store_description', '').strip()
        seller.whatsapp_number = request.POST.get('whatsapp_number', '').strip()
        seller.banner_headline = request.POST.get('banner_headline', '').strip()
        seller.banner_subtext = request.POST.get('banner_subtext', '').strip()
        seller.banner_bg_color = request.POST.get('banner_bg_color', '#111118').strip()
        seller.banner_accent_color = request.POST.get('banner_accent_color', '#FF4D00').strip()
        seller.allow_pod = request.POST.get('allow_pod') == 'on'
        seller.is_on_vacation = request.POST.get('is_on_vacation') == 'on'
        vacation_return = request.POST.get('vacation_return_date', '').strip()
        seller.vacation_return_date = vacation_return if vacation_return else None

        if 'logo' in request.FILES:
            logo_file = request.FILES['logo']
            if not logo_file.name.lower().endswith('.png'):
                messages.error(request, 'Store logo must be a PNG file.')
                return redirect('dashboard:seller_settings')
            seller.logo = logo_file

        seller.save()
        messages.success(request, 'Store settings updated.')
        return redirect('dashboard:seller_settings')

    # Check if name change is allowed
    from datetime import timedelta
    can_change_name = True
    name_change_days_left = 0
    if seller.store_name_last_changed:
        days_since = (timezone.now() - seller.store_name_last_changed).days
        if days_since < 90:
            can_change_name = False
            name_change_days_left = 90 - days_since

    return render(request, 'dashboard/seller/settings.html', {
        'seller': seller,
        'storefront_images': storefront_images,
        'can_change_name': can_change_name,
        'name_change_days_left': name_change_days_left,
    })

# ─────────────────────────────────────────────────────────────
# SELLER DELIVERY ZONES
# ─────────────────────────────────────────────────────────────

@login_required
@seller_required
def seller_delivery_zones(request):
    seller = request.user.seller_profile
    zones = seller.delivery_zones.order_by('state')

    # Get allowed states for this seller
    # Based on their store state + bordering states
    seller_state = seller.delivery_zones.values_list(
        'state', flat=True
    ).first()

    allowed_states = []
    if seller_state and seller_state in STATE_BORDERS:
        allowed_states = [seller_state] + STATE_BORDERS.get(seller_state, [])
    else:
        # Fallback — all Nigerian states
        allowed_states = list(STATE_BORDERS.keys())

    # States seller hasn't added yet
    existing_states = zones.values_list('state', flat=True)
    available_states = [s for s in allowed_states if s not in existing_states]

    if request.method == 'POST':
        state = request.POST.get('state', '').strip()
        fee = request.POST.get('fee', '0').strip()
        estimated_days = request.POST.get('estimated_days', 1)

        if state not in allowed_states:
            messages.error(request, f'{state} is outside your delivery boundary.')
            return redirect('dashboard:seller_delivery')

        if DeliveryZone.objects.filter(seller=seller, state=state).exists():
            messages.error(request, f'You already have a zone for {state}.')
            return redirect('dashboard:seller_delivery')

        DeliveryZone.objects.create(
            seller=seller,
            state=state,
            fee=fee,
            estimated_days=estimated_days,
        )
        messages.success(request, f'Delivery zone for {state} added.')
        return redirect('dashboard:seller_delivery')

    return render(request, 'dashboard/seller/delivery.html', {
        'seller': seller,
        'zones': zones,
        'available_states': available_states,
    })


@login_required
@seller_required
def delete_delivery_zone(request, zone_id):
    seller = request.user.seller_profile
    zone = get_object_or_404(DeliveryZone, pk=zone_id, seller=seller)

    if request.method == 'POST':
        state = zone.state
        zone.delete()
        messages.success(request, f'Delivery zone for {state} removed.')

    return redirect('dashboard:seller_delivery')


# ─────────────────────────────────────────────────────────────
# SELLER REVENUE
# ─────────────────────────────────────────────────────────────

@login_required
@seller_required
def seller_revenue(request):
    seller = request.user.seller_profile

    completed_orders = seller.seller_orders.filter(
        status__in=[
            SellerOrder.Status.DELIVERED,
            SellerOrder.Status.DELIVERED_PAID,
            SellerOrder.Status.COMPLETED,
        ]
    ).select_related('order').order_by('-created_at')

    total_revenue = completed_orders.aggregate(
        total=Sum('seller_payout')
    )['total'] or 0

    return render(request, 'dashboard/seller/revenue.html', {
        'seller': seller,
        'completed_orders': completed_orders,
        'total_revenue': total_revenue,
        'monthly_revenue': seller.monthly_revenue,
        'commission_rate': seller.current_commission_rate,
    })


# ─────────────────────────────────────────────────────────────
# SELLER DISPUTES
# ─────────────────────────────────────────────────────────────

@login_required
@seller_required
def seller_disputes(request):
    seller = request.user.seller_profile
    disputes = Dispute.objects.filter(
        seller=seller
    ).select_related('seller_order__order', 'buyer').order_by('-created_at')

    return render(request, 'dashboard/seller/disputes.html', {
        'seller': seller,
        'disputes': disputes,
    })


@login_required
@seller_required
def seller_dispute_detail(request, dispute_id):
    seller = request.user.seller_profile
    dispute = get_object_or_404(Dispute, pk=dispute_id, seller=seller)
    messages_qs = dispute.messages.order_by('created_at')

    if request.method == 'POST':
        # Seller can only reply — not initiate
        message_text = request.POST.get('message', '').strip()

        # Check there's at least one admin message to reply to
        admin_message_exists = messages_qs.filter(sender_type='admin').exists()
        if not admin_message_exists:
            messages.error(request, 'You can only reply after admin sends a message.')
            return redirect('dashboard:seller_dispute_detail', dispute_id=dispute_id)

        if message_text:
            from apps.disputes.models import DisputeMessage
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=request.user,
                sender_type='seller',
                message=message_text,
            )
            messages.success(request, 'Reply sent.')

        return redirect('dashboard:seller_dispute_detail', dispute_id=dispute_id)

    return render(request, 'dashboard/seller/dispute_detail.html', {
        'seller': seller,
        'dispute': dispute,
        'dispute_messages': messages_qs,
    })


# ─────────────────────────────────────────────────────────────
# ADMIN DASHBOARD — SECTION 9
# ─────────────────────────────────────────────────────────────

from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.conf import settings as django_settings

from apps.accounts.models import User, BanRecord
from apps.payments.models import PaymentLog, ReserveFund
from apps.core.models import ExchangeRate, SiteSettings, Coupon


@staff_member_required(login_url='/auth/login/')
def admin_dashboard(request):
    # Platform GMV — all confirmed payments
    gmv = PaymentLog.objects.filter(
        status='success',
        payment_type='purchase'
    ).aggregate(total=Sum('amount'))['total'] or 0

    # Sellers
    active_sellers = SellerProfile.objects.filter(
        status='active', is_approved=True
    ).count()

    pending_sellers = SellerProfile.objects.filter(
        status='pending', is_approved=False
    ).order_by('-created_at')

    # Disputes
    escalated_disputes = Dispute.objects.filter(
        status='escalated'
    ).select_related(
        'seller_order__order', 'buyer', 'seller'
    ).order_by('-created_at')

    # Reserve fund
    reserve_fund = ReserveFund.objects.first()

    # Recent payment logs
    recent_payments = PaymentLog.objects.select_related(
        'buyer', 'order'
    ).order_by('-created_at')[:20]

    # Fraud — users with high fraud score
    fraud_users = User.objects.filter(
        fraud_score__gte=3
    ).order_by('-fraud_score')[:20]

    # Ban records
    recent_bans = BanRecord.objects.select_related(
        'original_account'
    ).order_by('-created_at')[:20]

    # Exchange rate
    current_rate = ExchangeRate.objects.filter(
        is_active=True
    ).first()

    # Platform coupons
    platform_coupons = Coupon.objects.filter(
        seller__isnull=True
    ).order_by('-created_at')

    # Top selling products
    from apps.orders.models import OrderItem
    from django.db.models import Sum as DSum
    top_products = OrderItem.objects.values(
        'product_name'
    ).annotate(
        total_sold=DSum('quantity')
    ).order_by('-total_sold')[:10]

    # Site settings
    site_settings = SiteSettings.get_settings()

    return render(request, 'dashboard/admin/home.html', {
        'gmv': gmv,
        'active_sellers': active_sellers,
        'pending_sellers': pending_sellers,
        'escalated_disputes': escalated_disputes,
        'reserve_fund': reserve_fund,
        'recent_payments': recent_payments,
        'fraud_users': fraud_users,
        'recent_bans': recent_bans,
        'current_rate': current_rate,
        'platform_coupons': platform_coupons,
        'top_products': top_products,
        'site_settings': site_settings,
    })


@staff_member_required(login_url='/auth/login/')
def approve_seller(request, seller_id):
    seller = get_object_or_404(SellerProfile, pk=seller_id)

    if request.method == 'POST':
        seller.is_approved = True
        seller.status = SellerProfile.StoreStatus.ACTIVE
        seller.approved_by = request.user
        seller.approved_at = timezone.now()
        seller.save(update_fields=[
            'is_approved', 'status', 'approved_by', 'approved_at'
        ])

        # Update user role to seller
        seller.user.role = 'seller'
        seller.user.save(update_fields=['role'])

        # Send approval email
        _send_seller_approval_email(seller)

        messages.success(
            request,
            f'{seller.store_name} has been approved and is now live.'
        )

    return redirect('dashboard:admin')


@staff_member_required(login_url='/auth/login/')
def reject_seller(request, seller_id):
    seller = get_object_or_404(SellerProfile, pk=seller_id)

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'Please provide a rejection reason.')
            return redirect('dashboard:admin')

        seller.rejection_reason = reason
        seller.status = SellerProfile.StoreStatus.PENDING
        seller.save(update_fields=['rejection_reason', 'status'])

        # Send rejection email
        _send_seller_rejection_email(seller, reason)

        messages.success(
            request,
            f'{seller.store_name} application rejected. Seller notified.'
        )

    return redirect('dashboard:admin')


@staff_member_required(login_url='/auth/login/')
def set_exchange_rate(request):
    if request.method == 'POST':
        rate = request.POST.get('usd_to_ngn', '').strip()
        try:
            rate = float(rate)
            if rate <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, 'Invalid exchange rate.')
            return redirect('dashboard:admin')

        ExchangeRate.objects.create(
            usd_to_ngn=rate,
            is_active=True,
            set_by=request.user,
        )
        messages.success(request, f'Exchange rate updated: $1 = ₦{rate}')

    return redirect('dashboard:admin')


@staff_member_required(login_url='/auth/login/')
def create_platform_coupon(request):
    if request.method == 'POST':
        discount_value = request.POST.get('discount_value')
        max_uses = request.POST.get('max_uses', 100)
        valid_from = request.POST.get('valid_from')
        valid_until = request.POST.get('valid_until')
        budget_cap = request.POST.get('budget_cap') or None

        try:
            discount_value = float(discount_value)
            if not 5 <= discount_value <= 50:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, 'Discount must be between 5% and 50%.')
            return redirect('dashboard:admin')

        Coupon.objects.create(
            seller=None,
            created_by=request.user,
            discount_type='percentage',
            discount_value=discount_value,
            max_uses=max_uses,
            valid_from=valid_from,
            valid_until=valid_until,
            budget_cap=budget_cap,
            is_active=True,
        )
        messages.success(request, 'Platform coupon created.')

    return redirect('dashboard:admin')


@staff_member_required(login_url='/auth/login/')
def ban_user(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        ban_type = request.POST.get('ban_type', 'hard')
        reason = request.POST.get('reason', '').strip()

        if not reason:
            messages.error(request, 'Ban reason is required.')
            return redirect('dashboard:admin')

        target_user.ban_status = ban_type
        target_user.ban_reason = reason
        target_user.banned_at = timezone.now()
        target_user.save(update_fields=['ban_status', 'ban_reason', 'banned_at'])

        BanRecord.objects.create(
            original_account=target_user,
            device_fingerprint=target_user.device_fingerprint or '',
            ban_type=ban_type,
            ban_reason=reason,
        )

        messages.success(request, f'{target_user.email} has been banned ({ban_type}).')

    return redirect('dashboard:admin')


@staff_member_required(login_url='/auth/login/')
def suspend_seller(request, seller_id):
    seller = get_object_or_404(SellerProfile, pk=seller_id)

    if request.method == 'POST':
        seller.status = SellerProfile.StoreStatus.SUSPENDED
        seller.save(update_fields=['status'])

        # Hide all products
        seller.products.update(is_active=False)

        messages.success(
            request,
            f'{seller.store_name} has been suspended. All products hidden.'
        )

    return redirect('dashboard:admin')


# ── EMAIL HELPERS ─────────────────────────────────────────────

def _send_seller_approval_email(seller):
    send_mail(
        subject='Your Nexo store has been approved!',
        message=(
            f'Hi {seller.user.get_short_name()},\n\n'
            f'Great news! Your store "{seller.store_name}" has been approved '
            f'and is now live on Nexo.\n\n'
            f'Start adding products at:\n'
            f'{django_settings.FRONTEND_URL}/products/add/\n\n'
            f'The Nexo Team'
        ),
        from_email=django_settings.DEFAULT_FROM_EMAIL,
        recipient_list=[seller.user.email],
        fail_silently=True,
    )


def _send_seller_rejection_email(seller, reason):
    send_mail(
        subject='Update on your Nexo seller application',
        message=(
            f'Hi {seller.user.get_short_name()},\n\n'
            f'Unfortunately your store application for "{seller.store_name}" '
            f'was not approved at this time.\n\n'
            f'Reason: {reason}\n\n'
            f'You may reapply after addressing the issue above.\n\n'
            f'The Nexo Team'
        ),
        from_email=django_settings.DEFAULT_FROM_EMAIL,
        recipient_list=[seller.user.email],
        fail_silently=True,
    )