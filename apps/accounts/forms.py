# apps/accounts/forms.py
# ─────────────────────────────────────────────────────────────
# ACCOUNTS FORMS
# BuyerRegistrationForm  — new buyer signs up
# SellerRegistrationForm — covered in Section 4
# LoginForm              — email + password login
# ─────────────────────────────────────────────────────────────

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class BuyerRegistrationForm(forms.ModelForm):
    """
    Registration form for buyers.
    Collects: full name, email, phone, password.
    Email must be unique.
    Password validated against Django's password validators.
    """

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Create a strong password',
            'class': 'form-input',
        }),
        help_text='Minimum 8 characters'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Repeat your password',
            'class': 'form-input',
        })
    )

    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'placeholder': 'Your full name',
                'class': 'form-input',
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'your@email.com',
                'class': 'form-input',
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '08012345678',
                'class': 'form-input',
            }),
        }

    def clean_email(self):
        """Check email is not already registered"""
        email = self.cleaned_data.get('email', '').lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError(
                'An account with this email already exists. '
                'Try logging in instead.'
            )
        return email

    def clean_password1(self):
        """Run Django password validators"""
        password = self.cleaned_data.get('password1')
        if password:
            validate_password(password)
        return password

    def clean(self):
        """Check both passwords match"""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError({'password2': 'Passwords do not match'})
        return cleaned_data

    def save(self, commit=True):
        """Save user with hashed password and buyer role"""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.role = User.Role.BUYER
        user.is_email_verified = False
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    """
    Login form — email + password.
    Works for buyers, sellers and admin.
    Role checked after login to redirect correctly.
    """

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'your@email.com',
            'class': 'form-input',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Your password',
            'class': 'form-input',
        })
    )
    # Remember me — extends session from browser close to 30 days
    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )

    def clean_email(self):
        return self.cleaned_data.get('email', '').lower()


class ForgotPasswordForm(forms.Form):
    """
    Step 1 of password reset — user enters their email.
    We send a reset link if account exists.
    We always show success message even if email not found
    (prevents email enumeration attacks)
    """

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'your@email.com',
            'class': 'form-input',
        })
    )

    def clean_email(self):
        return self.cleaned_data.get('email', '').lower()


class ResetPasswordForm(forms.Form):
    """
    Step 2 of password reset — user enters new password.
    Token validated in view before showing this form.
    """

    password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'New password',
            'class': 'form-input',
        })
    )
    password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Repeat new password',
            'class': 'form-input',
        })
    )

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if password:
            validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise ValidationError({'password2': 'Passwords do not match'})
        return cleaned_data