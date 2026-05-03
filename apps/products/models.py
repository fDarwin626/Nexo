# apps/products/models.py
# ─────────────────────────────────────────────────────────────
# PRODUCTS MODELS
# Category        — hierarchical categories + subcategories
# VariantType     — global variant types (Size, Color, Storage)
# VariantOption   — global variant options (XL, Red, 128GB)
# Product         — the actual product listing
# ProductSKU      — each variant combination (Black+128GB = 1 SKU)
# ProductImage    — multiple images per product/variant
# Wishlist        — buyer saves products for later
# Review          — verified purchase reviews + ratings
# ─────────────────────────────────────────────────────────────

from django.db import models
from django.utils.text import slugify
from django.conf import settings
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex


class Category(models.Model):
    """
     Hierarchical category system.
    A category can have a parent — making it a subcategory.

    Example:
    Electronics (parent=None)
        └── Phones (parent=Electronics)
        └── Laptops (parent=Electronics)
    Fashion (parent=None)
        └── Men's Clothing (parent=Fashion)
        └── Women's Clothing (parent=Fashion)
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    icon = models.CharField(
        max_length=100,
        blank=True,
        default='mdi:tag',
        help_text='Iconify icon name eg: heroicons:shopping-bag or mdi:phone'
    )
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories',
        help_text='Leave empty for top-level categories'
    )
    # Which variant types are REQUIRED for products in this category
    # eg Clothing requires Size + Color
    # eg Electronics requires Storage + Color
    required_variants = models.ManyToManyField(
        'VariantType',
        blank=True,
        related_name='required_for_categories',
        help_text='Variant types sellers must fill when listing in this category'
    )

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(
        default=0,
        help_text='Display order on marketplace — lower number shows first'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} → {self.name}'
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def is_subcategory(self):
        return self.parent is not None

    @property
    def full_path(self):
        """Returns Electronics > Phones for breadcrumb display"""
        if self.parent:
            return f'{self.parent.name} > {self.name}'
        return self.name


class VariantType(models.Model):
    """
    Global variant types — managed by admin.
    These are the TYPES of variation a product can have.

    Examples: Size, Color, Storage, RAM, Material

    Sellers pick from these when creating products.
    They cannot create new VariantTypes — only admin can.
    But they CAN add new VariantOptions (values).
    """

    name = models.CharField(
        max_length=50,
        unique=True,
        help_text='eg Size, Color, Storage, RAM, Material'
    )
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Variant Type'
        verbose_name_plural = 'Variant Types'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class VariantOption(models.Model):
    """
    Global variant options — the actual values.
    Belongs to a VariantType.

    Examples:
    Size → [XS, S, M, L, XL, XXL]
    Color → [Red, Blue, Black, White]
    Storage → [64GB, 128GB, 256GB, 512GB]

    Admin pre-loads common ones.
    When a seller types a new value — it auto-saves here
    so future sellers see it as a premade option.
    """

    variant_type = models.ForeignKey(
        VariantType,
        on_delete=models.CASCADE,
        related_name='options'
    )
    value = models.CharField(
        max_length=50,
        help_text='eg XL, Red, 128GB, Cotton'
    )
    # Track who first added this option
    # null = pre-loaded by admin
    # set = seller typed it first and it was saved globally
    created_by_seller = models.ForeignKey(
        'stores.SellerProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_variant_options',
        help_text='Seller who first added this option — null if admin pre-loaded'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Variant Option'
        verbose_name_plural = 'Variant Options'
        # Prevent duplicate values within same variant type
        unique_together = ['variant_type', 'value']
        ordering = ['variant_type', 'value']

    def __str__(self):
        return f'{self.variant_type.name}: {self.value}'


class Product(models.Model):
    """
    The main product listing.
    Each product belongs to one seller and one category.
    Actual stock is tracked at ProductSKU level (per variant combination)
    not at this level.

    Product lifecycle:
    - All SKUs hit 0 stock → product auto-invisible
    - 2 week restock timer starts
    - Seller restocks → goes live again
    - 2 weeks no restock → product auto-deleted via Celery
    """

    class Condition(models.TextChoices):
        BRAND_NEW = 'brand_new', 'Brand New (Sealed)'
        NEW = 'new', 'New'
        NIGERIAN_USED = 'nigerian_used', 'Nigerian Used'
        REFURBISHED = 'refurbished', 'Refurbished'
        FOR_PARTS = 'for_parts', 'For Parts Only'

    # ── RELATIONSHIPS ────────────────────────────────────────
    seller = models.ForeignKey(
        'stores.SellerProfile',
        on_delete=models.CASCADE,
        related_name='products',
        help_text='The store this product belongs to'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        help_text='PROTECT means category cannot be deleted if products exist in it'
    )

    # ── PRODUCT IDENTITY ─────────────────────────────────────
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, blank=True)
    description = models.TextField()
    condition = models.CharField(
        max_length=15,
        choices=Condition.choices,
        default=Condition.NEW
    )

    # ── PRICING ──────────────────────────────────────────────
    # Base price in NGN — actual price per SKU can override this
    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Base price in NGN — individual SKUs can have different prices'
    )

    # ── DISCOUNTS ────────────────────────────────────────────
    discount_percent = models.PositiveIntegerField(
        default=0,
        help_text='Discount percentage 0-50. 0 means no discount'
    )
    discount_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Discount auto-expires at this datetime'
    )

    # ── FLASH SALE ───────────────────────────────────────────
    is_flash_sale = models.BooleanField(default=False)
    flash_sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Special flash sale price — overrides discount_percent'
    )
    flash_sale_start = models.DateTimeField(null=True, blank=True)
    flash_sale_end = models.DateTimeField(null=True, blank=True)
    flash_sale_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Limited quantity at flash sale price'
    )

    # ── VISIBILITY ───────────────────────────────────────────
    is_active = models.BooleanField(
        default=True,
        help_text='False = invisible to buyers. Auto-set False when all SKUs hit 0 stock'
    )
    is_featured = models.BooleanField(
        default=False,
        help_text='Featured products appear at top of category — paid promotion'
    )
    featured_until = models.DateTimeField(null=True, blank=True)

    # ── STOCK LIFECYCLE ──────────────────────────────────────
    # Set when all SKUs hit 0 stock
    # Celery checks daily — if 14 days passed → auto-delete
    restock_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Auto-delete deadline. Set when all SKUs hit 0. 14 days from then.'
    )

    # ── RATINGS ──────────────────────────────────────────────
    # Auto-calculated from all reviews — never set manually
    rating_avg = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00
    )
    rating_count = models.PositiveIntegerField(default=0)

    # ── SEARCH ───────────────────────────────────────────────
    # PostgreSQL Full Text Search vector
    # Auto-populated from name + description
    search_vector = SearchVectorField(null=True, blank=True)

    # ── TIMESTAMPS ───────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['seller']),
            models.Index(fields=['category']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_featured']),
            models.Index(fields=['condition']),
            # GIN index for full text search
            GinIndex(fields=['search_vector']),
        ]

    def __str__(self):
        return f'{self.name} — {self.seller.store_name}'

    def save(self, *args, **kwargs):
        # Auto-generate unique slug from product name + seller
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = f'{base_slug}-{self.seller.store_slug}'
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        """
        Returns the actual price buyer sees after discount.
        Flash sale price takes priority over regular discount.
        """
        from django.utils import timezone
        now = timezone.now()

        # Check flash sale first
        if (self.is_flash_sale and
                self.flash_sale_price and
                self.flash_sale_start <= now <= self.flash_sale_end):
            return self.flash_sale_price

        # Check regular discount
        if self.discount_percent > 0:
            if not self.discount_until or self.discount_until > now:
                discount = self.base_price * (self.discount_percent / 100)
                return self.base_price - discount

        return self.base_price

    @property
    def total_stock(self):
        """Sum of stock across all SKUs"""
        return self.skus.aggregate(
            total=models.Sum('stock')
        )['total'] or 0

    @property
    def is_in_stock(self):
        return self.total_stock > 0


class ProductSKU(models.Model):
    """
    Stock Keeping Unit — one row per variant combination.

    Example for iPhone 15 Pro:
    SKU 1: Black + 128GB → 10 in stock → ₦850,000
    SKU 2: Black + 256GB → 5 in stock  → ₦950,000
    SKU 3: White + 128GB → 8 in stock  → ₦850,000

    This is what actually gets added to cart and deducted on purchase.
    Price can be different per SKU via price_override.
    If price_override is null → use product.base_price
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='skus'
    )
    # The variant options that make up this SKU
    # eg [Black, 128GB] or [Red, XL]
    variant_options = models.ManyToManyField(
        VariantOption,
        related_name='skus',
        blank=True,
        help_text='The combination of variant options for this SKU'
    )
    # Optional price override — if null use product.base_price
    price_override = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Leave empty to use product base price'
    )
    stock = models.PositiveIntegerField(
        default=0,
        help_text='Units available for this variant combination'
    )
    # Auto-generated unique code for this SKU
    # Used in order tracking and inventory management
    sku_code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text='Auto-generated unique SKU code'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product SKU'
        verbose_name_plural = 'Product SKUs'
        indexes = [
            models.Index(fields=['sku_code']),
            models.Index(fields=['stock']),
        ]

    def __str__(self):
        options = ' + '.join([str(o) for o in self.variant_options.all()])
        return f'{self.product.name} — {options} ({self.stock} in stock)'

    def save(self, *args, **kwargs):
        # Auto-generate SKU code if not set
        if not self.sku_code:
            import uuid
            self.sku_code = f'NXO-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        """Returns price_override if set, else product base price"""
        return self.price_override if self.price_override else self.product.base_price

    @property
    def is_in_stock(self):
        return self.stock > 0


class ProductImage(models.Model):
    """
    Multiple images per product.
    Images can be linked to a specific SKU (variant-specific)
    eg Red shirt shows red image when Red variant selected.
    Or linked to the product generally (shows for all variants).
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='images'
    )
    # Optional — link image to specific SKU
    # eg when buyer selects Red variant → show red shirt image
    sku = models.ForeignKey(
        ProductSKU,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='images',
        help_text='Link to specific SKU for variant-specific images'
    )
    image = models.ImageField(
        upload_to='products/images/',
        help_text='Uploaded to Cloudinary in production'
    )
    alt_text = models.CharField(
        max_length=125,
        blank=True,
        help_text='Accessibility text for screen readers'
    )
    # Order controls gallery display sequence
    # Drag and drop in seller dashboard updates this
    order = models.PositiveIntegerField(
        default=0,
        help_text='Display order in gallery — 0 shows first'
    )
    is_primary = models.BooleanField(
        default=False,
        help_text='Primary image shown on product cards in marketplace'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'
        ordering = ['order']
        indexes = [
            models.Index(fields=['product', 'is_primary']),
        ]

    def __str__(self):
        return f'{self.product.name} — image {self.order}'


class Wishlist(models.Model):
    """
    Buyer saves products to wishlist.
    - Logged in buyers: saved to DB here
    - Guest buyers: saved to localStorage (merged on login)

    price_at_save enables price drop notifications:
    Celery checks daily — if current price < price_at_save
    → send email to buyer "Price dropped on your wishlist item!"
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlisted_by'
    )
    # Snapshot of price when saved — used for price drop detection
    price_at_save = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Price when added to wishlist — compared daily for price drop alerts'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'
        # User can only wishlist a product once
        unique_together = ['user', 'product']
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} → {self.product.name}'


class Review(models.Model):
    """
    Product reviews — verified purchase only.
    Buyer can only review after order is marked DELIVERED.
    Seller can reply once per review.
    Store rating is auto-calculated from all product reviews.
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    # Link to the specific order item — proves purchase
    # Cannot review without a delivered order item
    order_item = models.OneToOneField(
        'orders.OrderItem',
        on_delete=models.CASCADE,
        related_name='review',
        help_text='Verified purchase proof — one review per order item'
    )
    rating = models.PositiveIntegerField(
        help_text='Rating from 1 to 5'
    )
    comment = models.TextField()
    # Optional photo with review
    photo = models.ImageField(
        upload_to='reviews/photos/',
        null=True,
        blank=True,
        help_text='Optional photo uploaded to Cloudinary'
    )
    # Seller reply — one reply only, never editable
    seller_reply = models.TextField(
        blank=True,
        help_text='Seller can reply once — cannot edit after submitting'
    )
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'rating']),
            models.Index(fields=['buyer']),
        ]

    def __str__(self):
        return f'{self.buyer.email} → {self.product.name} ({self.rating}★)'

    def clean(self):
        from django.core.exceptions import ValidationError
        # Enforce rating between 1 and 5
        if not 1 <= self.rating <= 5:
            raise ValidationError('Rating must be between 1 and 5')




