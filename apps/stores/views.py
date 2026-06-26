# apps/stores/views.py
# ─────────────────────────────────────────────────────────────
# STORES VIEWS
# seller_register_step1  — personal account details
# seller_register_step2  — store details
# seller_register_step3  — bank details
# seller_register_step4  — subscription plan + payment
# seller_onboarding_complete — after payment confirmed
# ─────────────────────────────────────────────────────────────

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.conf import settings
from django.utils import timezone
import requests
import json
from django.contrib.auth.decorators import login_required

from .forms import (
    SellerStep1Form,
    SellerStep2Form,
    SellerStep3Form,
    SellerSubscriptionForm,
)
from .models import SellerProfile, Subscription
from apps.accounts.tokens import email_verification_token
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()

# Subscription plan prices in NGN
def _get_plan_prices():
    """
    Gets subscription prices from SiteSettings.
    Admin can change prices anytime from Django admin.
    No code change needed.
    """
    from apps.core.models import SiteSettings
    s = SiteSettings.get_settings()
    return {
        '1m':  int(s.sub_price_1m),
        '6m':  int(s.sub_price_6m),
        '12m': int(s.sub_price_12m),
        '24m': int(s.sub_price_24m),
    }

# Subscription plan durations in days
PLAN_DAYS = {
    '1m':  30,
    '6m':  180,
    '12m': 365,
    '24m': 730,
}




@login_required
def seller_register_start(request):
    """
    Entry point for seller registration.
    Must be logged in as buyer first.
    Accessed from user settings — not from login/register pages.
    """
    # Already a seller?
    if hasattr(request.user, 'seller_profile'):
        messages.info(request, 'You already have a seller account.')
        return redirect('/')

    # Email not verified?
    if not request.user.is_email_verified:
        messages.warning(
            request,
            'Please verify your email before becoming a seller.'
        )
        return redirect('accounts:resend_verification')

    # Store user in session and proceed to store details
    request.session['seller_registration_user_id'] = request.user.pk
    request.session['seller_registration_step'] = 2
    return redirect('stores:seller_register_step2')


def seller_register_step1(request):
    """
    Step 1 — Personal account details.
    Creates user with seller role.
    Sends verification email.
    Stores user ID in session for next steps.
    """
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        form = SellerStep1Form(request.POST)
        if form.is_valid():
            user = form.save()
            # Send verification email
            _send_seller_verification_email(request, user)
            # Store in session for next steps
            request.session['seller_registration_user_id'] = user.pk
            request.session['seller_registration_step'] = 2
            messages.success(
                request,
                'Account created! Please verify your email, '
                'then continue setting up your store.'
            )
            return redirect('stores:seller_register_step2')
    else:
        form = SellerStep1Form()

    return render(request, 'stores/register/step1.html', {
        'form': form,
        'step': 1,
        'total_steps': 4,
    })


def seller_register_step2(request):
    """
    Step 2 — Store identity and branding.
    User must exist in session from step 1.
    """
    user_id = request.session.get('seller_registration_user_id')
    if not user_id:
        messages.error(request, 'Please start from the beginning.')
        return redirect('stores:seller_register_step1')

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return redirect('stores:seller_register_step1')

    if request.method == 'POST':
        form = SellerStep2Form(request.POST, request.FILES)
        if form.is_valid():
            # Save store profile but don't commit yet
            profile = form.save(commit=False)
            profile.user = user
            profile.status = SellerProfile.StoreStatus.PENDING
            profile.save()
            # Ensure a role is upgraded to seller — covers both the
            # brand-new-signup path (step1) and the existing-buyer
            # upgrade path (seller_register_start), which never
            # touched a role before this point.
            if user.role != User.Role.SELLER:
                user.role = User.Role.SELLER
                user.save(update_fields=['role'])
            # Store profile ID in session
            request.session['seller_registration_profile_id'] = profile.pk
            request.session['seller_registration_step'] = 3
            return redirect('stores:seller_register_step3')
    else:
        form = SellerStep2Form()

    return render(request, 'stores/register/step2.html', {
        'form': form,
        'step': 2,
        'total_steps': 4,
    })


def seller_register_step3(request):
    """
    Step 3 — Bank account details.
    Updates the SellerProfile with bank info.
    """
    profile_id = request.session.get('seller_registration_profile_id')
    if not profile_id:
        return redirect('stores:seller_register_step1')

    try:
        profile = SellerProfile.objects.get(pk=profile_id)
    except SellerProfile.DoesNotExist:
        return redirect('stores:seller_register_step1')

    if request.method == 'POST':
        form = SellerStep3Form(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            request.session['seller_registration_step'] = 4
            return redirect('stores:seller_register_step4')
    else:
        form = SellerStep3Form(instance=profile)

    return render(request, 'stores/register/step3.html', {
        'form': form,
        'step': 3,
        'total_steps': 4,
        'account_type': profile.account_type,
    })


def seller_register_step4(request):
    """
    Step 4 — Subscription plan + commission policy acceptance + payment.
    """
    profile_id = request.session.get('seller_registration_profile_id')
    user_id = request.session.get('seller_registration_user_id')

    if not profile_id or not user_id:
        return redirect('stores:seller_register_step1')

    try:
        profile = SellerProfile.objects.get(pk=profile_id)
        user = User.objects.get(pk=user_id)
    except (SellerProfile.DoesNotExist, User.DoesNotExist):
        return redirect('stores:seller_register_step1')

    plan_prices = _get_plan_prices()

    if request.method == 'POST':
        form = SellerSubscriptionForm(request.POST)

        # Check policy accepted
        policy_accepted = request.POST.get('policy_accepted')
        if not policy_accepted:
            messages.error(
                request,
                'You must read and accept the Nexo Seller Policy '
                'before proceeding.'
            )
            return render(request, 'stores/register/step4.html', {
                'form': form,
                'step': 4,
                'total_steps': 4,
                'flutterwave_public_key': settings.FLUTTERWAVE_PUBLIC_KEY,
                'plan_prices': plan_prices,
            })

        if form.is_valid():
            plan = form.cleaned_data['plan']
            amount = plan_prices[plan]

            tx_ref = f'SUB-{profile.pk}-{plan}-{int(timezone.now().timestamp())}'

            # Store in session
            request.session['seller_subscription_plan'] = plan
            request.session['seller_subscription_amount'] = amount
            request.session['seller_subscription_tx_ref'] = tx_ref

            payment_data = {
                'tx_ref': tx_ref,
                'amount': amount,
                'currency': 'NGN',
                'redirect_url': request.build_absolute_uri(
                    '/store/register/payment-callback/'
                ),
                'customer': {
                    'email': user.email,
                    'name': user.full_name,
                    'phonenumber': user.phone,
                },
                'customizations': {
                    'title': 'Nexo Seller Subscription',
                    'description': f'Seller subscription — {plan} plan',
                },
                'meta': {
                    'profile_id': profile.pk,
                    'user_id': user.pk,
                    'plan': plan,
                    'type': 'seller_subscription',
                }
            }

            return render(request, 'stores/register/step4_payment.html', {
                'payment_data': json.dumps(payment_data),
                'flutterwave_public_key': settings.FLUTTERWAVE_PUBLIC_KEY,
                'amount': amount,
                'plan': plan,
            })
    else:
        form = SellerSubscriptionForm()

    return render(request, 'stores/register/step4.html', {
        'form': form,
        'step': 4,
        'total_steps': 4,
        'flutterwave_public_key': settings.FLUTTERWAVE_PUBLIC_KEY,
        'plan_prices': plan_prices,
    })


def seller_payment_callback(request):
    import urllib.parse

    # Flutterwave sends data as encoded JSON in 'response' parameter
    response_data = request.GET.get('response')

    if response_data:
        try:
            import json
            decoded = urllib.parse.unquote(response_data)
            data = json.loads(decoded)
            status = data.get('status')
            tx_ref = data.get('txRef') or data.get('tx_ref')
            transaction_id = data.get('id') or data.get('transaction_id')
        except Exception as e:
            print(f'Parse error: {e}')
            status = None
            tx_ref = None
            transaction_id = None
    else:
        status = request.GET.get('status')
        tx_ref = request.GET.get('tx_ref')
        transaction_id = request.GET.get('transaction_id')

    print(f'=== PAYMENT CALLBACK ===')
    print(f'status: {status}')
    print(f'tx_ref: {tx_ref}')
    print(f'transaction_id: {transaction_id}')
    print(f'session profile_id: {request.session.get("seller_registration_profile_id")}')
    print(f'========================')

    if status != 'successful':
        messages.error(request, f'Payment not successful: {status}')
        return redirect('stores:seller_register_step4')

    verified = _verify_flutterwave_payment(transaction_id)
    print(f'VERIFIED: {verified}')

    if not verified:
        messages.error(request, 'Payment verification failed.')
        return redirect('stores:seller_register_step4')

    profile_id = request.session.get('seller_registration_profile_id')
    plan = request.session.get('seller_subscription_plan')
    amount = request.session.get('seller_subscription_amount')

    if not profile_id or not plan:
        messages.error(request, f'Session expired. Your tx_ref: {tx_ref}')
        return redirect('stores:seller_register_step1')

    try:
        profile = SellerProfile.objects.get(pk=profile_id)
    except SellerProfile.DoesNotExist:
        return redirect('stores:seller_register_step1')

    if Subscription.objects.filter(fw_transaction_ref=tx_ref).exists():
        messages.info(request, 'Payment already processed.')
        return redirect('stores:onboarding_complete')

    from datetime import date, timedelta
    start_date = date.today()
    end_date = start_date + timedelta(days=PLAN_DAYS[plan])

    Subscription.objects.create(
        seller=profile,
        plan=plan,
        amount_paid=amount,
        status=Subscription.Status.ACTIVE,
        start_date=start_date,
        end_date=end_date,
        fw_transaction_ref=tx_ref,
    )

    profile.status = SellerProfile.StoreStatus.PENDING
    profile.save(update_fields=['status'])

    for key in [
        'seller_registration_user_id',
        'seller_registration_profile_id',
        'seller_registration_step',
        'seller_subscription_plan',
        'seller_subscription_amount',
        'seller_subscription_tx_ref',
    ]:
        request.session.pop(key, None)

    messages.success(request, 'Payment successful! Store pending approval.')
    return redirect('stores:onboarding_complete')



def onboarding_complete(request):
    """Final page after successful seller registration + payment"""
    return render(request, 'stores/register/complete.html')


def _verify_flutterwave_payment(transaction_id):
    """
    Verifies payment with Flutterwave API.
    Returns True if payment is confirmed successful.
    """
    if not transaction_id:
        return False

    try:
        response = requests.get(
            f'https://api.flutterwave.com/v3/transactions/{transaction_id}/verify',
            headers={
                'Authorization': f'Bearer {settings.FLUTTERWAVE_SECRET_KEY}',
                'Content-Type': 'application/json',
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


def _send_seller_verification_email(request, user):
    """Sends verification email to new seller"""
    from django.core.mail import send_mail
    token = email_verification_token.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    verify_url = request.build_absolute_uri(
        f'/auth/verify-email/{uid}/{token}/'
    )
    subject = 'Verify your Nexo seller account'
    message = (
        f'Hi {user.get_short_name()},\n\n'
        f'Welcome to Nexo! Please verify your email to continue '
        f'setting up your store.\n\n'
        f'Click this link to verify your email:\n'
        f'{verify_url}\n\n'
        f'This link expires in 15 minutes.\n\n'
        f'The Nexo Team'
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


def store_detail(request, store_slug):
    """Public seller storefront page"""
    from django.shortcuts import get_object_or_404
    from django.core.paginator import Paginator
    from apps.core.models import Coupon
    from django.utils import timezone as tz

    store = get_object_or_404(
        SellerProfile,
        store_slug=store_slug,
        is_approved=True,
        status='active'
    )

    products_qs = store.products.filter(
        is_active=True
    ).prefetch_related('images').order_by('-created_at')

    bestsellers = store.products.filter(
        is_active=True
    ).prefetch_related('images').order_by('-rating_avg', '-rating_count')[:8]

    new_arrivals = store.products.filter(
        is_active=True
    ).prefetch_related('images').order_by('-created_at')[:8]

    # Search within store
    q = request.GET.get('q', '').strip()
    if q:
        products_qs = products_qs.filter(name__icontains=q)

    paginator = Paginator(products_qs, 24)
    page = request.GET.get('page', 1)
    products = paginator.get_page(page)

    # Active coupon for this store
    now = tz.now()
    active_coupon = Coupon.objects.filter(
        seller=store,
        is_active=True,
        valid_from__lte=now,
        valid_until__gte=now,
    ).order_by('-discount_value').first()

    return render(request, 'stores/storefront.html', {
        'store': store,
        'products': products,
        'bestsellers': bestsellers,
        'active_coupon': active_coupon,
        'new_arrivals': new_arrivals,
    })

@login_required
def storefront_builder(request):
    """
    Seller storefront builder — Shopify-like editor.
    Handles all storefront customisation in one view.
    Two actions:
    - select_header: seller picks a header image from gallery
    - POST (main form): saves all other settings
    """
    from .models import StorefrontImage

    try:
        seller = request.user.seller_profile
    except SellerProfile.DoesNotExist:
        messages.error(request, 'You need a seller account.')
        return redirect('/')

    if not seller.is_approved:
        messages.error(request, 'Your store is pending approval.')
        return redirect('dashboard:seller')

    storefront_images = StorefrontImage.objects.filter(is_active=True)

    if request.method == 'POST':
        action = request.POST.get('action')

        # ── HEADER IMAGE — saved as part of main form ──
        image_id = request.POST.get('image_id')
        if image_id:
            try:
                img = StorefrontImage.objects.get(pk=image_id, is_active=True)
                seller.header_image = img
            except StorefrontImage.DoesNotExist:
                pass

        # ── MAIN SETTINGS SAVE ──
        # Store identity
        if can_change_name(seller):
            new_name = request.POST.get('store_name', '').strip()
            if new_name and new_name != seller.store_name:
                seller.store_name = new_name
                seller.store_name_last_changed = timezone.now()

        seller.store_description = request.POST.get('store_description', '').strip()
        seller.whatsapp_number = request.POST.get('whatsapp_number', '').strip()
        seller.store_tagline = request.POST.get('store_tagline', '').strip()

        # Logo upload
        if request.FILES.get('logo'):
            seller.logo = request.FILES['logo']

        # Hero section
        seller.hero_headline = request.POST.get('hero_headline', '').strip()
        seller.hero_subtext = request.POST.get('hero_subtext', '').strip()
        seller.hero_cta_text = request.POST.get('hero_cta_text', 'Shop Now').strip()
        seller.hero_layout_style = request.POST.get('hero_layout_style', 'split')
        seller.hero_text_align = request.POST.get('hero_text_align', 'left')
        seller.hero_text_color = request.POST.get('hero_text_color', '#FAF7F5')


        # Trust badges
        seller.trust_badge_style = request.POST.get('trust_badge_style', 'bar')

        # Sections
        seller.show_bestsellers = 'show_bestsellers' in request.POST
        seller.bestsellers_label = request.POST.get('bestsellers_label', 'Bestsellers').strip()

        seller.show_promo_banner = 'show_promo_banner' in request.POST
        seller.promo_banner_text = request.POST.get('promo_banner_text', '').strip()
        seller.promo_banner_bg = request.POST.get('promo_banner_bg', '#1C0F0A')

        seller.show_new_arrivals = 'show_new_arrivals' in request.POST
        seller.new_arrivals_label = request.POST.get('new_arrivals_label', 'New Arrivals').strip()

        seller.show_newsletter = 'show_newsletter' in request.POST
        seller.newsletter_headline = request.POST.get('newsletter_headline', 'Join our newsletter').strip()

        # Store options
        seller.allow_pod = 'allow_pod' in request.POST
        seller.is_on_vacation = 'is_on_vacation' in request.POST
        vacation_date = request.POST.get('vacation_return_date', '').strip()
        if vacation_date:
            from datetime import date
            try:
                from datetime import datetime
                seller.vacation_return_date = datetime.strptime(vacation_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            seller.vacation_return_date = None

        seller.save()
        messages.success(request, 'Store updated successfully.')
        return redirect('stores:storefront_builder')

    # Name change eligibility
    name_change_ok = can_change_name(seller)
    days_left = 0
    if not name_change_ok and seller.store_name_last_changed:
        from datetime import timedelta
        unlock_at = seller.store_name_last_changed + timedelta(days=90)
        days_left = (unlock_at - timezone.now()).days

    return render(request, 'stores/storefront_builder.html', {
        'seller': seller,
        'storefront_images': storefront_images,
        'can_change_name': name_change_ok,
        'name_change_days_left': days_left,
    })


def can_change_name(seller):
    """Returns True if seller is allowed to change store name"""
    if not seller.store_name_last_changed:
        return True
    from datetime import timedelta
    return timezone.now() - seller.store_name_last_changed > timedelta(days=90)