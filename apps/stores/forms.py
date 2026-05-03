# apps/stores/forms.py
# ─────────────────────────────────────────────────────────────
# STORES FORMS
# SellerRegistrationStep1Form — account details (name, email, password)
# SellerRegistrationStep2Form — store details (name, logo, category)
# SellerRegistrationStep3Form — bank details (bank, account number)
# ─────────────────────────────────────────────────────────────

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import SellerProfile, DeliveryZone
from apps.products.models import Category

User = get_user_model()


class SellerStep1Form(forms.ModelForm):
    """
    Step 1 — Personal account details.
    Creates the User account with seller role.
    """

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Create a strong password',
            'class': 'form-input',
        })
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
                'placeholder': 'Your full legal name',
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
        email = self.cleaned_data.get('email', '').lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError(
                'An account with this email already exists.'
            )
        return email

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

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.role = User.Role.SELLER
        user.is_email_verified = False
        if commit:
            user.save()
        return user


class SellerStep2Form(forms.ModelForm):
    """
    Step 2 — Store identity and branding.
    Creates the SellerProfile linked to the user.
    """

    class Meta:
        model = SellerProfile
        fields = [
            'store_name',
            'store_description',
            'logo',
            'whatsapp_number',
            'account_type',
        ]
        widgets = {
            'store_name': forms.TextInput(attrs={
                'placeholder': 'eg Nike Store Lagos',
                'class': 'form-input',
            }),
            'store_description': forms.Textarea(attrs={
                'placeholder': 'Short description of your store...',
                'class': 'form-input',
                'rows': 3,
            }),
            'whatsapp_number': forms.TextInput(attrs={
                'placeholder': '2348012345678 (with country code)',
                'class': 'form-input',
            }),
            'account_type': forms.RadioSelect(),
        }

    def clean_store_name(self):
        name = self.cleaned_data.get('store_name', '').strip()
        if SellerProfile.objects.filter(store_name__iexact=name).exists():
            raise ValidationError(
                'A store with this name already exists. '
                'Please choose a different name.'
            )
        return name


class SellerStep3Form(forms.ModelForm):
    """
    Step 3 — Bank account details for Flutterwave subaccount.
    Individual sellers: BVN + bank account
    Business sellers: CAC number + business bank account
    """

    class Meta:
        model = SellerProfile
        fields = [
            'bank_name',
            'bank_account_number',
            'account_name',
            'cac_number',
        ]
        widgets = {
            'bank_name': forms.TextInput(attrs={
                'placeholder': 'eg Access Bank, GTBank, Zenith Bank',
                'class': 'form-input',
            }),
            'bank_account_number': forms.TextInput(attrs={
                'placeholder': '10-digit account number',
                'class': 'form-input',
                'maxlength': '10',
            }),
            'account_name': forms.TextInput(attrs={
                'placeholder': 'Name on the bank account',
                'class': 'form-input',
            }),
            'cac_number': forms.TextInput(attrs={
                'placeholder': 'CAC registration number (business only)',
                'class': 'form-input',
            }),
        }

    def clean_bank_account_number(self):
        number = self.cleaned_data.get('bank_account_number', '')
        if not number.isdigit():
            raise ValidationError('Account number must contain only digits')
        if len(number) != 10:
            raise ValidationError('Account number must be exactly 10 digits')
        return number


class SellerSubscriptionForm(forms.Form):
    """
    Step 4 — Subscription plan selection.
    Prices loaded from SiteSettings — admin controlled.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load prices dynamically from SiteSettings
        from apps.core.models import SiteSettings
        s = SiteSettings.get_settings()

        self.fields['plan'] = forms.ChoiceField(
            choices=[
                ('1m',  f'Starter — 1 Month (₦{s.sub_price_1m:,.0f})'),
                ('6m',  f'Standard — 6 Months (₦{s.sub_price_6m:,.0f})'),
                ('12m', f'Pro — 1 Year (₦{s.sub_price_12m:,.0f})'),
                ('24m', f'Elite — 2 Years (₦{s.sub_price_24m:,.0f})'),
            ],
            widget=forms.RadioSelect(attrs={'class': 'plan-radio'}),
            initial='12m',
        )


class StoreSettingsForm(forms.ModelForm):
    """
    Seller updates their store appearance from dashboard.
    Controls their 35% — banner, colors, WhatsApp etc.
    """

    class Meta:
        model = SellerProfile
        fields = [
            'store_name',
            'store_description',
            'logo',
            'banner_image',
            'banner_headline',
            'banner_subtext',
            'banner_bg_color',
            'banner_accent_color',
            'whatsapp_number',
            'allow_pod',
        ]
        widgets = {
            'store_name': forms.TextInput(attrs={'class': 'form-input'}),
            'store_description': forms.Textarea(attrs={
                'class': 'form-input', 'rows': 3
            }),
            'banner_headline': forms.TextInput(attrs={
                'class': 'form-input',
                'maxlength': '60',
                'placeholder': 'eg Premium Nike Footwear'
            }),
            'banner_subtext': forms.TextInput(attrs={
                'class': 'form-input',
                'maxlength': '120',
                'placeholder': 'eg Free delivery within Lagos'
            }),
            'banner_bg_color': forms.TextInput(attrs={
                'class': 'form-input color-picker',
                'type': 'color',
            }),
            'banner_accent_color': forms.TextInput(attrs={
                'class': 'form-input color-picker',
                'type': 'color',
            }),
            'whatsapp_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '2348012345678'
            }),
        }