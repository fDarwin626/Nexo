
# apps/products/admin.py
from django.contrib import admin
from .models import (
    Category, VariantType, VariantOption,
    Product, ProductSKU, ProductImage,
    Wishlist, Review
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'is_active', 'order']
    list_filter = ['is_active', 'parent']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['required_variants']


@admin.register(VariantType)
class VariantTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(VariantOption)
class VariantOptionAdmin(admin.ModelAdmin):
    list_display = ['variant_type', 'value', 'created_by_seller', 'is_active']
    list_filter = ['variant_type', 'is_active']
    search_fields = ['value']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'seller', 'category', 'base_price',
        'condition', 'is_active', 'rating_avg', 'created_at'
    ]
    list_filter = ['condition', 'is_active', 'is_featured', 'category']
    search_fields = ['name', 'seller__store_name']
    readonly_fields = [
        'slug', 'rating_avg', 'rating_count',
        'search_vector', 'created_at', 'updated_at'
    ]

    def save_model(self, request, obj, form, change):
        # 🏪 Auto-assign Nexo Official store if no seller selected
        # Admin never needs to manually pick a seller — they ARE the store
        if not obj.seller_id:
            from apps.stores.models import SellerProfile
            nexo_store, created = SellerProfile.objects.get_or_create(
                user=request.user,
                defaults={
                    'store_name': 'Nexo Official',
                    'store_slug': 'nexo-official',
                    'status': 'active',
                    'is_approved': True,
                }
            )
            obj.seller = nexo_store
        super().save_model(request, obj, form, change)

    def get_fields(self, request, obj=None):
        # 🙈 Hide seller field from admin — auto-assigned on save
        fields = super().get_fields(request, obj)
        if request.user.is_superuser:
            return [f for f in fields if f != 'seller']
        return fields


@admin.register(ProductSKU)
class ProductSKUAdmin(admin.ModelAdmin):
    list_display = ['product', 'sku_code', 'stock', 'price_override', 'is_active']
    list_filter = ['is_active']
    search_fields = ['sku_code', 'product__name']
    readonly_fields = ['sku_code', 'created_at', 'updated_at']
    filter_horizontal = ['variant_options']


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'order', 'is_primary', 'created_at']
    list_filter = ['is_primary']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'price_at_save', 'created_at']
    search_fields = ['user__email', 'product__name']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'buyer', 'rating', 'created_at']
    list_filter = ['rating']
    search_fields = ['product__name', 'buyer__email']
    readonly_fields = ['created_at']