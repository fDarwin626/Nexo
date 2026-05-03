# apps/accounts/views.py
# ─────────────────────────────────────────────────────────────
# ACCOUNTS VIEWS
# register_buyer     — new buyer registration
# verify_email       — click link in email to verify
# resend_verification — resend verification email
# login_view         — email + password login
# logout_view        — logout
# forgot_password    — request password reset email
# reset_password     — set new password via token
# ─────────────────────────────────────────────────────────────
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.http import require_POST


from .forms import (
    BuyerRegistrationForm,
    LoginForm,
    ForgotPasswordForm,
    ResetPasswordForm,
)
from .tokens import email_verification_token, password_reset_token

User = get_user_model()


def register_buyer(request):
    """
    Buyer registration view.

    GET:  Show empty registration form
    POST: Validate form → create user → send verification email
          → redirect to "check your email" page
    """
    # If already logged in — redirect to homepage
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        form = BuyerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            try:
                _send_verification_email(request, user)
            except Exception as e:
                print(f'DEBUG ERROR: {e}')
            request.session['verification_email'] = user.email
            return redirect('accounts:verification_sent')

        else:
            messages.error(request, 'Please fix the errors below')
    else:
        form = BuyerRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def verification_sent(request):
    """
    Page shown after registration.
    Tells user to check their email.
    """
    email = request.session.get('verification_email', '')
    return render(request, 'accounts/verification_sent.html', {
        'email': email
    })


def verify_email(request, uidb64, token):
    # Fix quoted-printable encoding breaking token
    # Email clients sometimes wrap = signs
    token = token.replace('=', '')

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and email_verification_token.check_token(user, token):
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        messages.success(
            request,
            '✅ Email verified successfully! You can now log in.'
        )
        return redirect('accounts:login')
    else:
        messages.error(
            request,
            'Verification link is invalid or has expired. '
            'Request a new one below.'
        )
        return redirect('accounts:resend_verification')


def resend_verification(request):
    """
    Lets user request a new verification email
    if their link expired.
    """
    if request.method == 'POST':
        email = request.POST.get('email', '').lower()
        try:
            user = User.objects.get(email=email)
            if user.is_email_verified:
                messages.info(request, 'Your email is already verified.')
                return redirect('accounts:login')
            _send_verification_email(request, user)
            messages.success(
                request,
                'New verification email sent! Check your inbox.'
            )
        except User.DoesNotExist:
            # Always show success — prevents email enumeration
            messages.success(
                request,
                'If that email exists, a verification link has been sent.'
            )
    return render(request, 'accounts/resend_verification.html')


def login_view(request):
    """
    Login view — email + password.
    After login redirects based on role:
    - Admin   → /admin/
    - Seller  → /dashboard/seller/
    - Buyer   → / (homepage)

    Remember me: extends session to 30 days
    """
    if request.user.is_authenticated:
        return redirect(_get_redirect_url(request.user))

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data['remember_me']

            user = authenticate(request, username=email, password=password)

            if user is not None:
                # Check if banned
                if user.is_shadow_banned:
                    # Shadow ban — show fake success, do nothing
                    # User thinks they logged in but they didn't
                    messages.success(request, f'Welcome back, {user.get_short_name()}!')
                    return redirect('/')

                if user.ban_status in ['hard', 'permanent']:
                    messages.error(
                        request,
                        'Your account has been suspended. '
                        'Contact support to appeal.'
                    )
                    return redirect('accounts:login')

                # Check email verified
                if not user.is_email_verified:
                    messages.warning(
                        request,
                        'Please verify your email before logging in. '
                        'Check your inbox or request a new link.'
                    )
                    request.session['verification_email'] = user.email
                    return redirect('accounts:resend_verification')

                # All good — log them in
                login(request, user)

                # Remember me — 30 days session
                if remember_me:
                    request.session.set_expiry(30 * 24 * 60 * 60)
                else:
                    # Session expires when browser closes
                    request.session.set_expiry(0)

                messages.success(
                    request,
                    f'Welcome back, {user.get_short_name()}! 👋'
                )

                # Redirect based on role
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect(_get_redirect_url(user))

            else:
                messages.error(
                    request,
                    'Invalid email or password. Please try again.'
                )
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


@require_POST
def logout_view(request):
    """
    Logout — POST only for security.
    GET requests cannot log user out
    (prevents CSRF logout attacks via image tags etc)
    """
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


def forgot_password(request):
    """
    Step 1 — user enters email to receive reset link.
    Always shows success even if email not found
    (prevents email enumeration attacks)
    """
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                _send_password_reset_email(request, user)
            except User.DoesNotExist:
                pass  # Silent — prevents enumeration
            messages.success(
                request,
                'If that email is registered, you will receive '
                'a password reset link shortly.'
            )
            return redirect('accounts:forgot_password')
    else:
        form = ForgotPasswordForm()

    return render(request, 'accounts/forgot_password.html', {'form': form})


def reset_password(request, uidb64, token):
    """
    Step 2 — user clicks reset link and sets new password.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    # Validate token
    if not user or not password_reset_token.check_token(user, token):
        messages.error(
            request,
            'Password reset link is invalid or has expired. '
            'Please request a new one.'
        )
        return redirect('accounts:forgot_password')

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['password1'])
            user.save(update_fields=['password'])
            messages.success(
                request,
                '✅ Password reset successfully! You can now log in.'
            )
            return redirect('accounts:login')
    else:
        form = ResetPasswordForm()

    return render(request, 'accounts/reset_password.html', {
        'form': form,
        'uidb64': uidb64,
        'token': token,
    })


@login_required
def delete_account(request):
    """
    User deletes their own account.
    POST only — prevents accidental deletion.
    Soft approach — we ask for password confirmation first.
    """
    if request.method == 'POST':
        password = request.POST.get('password')
        user = request.user

        # Verify password before deletion
        if not user.check_password(password):
            messages.error(
                request,
                'Incorrect password. Account not deleted.'
            )
            return redirect('accounts:delete_account')

        # If seller — check no active orders
        if hasattr(user, 'seller_profile'):
            from apps.orders.models import SellerOrder
            active_orders = SellerOrder.objects.filter(
                seller=user.seller_profile,
                status__in=[
                    'pending', 'payment_confirmed',
                    'processing', 'shipped', 'out_for_delivery'
                ]
            ).exists()

            if active_orders:
                messages.error(
                    request,
                    'You have active orders. Please fulfill all orders '
                    'before deleting your account.'
                )
                return redirect('accounts:delete_account')

        # Log them out first
        logout(request)

        # Delete the account
        user.delete()

        messages.success(
            request,
            'Your account has been permanently deleted. '
            'We are sorry to see you go.'
        )
        return redirect('accounts:register')

    return render(request, 'accounts/delete_account.html')



# ── HELPER FUNCTIONS ─────────────────────────────────────────

def _get_redirect_url(user):
    """Returns correct URL after login based on user role"""
    if user.is_admin or user.is_staff:
        return '/admin/'
    elif user.is_seller:
        return '/dashboard/seller/'
    else:
        return '/'


def _send_verification_email(request, user):
    """
    Sends email verification link to new user.
    Link contains base64 encoded user ID + secure token.
    """
    token = email_verification_token.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    # Build full URL eg http://localhost:8000/auth/verify-email/abc123/xyz/
    domain = request.get_host()
    protocol = 'https' if request.is_secure() else 'http'
    verify_url = request.build_absolute_uri(
        f'/auth/verify-email/{uid}/{token}/'
    )
    subject = 'Verify your Nexo account'
    message = (
        f'Hi {user.get_short_name()},\n\n'
        f'Welcome to Nexo! Please verify your email address to get started.\n\n'
        f'Click this link to verify your email:\n'
        f'{verify_url}\n\n'
        f'This link expires in 15 minutes.\n\n'
        f'If you did not create a Nexo account, ignore this email.\n\n'
        f'The Nexo Team'
    )


    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def _send_password_reset_email(request, user):
    """Sends password reset link to user"""
    token = password_reset_token.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    domain = request.get_host()
    protocol = 'https' if request.is_secure() else 'http'
    reset_url = f'{protocol}://{domain}/auth/reset-password/{uid}/{token}/'

    subject = 'Reset your Nexo password'
    message = f'''
    Hi {user.get_short_name()},

    We received a request to reset your Nexo password.

    Click this link to set a new password:
    {reset_url}

    ⚠️ This link expires in 10 minutes.
    If you didn't request this, ignore this email — your password is unchanged.

    — The Nexo Team
    '''


    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )