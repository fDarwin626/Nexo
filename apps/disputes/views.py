# apps/disputes/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
import requests

from .models import Dispute, DisputeMessage, SellerStrike
from apps.orders.models import SellerOrder, Order
from apps.stores.models import SellerProfile
from apps.payments.models import ReserveFund, ReserveFundLog
from apps.notifications.models import Notification


# ─────────────────────────────────────────────────────────────
# BUYER — OPEN DISPUTE
# ─────────────────────────────────────────────────────────────

@login_required
def open_dispute(request, seller_order_id):
    """
    Buyer opens a dispute against a seller order.
    Only allowed if:
    - Order belongs to this buyer
    - Order status is delivered or completed
    - No dispute already exists for this order
    """
    seller_order = get_object_or_404(
        SellerOrder,
        pk=seller_order_id,
        order__buyer=request.user,
    )

    # Check order is in a disputable state
    disputable_statuses = [
        SellerOrder.Status.DELIVERED,
        SellerOrder.Status.DELIVERED_PAID,
        SellerOrder.Status.COMPLETED,
        SellerOrder.Status.SHIPPED,
    ]
    if seller_order.status not in disputable_statuses:
        messages.error(
            request,
            'You can only open a dispute for delivered or shipped orders.'
        )
        return redirect('orders:order_detail', order_ref=seller_order.order.order_ref)

    # Check no dispute already exists
    if hasattr(seller_order, 'dispute'):
        messages.info(request, 'A dispute already exists for this order.')
        return redirect('disputes:detail', dispute_id=seller_order.dispute.pk)

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        description = request.POST.get('description', '').strip()

        if not reason or not description:
            messages.error(request, 'Please fill in all required fields.')
            return redirect('disputes:open', seller_order_id=seller_order_id)

        if reason not in dict(Dispute.Reason.choices):
            messages.error(request, 'Invalid dispute reason.')
            return redirect('disputes:open', seller_order_id=seller_order_id)

        with transaction.atomic():
            dispute = Dispute.objects.create(
                seller_order=seller_order,
                buyer=request.user,
                seller=seller_order.seller,
                reason=reason,
                description=description,
                status=Dispute.Status.OPEN,
                # 48hr deadline for seller to respond
                seller_response_deadline=timezone.now() + timezone.timedelta(hours=48),
            )

            # Handle evidence uploads
            photos = ['evidence_photo_1', 'evidence_photo_2', 'evidence_photo_3']
            for field in photos:
                if field in request.FILES:
                    setattr(dispute, field, request.FILES[field])

            evidence_video = request.POST.get('evidence_video_url', '').strip()
            if evidence_video:
                dispute.evidence_video_url = evidence_video

            dispute.save()

            # Update seller order status
            seller_order.status = SellerOrder.Status.DISPUTED
            seller_order.save(update_fields=['status'])

            # Notify seller
            Notification.objects.create(
                recipient=seller_order.seller.user,
                notification_type='dispute_opened',
                title='Dispute Opened Against Your Order',
                message=(
                    f'A dispute has been opened for order '
                    f'{seller_order.order.order_ref}. '
                    f'You have 48 hours to respond.'
                ),
                link=f'/dashboard/seller/disputes/{dispute.pk}/',
                related_object_id=dispute.pk,
                related_object_type='dispute',
            )

            # Notify admin
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admins = User.objects.filter(is_staff=True)
            for admin in admins:
                Notification.objects.create(
                    recipient=admin,
                    notification_type='dispute_opened',
                    title='New Dispute Opened',
                    message=(
                        f'Dispute opened for order '
                        f'{seller_order.order.order_ref} '
                        f'against {seller_order.seller.store_name}.'
                    ),
                    link=f'/disputes/admin/{dispute.pk}/',
                    related_object_id=dispute.pk,
                    related_object_type='dispute',
                )

        messages.success(
            request,
            'Dispute opened successfully. '
            'The seller has 48 hours to respond.'
        )
        return redirect('disputes:detail', dispute_id=dispute.pk)

    return render(request, 'disputes/open.html', {
        'seller_order': seller_order,
        'reason_choices': Dispute.Reason.choices,
    })


# ─────────────────────────────────────────────────────────────
# BUYER — VIEW DISPUTE
# ─────────────────────────────────────────────────────────────

@login_required
def dispute_detail(request, dispute_id):
    """Buyer views their dispute status and thread"""
    dispute = get_object_or_404(
        Dispute,
        pk=dispute_id,
        buyer=request.user,
    )
    dispute_messages = dispute.messages.order_by('created_at')

    return render(request, 'disputes/detail.html', {
        'dispute': dispute,
        'dispute_messages': dispute_messages,
    })


@login_required
def my_disputes(request):
    """Buyer views all their disputes"""
    disputes = Dispute.objects.filter(
        buyer=request.user
    ).select_related(
        'seller_order__order', 'seller'
    ).order_by('-created_at')

    return render(request, 'disputes/my_disputes.html', {
        'disputes': disputes,
    })


# ─────────────────────────────────────────────────────────────
# ADMIN — DISPUTE LIST
# ─────────────────────────────────────────────────────────────

@staff_member_required(login_url='/auth/login/')
def admin_dispute_list(request):
    """Admin views all disputes with filter"""
    status_filter = request.GET.get('status', '')

    disputes = Dispute.objects.select_related(
        'seller_order__order', 'buyer', 'seller'
    ).order_by('-created_at')

    if status_filter:
        disputes = disputes.filter(status=status_filter)

    return render(request, 'disputes/admin_list.html', {
        'disputes': disputes,
        'status_filter': status_filter,
        'status_choices': Dispute.Status.choices,
    })


# ─────────────────────────────────────────────────────────────
# ADMIN — DISPUTE DETAIL + ACTIONS
# ─────────────────────────────────────────────────────────────

@staff_member_required(login_url='/auth/login/')
def admin_dispute_detail(request, dispute_id):
    """Admin views full dispute with all evidence and messages"""
    dispute = get_object_or_404(Dispute, pk=dispute_id)
    dispute_messages = dispute.messages.order_by('created_at')
    strikes = dispute.strikes.all()

    return render(request, 'disputes/admin_detail.html', {
        'dispute': dispute,
        'dispute_messages': dispute_messages,
        'strikes': strikes,
        'status_choices': Dispute.Status.choices,
        'strike_level_choices': SellerStrike.StrikeLevel.choices,
    })


@staff_member_required(login_url='/auth/login/')
def admin_send_message(request, dispute_id):
    """
    Admin sends message to seller in dispute thread.
    Admin INITIATES — seller can only reply.
    """
    dispute = get_object_or_404(Dispute, pk=dispute_id)

    if request.method == 'POST':
        message_text = request.POST.get('message', '').strip()

        if not message_text:
            messages.error(request, 'Message cannot be empty.')
            return redirect('disputes:admin_detail', dispute_id=dispute_id)

        DisputeMessage.objects.create(
            dispute=dispute,
            sender=request.user,
            sender_type='admin',
            message=message_text,
        )

        # Notify seller
        Notification.objects.create(
            recipient=dispute.seller.user,
            notification_type='dispute_update',
            title='Admin Message on Your Dispute',
            message='Admin has sent you a message regarding a dispute. Please respond.',
            link=f'/dashboard/seller/disputes/{dispute.pk}/',
            related_object_id=dispute.pk,
            related_object_type='dispute',
        )

        messages.success(request, 'Message sent to seller.')

    return redirect('disputes:admin_detail', dispute_id=dispute_id)


@staff_member_required(login_url='/auth/login/')
def admin_resolve_dispute(request, dispute_id):
    """
    Admin resolves dispute with binding decision.
    Can issue refund from reserve fund or seller payout.
    """
    dispute = get_object_or_404(Dispute, pk=dispute_id)

    if request.method == 'POST':
        resolution = request.POST.get('resolution', '').strip()
        admin_decision = request.POST.get('admin_decision', '').strip()
        compensation_amount = request.POST.get('compensation_amount', '').strip()
        compensation_source = request.POST.get('compensation_source', '').strip()

        if not resolution or not admin_decision:
            messages.error(request, 'Resolution type and decision text are required.')
            return redirect('disputes:admin_detail', dispute_id=dispute_id)

        if resolution not in dict(Dispute.Status.choices):
            messages.error(request, 'Invalid resolution type.')
            return redirect('disputes:admin_detail', dispute_id=dispute_id)

        with transaction.atomic():
            dispute.status = resolution
            dispute.admin_decision = admin_decision
            dispute.resolved_by = request.user
            dispute.resolved_at = timezone.now()

            # Handle compensation
            if compensation_amount:
                try:
                    comp_amount = float(compensation_amount)
                    dispute.compensation_amount = comp_amount
                    dispute.compensation_source = compensation_source

                    # Deduct from reserve fund if applicable
                    if compensation_source in ['reserve_fund', 'both']:
                        reserve = ReserveFund.objects.first()
                        if reserve:
                            fund_amount = comp_amount if compensation_source == 'reserve_fund' \
                                else comp_amount * 0.5
                            reserve.balance -= fund_amount
                            reserve.save(update_fields=['balance'])

                            ReserveFundLog.objects.create(
                                reserve_fund=reserve,
                                transaction_type='disbursement',
                                amount=-fund_amount,
                                balance_after=reserve.balance,
                                reference=dispute.seller_order.order.order_ref,
                                note=f'Dispute {dispute.pk} compensation to buyer',
                                created_by=request.user,
                            )

                    # Attempt Flutterwave refund if pay_now order
                    if dispute.seller_order.order.payment_method == 'pay_now':
                        fw_ref = _process_flutterwave_refund(
                            dispute.seller_order.order.fw_transaction_ref,
                            comp_amount,
                        )
                        if fw_ref:
                            dispute.refund_fw_reference = fw_ref

                except (ValueError, TypeError):
                    messages.error(request, 'Invalid compensation amount.')
                    return redirect('disputes:admin_detail', dispute_id=dispute_id)

            dispute.save()

            # Update seller order status
            seller_order = dispute.seller_order
            if resolution == Dispute.Status.RESOLVED_REFUND:
                seller_order.status = SellerOrder.Status.REFUNDED
            else:
                seller_order.status = SellerOrder.Status.COMPLETED
            seller_order.save(update_fields=['status'])

            # Notify buyer
            Notification.objects.create(
                recipient=dispute.buyer,
                notification_type='dispute_update',
                title='Your Dispute Has Been Resolved',
                message=f'Admin decision: {admin_decision[:100]}',
                link=f'/disputes/{dispute.pk}/',
                related_object_id=dispute.pk,
                related_object_type='dispute',
            )

            # Notify seller
            Notification.objects.create(
                recipient=dispute.seller.user,
                notification_type='dispute_update',
                title='Dispute Resolved',
                message=f'The dispute for order {seller_order.order.order_ref} has been resolved.',
                link=f'/dashboard/seller/disputes/{dispute.pk}/',
                related_object_id=dispute.pk,
                related_object_type='dispute',
            )

        messages.success(request, 'Dispute resolved successfully.')

    return redirect('disputes:admin_detail', dispute_id=dispute_id)


@staff_member_required(login_url='/auth/login/')
def admin_issue_strike(request, dispute_id):
    """
    Admin issues a strike to seller.
    Strike ladder:
    1 = Warning
    2 = Forced refund
    3 = Store suspended
    4 = Permanent ban
    """
    dispute = get_object_or_404(Dispute, pk=dispute_id)

    if request.method == 'POST':
        level = request.POST.get('level', '').strip()
        reason = request.POST.get('reason', '').strip()
        action_taken = request.POST.get('action_taken', '').strip()

        if not level or not reason:
            messages.error(request, 'Strike level and reason are required.')
            return redirect('disputes:admin_detail', dispute_id=dispute_id)

        with transaction.atomic():
            SellerStrike.objects.create(
                seller=dispute.seller,
                dispute=dispute,
                level=level,
                reason=reason,
                issued_by=request.user,
                action_taken=action_taken,
            )

            # Update seller strike count
            dispute.seller.strike_count += 1
            dispute.seller.save(update_fields=['strike_count'])

            # Apply consequences based on strike level
            if level == SellerStrike.StrikeLevel.SUSPENDED:
                dispute.seller.status = SellerProfile.StoreStatus.SUSPENDED
                dispute.seller.save(update_fields=['status'])
                # Hide all products
                dispute.seller.products.update(is_active=False)

            elif level == SellerStrike.StrikeLevel.BANNED:
                dispute.seller.status = SellerProfile.StoreStatus.BANNED
                dispute.seller.save(update_fields=['status'])
                # Ban user account
                dispute.seller.user.ban_status = 'permanent'
                dispute.seller.user.ban_reason = f'Dispute strike 4 — {reason}'
                dispute.seller.user.banned_at = timezone.now()
                dispute.seller.user.save(update_fields=[
                    'ban_status', 'ban_reason', 'banned_at'
                ])
                # Hide all products
                dispute.seller.products.update(is_active=False)

            # Notify seller
            Notification.objects.create(
                recipient=dispute.seller.user,
                notification_type='strike_issued',
                title=f'Strike Issued — {level.title()}',
                message=f'A strike has been issued against your store: {reason}',
                link=f'/dashboard/seller/disputes/{dispute.pk}/',
                related_object_id=dispute.pk,
                related_object_type='dispute',
            )

        messages.success(
            request,
            f'Strike issued to {dispute.seller.store_name}.'
        )

    return redirect('disputes:admin_detail', dispute_id=dispute_id)


# ─────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────

def _process_flutterwave_refund(fw_transaction_ref, amount):
    """
    Initiates refund via Flutterwave API.
    Returns refund reference if successful, None if failed.
    """
    if not fw_transaction_ref:
        return None

    try:
        # First get transaction ID from reference
        search_response = requests.get(
            f'https://api.flutterwave.com/v3/transactions?tx_ref={fw_transaction_ref}',
            headers={
                'Authorization': f'Bearer {settings.FLUTTERWAVE_SECRET_KEY}',
            },
            timeout=30,
        )
        search_data = search_response.json()
        transactions = search_data.get('data', [])

        if not transactions:
            return None

        transaction_id = transactions[0].get('id')

        # Initiate refund
        refund_response = requests.post(
            f'https://api.flutterwave.com/v3/transactions/{transaction_id}/refund',
            headers={
                'Authorization': f'Bearer {settings.FLUTTERWAVE_SECRET_KEY}',
                'Content-Type': 'application/json',
            },
            json={'amount': amount},
            timeout=30,
        )
        refund_data = refund_response.json()

        if refund_data.get('status') == 'success':
            return refund_data.get('data', {}).get('id', '')

    except Exception as e:
        print(f'FW REFUND ERROR: {e}')

    return None