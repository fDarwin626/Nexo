# apps/orders/models.py
# ─────────────────────────────────────────────────────────────
# ORDERS MODELS
# Cart         — temporary basket before checkout
# CartItem     — one product SKU in the cart
# Order        — confirmed purchase (master record)
# SellerOrder  — per-seller split of a master order
# OrderItem    — one product SKU in a seller order
# ─────────────────────────────────────────────────────────────

from django.db import models
from django.conf import settings
import uuid


class Cart(models.Model):
    """
    Temporary basket before checkout.

    Two types:
    - Logged in buyer: linked to user account
    - Guest buyer: linked to session key only

    On login: guest cart merges into user cart automatically.
    On checkout: cart is cleared after order created.
    """

    # Logged in buyer — null for guests
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart'
    )
    # Guest session key — used to identify guest carts
    # Django generates this automatically per browser session
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        unique=True,
        help_text='Django session key for guest carts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'

    def __str__(self):
        if self.user:
            return f'Cart — {self.user.email}'
        return f'Guest Cart — {self.session_key}'

    @property
    def total_items(self):
        return self.items.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0

    @property
    def subtotal(self):
        """Total before delivery fees and discounts"""
        total = sum(
            item.sku.effective_price * item.quantity
            for item in self.items.select_related('sku__product').all()
        )
        return total

    def get_items_by_seller(self):
        """
        Groups cart items by seller.
        Used at checkout to split order per seller.

        Returns dict: {seller_profile: [cart_items]}
        """
        from collections import defaultdict
        grouped = defaultdict(list)
        for item in self.items.select_related(
            'sku__product__seller'
        ).all():
            seller = item.sku.product.seller
            grouped[seller].append(item)
        return dict(grouped)


class CartItem(models.Model):
    """
    One product SKU in the cart.
    Linked to a specific SKU (variant combination)
    so we track exact stock correctly.
    """

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    sku = models.ForeignKey(
        'products.ProductSKU',
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    # Snapshot price at time of adding to cart
    # Protects against price changes while item sits in cart
    price_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Price at time of adding to cart — locked until checkout'
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        # Prevent same SKU appearing twice in same cart
        unique_together = ['cart', 'sku']

    def __str__(self):
        return f'{self.sku.product.name} x{self.quantity}'

    @property
    def line_total(self):
        return self.price_snapshot * self.quantity


class Order(models.Model):
    """
    Master order record — created after payment confirmed.

    One Order contains items from potentially multiple sellers.
    It splits into SellerOrders — one per seller in the cart.

    Pay Now: created after Flutterwave webhook confirms payment
    POD: created immediately, payment_status stays PENDING_CASH
    """

    class PaymentMethod(models.TextChoices):
        PAY_NOW = 'pay_now', 'Pay Now (Online)'
        POD     = 'pod',     'Pay on Delivery'

    class PaymentStatus(models.TextChoices):
        PENDING       = 'pending',       'Payment Pending'
        CONFIRMED     = 'confirmed',     'Payment Confirmed'
        PENDING_CASH  = 'pending_cash',  'Pending Cash (POD)'
        FAILED        = 'failed',        'Payment Failed'
        REFUNDED      = 'refunded',      'Refunded'
        PARTIAL_REFUND = 'partial_refund', 'Partially Refunded'

    class DeliveryType(models.TextChoices):
        DOOR    = 'door',    'Door Delivery'
        PICKUP  = 'pickup',  'Pickup Station'

    # ── BUYER ────────────────────────────────────────────────
    # null for guest checkout
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )
    # Guest email — used for order confirmation if no account
    guest_email = models.EmailField(
        blank=True,
        help_text='Used for guest checkout order confirmation emails'
    )
    guest_name = models.CharField(max_length=255, blank=True)
    guest_phone = models.CharField(max_length=20, blank=True)

    # ── ORDER REFERENCE ──────────────────────────────────────
    # Unique human-readable order reference
    # Shown to buyer and seller eg NXO-2024-ABC123
    order_ref = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text='Auto-generated unique order reference'
    )

    # ── PAYMENT ──────────────────────────────────────────────
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.PAY_NOW
    )
    payment_status = models.CharField(
        max_length=15,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )
    # Flutterwave transaction reference
    # Used to verify payment and prevent duplicate orders
    fw_transaction_ref = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text='Flutterwave transaction reference for this order'
    )

    # ── DELIVERY ─────────────────────────────────────────────
    delivery_type = models.CharField(
        max_length=10,
        choices=DeliveryType.choices,
        default=DeliveryType.DOOR
    )
    delivery_address = models.TextField(
        blank=True,
        help_text='Full delivery address for door delivery'
    )
    delivery_state = models.CharField(
        max_length=50,
        help_text='Nigerian state for delivery zone validation'
    )
    delivery_city = models.CharField(max_length=100, blank=True)

    # ── AMOUNTS ──────────────────────────────────────────────
    # All amounts in NGN
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Products total before delivery and discount'
    )
    total_delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text='Sum of all seller delivery fees'
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text='Amount deducted by coupon'
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Final amount charged = subtotal + delivery - discount'
    )

    # ── COUPON ───────────────────────────────────────────────
    coupon = models.ForeignKey(
        'core.Coupon',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )

    # ── TIMESTAMPS ───────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_ref']),
            models.Index(fields=['buyer']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['fw_transaction_ref']),
        ]

    def __str__(self):
        return f'Order {self.order_ref} — {self.payment_status}'

    def save(self, *args, **kwargs):
        # Auto-generate order reference on first save
        if not self.order_ref:
            self.order_ref = self._generate_order_ref()
        super().save(*args, **kwargs)

    def _generate_order_ref(self):
        """Generates unique ref like NXO-2024-AB12CD"""
        from django.utils import timezone
        year = timezone.now().year
        unique = uuid.uuid4().hex[:6].upper()
        return f'NXO-{year}-{unique}'

    @property
    def buyer_name(self):
        if self.buyer:
            return self.buyer.full_name
        return self.guest_name

    @property
    def buyer_email(self):
        if self.buyer:
            return self.buyer.email
        return self.guest_email


class SellerOrder(models.Model):
    """
    Per-seller split of a master order.

    When a buyer orders from 3 sellers in one cart:
    - 1 master Order is created
    - 3 SellerOrders are created (one per seller)
    - Each seller only sees their SellerOrder
    - Each seller gets paid their portion via FW subaccount split

    Status tracked independently per seller:
    Emeka can mark his items shipped while Aisha is still processing.
    """

    class Status(models.TextChoices):
        PENDING           = 'pending',            'Pending'
        PAYMENT_CONFIRMED = 'payment_confirmed',  'Payment Confirmed'
        PROCESSING        = 'processing',          'Processing'
        SHIPPED           = 'shipped',             'Shipped'
        OUT_FOR_DELIVERY  = 'out_for_delivery',   'Out for Delivery'
        DELIVERED         = 'delivered',           'Delivered'
        DELIVERED_PAID    = 'delivered_paid',      'Delivered & Paid (POD)'
        COMPLETED         = 'completed',           'Completed'
        CANCELLED_BUYER   = 'cancelled_buyer',     'Cancelled by Buyer'
        CANCELLED_SELLER  = 'cancelled_seller',    'Cancelled by Seller'
        REFUND_INITIATED  = 'refund_initiated',    'Refund Initiated'
        REFUNDED          = 'refunded',            'Refunded'
        DISPUTED          = 'disputed',            'Under Dispute'

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='seller_orders'
    )
    seller = models.ForeignKey(
        'stores.SellerProfile',
        on_delete=models.CASCADE,
        related_name='seller_orders'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    # ── AMOUNTS ──────────────────────────────────────────────
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Total for this seller items only'
    )
    delivery_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        help_text='Delivery fee for this seller items'
    )
    commission_rate = models.PositiveIntegerField(
        default=0,
        help_text='Commission % taken at time of order based on threshold'
    )
    commission_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text='Actual NGN amount taken as commission'
    )
    seller_payout = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text='Amount seller actually receives after commission'
    )

    # ── SHIPPING ─────────────────────────────────────────────
    tracking_number = models.CharField(
        max_length=100,
        blank=True,
        help_text='Optional courier tracking number'
    )
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # ── DELIVERY INSPECTION ──────────────────────────────────
    # Checklist completed before buyer accepts delivery
    inspection_passed = models.BooleanField(
        null=True,
        blank=True,
        help_text='True=buyer accepted, False=buyer rejected at door'
    )
    inspection_notes = models.TextField(
        blank=True,
        help_text='Notes from delivery inspection'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Seller Order'
        verbose_name_plural = 'Seller Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        return f'{self.seller.store_name} — {self.order.order_ref} ({self.status})'


class OrderItem(models.Model):
    """
    One product SKU line in a SellerOrder.

    Stores price snapshot at time of purchase —
    so even if seller changes price later,
    the order history shows what buyer actually paid.

    Also stores product name snapshot —
    so if product is deleted, order history still shows
    what was purchased.
    """

    seller_order = models.ForeignKey(
        SellerOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    sku = models.ForeignKey(
        'products.ProductSKU',
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_items'
    )
    quantity = models.PositiveIntegerField()

    # ── PRICE SNAPSHOT ───────────────────────────────────────
    # Locked at purchase time — never changes
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Price per unit at time of purchase — never changes'
    )

    # ── PRODUCT SNAPSHOT ─────────────────────────────────────
    # In case product is deleted — order history stays intact
    product_name = models.CharField(
        max_length=255,
        help_text='Product name snapshot at purchase time'
    )
    product_sku_code = models.CharField(
        max_length=50,
        help_text='SKU code snapshot at purchase time'
    )
    variant_description = models.CharField(
        max_length=255,
        blank=True,
        help_text='eg Black + 128GB — snapshot at purchase time'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        return f'{self.product_name} x{self.quantity} — {self.seller_order.order.order_ref}'

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def can_review(self):
        """
        Buyer can only review if:
        1. SellerOrder is COMPLETED or DELIVERED
        2. No review exists yet for this order item
        """
        from django.utils import timezone
        delivered_statuses = [
            SellerOrder.Status.DELIVERED,
            SellerOrder.Status.DELIVERED_PAID,
            SellerOrder.Status.COMPLETED,
        ]
        is_delivered = self.seller_order.status in delivered_statuses
        has_review = hasattr(self, 'review')
        return is_delivered and not has_review