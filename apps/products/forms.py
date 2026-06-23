# apps/products/forms.py
# ─────────────────────────────────────────────────────────────
# PRODUCTS FORMS
# ProductForm        — seller creates/edits a product
# ProductSKUForm     — variant combination + stock + price
# ProductImageForm   — upload product images
# ─────────────────────────────────────────────────────────────

from django import forms
from django.core.exceptions import ValidationError
from unicodedata import category

from .models import Product, ProductSKU, ProductImage, Category, VariantOption


def validate_png_only(image):
    """
    Enforces PNG only for primary product images.
    PNG = transparent background = clean UI display.
    No white boxes behind product images.
    """
    if not image.name.lower().endswith('.png'):
        raise ValidationError(
            'Only PNG images are accepted for product images. '
            'PNG ensures transparent backgrounds for clean display on Nexo.'
        )


def validate_png_or_jpg(image):
    """
    Gallery images (non-primary) accept PNG or JPG.
    Only primary/hero images must be PNG.
    """
    allowed = ['.png', '.jpg', '.jpeg']
    ext = '.' + image.name.lower().split('.')[-1]
    if ext not in allowed:
        raise ValidationError(
            'Only PNG or JPG images are accepted for gallery photos.'
        )


class ProductForm(forms.ModelForm):
    """
    Seller creates or edits a product.
    Category selection triggers required variant display via Alpine.js.
    """

    class Meta:
        model = Product
        fields = [
            'name',
            'category',
            'description',
            'condition',
            'base_price',
            'discount_percent',
            'discount_until',
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'eg Nike Air Max 270',
                'class': 'form-input',
            }),
            'category': forms.Select(attrs={
                'class': 'form-input',
                'x-model': 'selectedCategory',
                '@change': 'loadRequiredVariants()',
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Describe your product in detail...',
                'class': 'form-input',
                'rows': 4,
            }),
            'condition': forms.Select(attrs={
                'class': 'form-input',
            }),
            'base_price': forms.NumberInput(attrs={
                'placeholder': '0.00',
                'class': 'form-input',
                'min': '0',
                'step': '0.01',
            }),
            'discount_percent': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '0',
                'max': '50',
                'value': '0',
            }),
            'discount_until': forms.DateTimeInput(attrs={
                'class': 'form-input',
                'type': 'datetime-local',
            }),
        }

    def __init__(self, *args, **kwargs):
        # Only show active categories
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(
            is_active=True,
            parent__isnull=False,
        ).order_by('parent__name', 'name')
        self.fields['discount_percent'].required = False
        self.fields['discount_until'].required = False

    def clean_base_price(self):
        price = self.cleaned_data.get('base_price')
        if price and price <= 0:
            raise ValidationError('Price must be greater than 0')
        return price

    def clean_discount_percent(self):
        discount = self.cleaned_data.get('discount_percent') or 0
        if discount < 0 or discount > 50:
            raise ValidationError('Discount must be between 0 and 50%')
        return discount

    def clean_category(self):
        category = self.cleaned_data.get('category')
        if category and category.parent is None:
            raise ValidationError(
                'Please select a subCategory, not a top level category'
            )
        return category


class ProductSKUForm(forms.Form):
    """
    Dynamic form for creating a single SKU
    (variant combination + stock + price).

    This form is rendered multiple times for each SKU.
    eg iPhone 15 Pro has 4 SKUs:
    - Black + 128GB → stock: 10, price: ₦850,000
    - Black + 256GB → stock: 5,  price: ₦950,000
    etc
    """

    stock = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input sku-stock',
            'placeholder': 'Stock quantity',
            'min': '0',
        })
    )
    price_override = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={
            'class': 'form-input sku-price',
            'placeholder': 'Leave empty to use base price',
            'step': '0.01',
        })
    )


class ProductImageForm(forms.ModelForm):
    """
    Upload images for a product.
    Primary image MUST be PNG (transparent background).
    Gallery images accept PNG or JPG.
    """

    class Meta:
        model = ProductImage
        fields = ['image', 'alt_text', 'is_primary', 'order']
        widgets = {
            'alt_text': forms.TextInput(attrs={
                'placeholder': 'Describe this image for accessibility',
                'class': 'form-input',
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-input',
                'min': '0',
            }),
        }

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            is_primary = self.data.get('is_primary')
            if is_primary:
                validate_png_only(image)
            else:
                validate_png_or_jpg(image)
        return image


class FlashSaleForm(forms.ModelForm):
    """
    Seller creates a flash sale for a product.
    Flash sale price overrides regular discount.
    """

    class Meta:
        model = Product
        fields = [
            'is_flash_sale',
            'flash_sale_price',
            'flash_sale_start',
            'flash_sale_end',
            'flash_sale_quantity',
        ]
        widgets = {
            'flash_sale_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Flash sale price in NGN',
                'step': '0.01',
            }),
            'flash_sale_start': forms.DateTimeInput(attrs={
                'class': 'form-input',
                'type': 'datetime-local',
            }),
            'flash_sale_end': forms.DateTimeInput(attrs={
                'class': 'form-input',
                'type': 'datetime-local',
            }),
            'flash_sale_quantity': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Limited quantity at this price',
                'min': '1',
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('flash_sale_start')
        end = cleaned_data.get('flash_sale_end')
        price = cleaned_data.get('flash_sale_price')

        if start and end and start >= end:
            raise ValidationError(
                'Flash sale end time must be after start time'
            )
        if cleaned_data.get('is_flash_sale') and not price:
            raise ValidationError(
                'Flash sale price is required when flash sale is active'
            )
        return cleaned_data