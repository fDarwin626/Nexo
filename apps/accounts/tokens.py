# apps/accounts/tokens.py
# ─────────────────────────────────────────────────────────────
# TOKEN GENERATORS
# EmailVerificationTokenGenerator — for email verification links
# PasswordResetTokenGenerator     — for password reset links
#
# Django's built-in token generator uses:
# - User's password hash (token invalid after password change)
# - User's last login time
# - Current timestamp
# This means tokens are single-use and time-limited — secure.
# ─────────────────────────────────────────────────────────────


# apps/accounts/tokens.py
from django.contrib.auth.tokens import PasswordResetTokenGenerator
import six


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Token for email verification — expires in 15 minutes"""

    def _make_hash_value(self, user, timestamp):
        return (
            six.text_type(user.pk) +
            six.text_type(timestamp) +
            six.text_type(user.is_email_verified)
        )


class CustomPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    """Token for password reset — expires in 10 minutes"""

    def _make_hash_value(self, user, timestamp):
        return (
            six.text_type(user.pk) +
            six.text_type(timestamp) +
            six.text_type(user.password)
        )


# Instances used in views
email_verification_token = EmailVerificationTokenGenerator()
password_reset_token = CustomPasswordResetTokenGenerator()