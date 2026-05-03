# apps/accounts/signals.py
# ─────────────────────────────────────────────────────────────
# SIGNALS
# Fires automatically when certain events happen
# We use this to handle post-Google-login setup
# ─────────────────────────────────────────────────────────────

from django.dispatch import receiver
from allauth.socialaccount.signals import social_account_added
from allauth.account.signals import user_signed_up
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(user_signed_up)
def handle_user_sign_up(request, user, **kwargs):
    """
    Fires when any new user signs up email or social sets default
    role to buyer and make email verify if they sign up via Google.
    """
    #Set role to buyer if not already set
    if not user.role:
        user.role = User.Role.BUYER

    # If signed up via Google make email verified
    social_login = kwargs.get('sociallogin')
    if social_login:
        user.is_email_verified = True
    user.save(update_fields=['role', 'is_email_verified'])


@receiver(social_account_added)
def handle_social_account_added(request, sociallogin, **kwargs):
    """
        Fires when Google account is connected to existing account
        Ensures email is marked verified
    """
    user = sociallogin.user
    if not user.is_email_verified:
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
