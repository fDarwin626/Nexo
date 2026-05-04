# apps/products/tasks.py
# ─────────────────────────────────────────────────────────────
# PRODUCT CELERY TASKS
# check_restock_deadlines  — auto-delete products with no restock
# check_price_drops        — notify buyers of wishlist price drops
# update_product_visibility — hide/show based on stock
# ─────────────────────────────────────────────────────────────

from celery import shared_task
from django.utils import timezone
from django.db.models import Sum
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_restock_deadlines():
    """
    Runs daily at 1am.
    Checks all products with restock_deadline set.
    If deadline passed → auto-delete the product.
    Seller was already warned when stock hit 0.
    """
    from .models import Product

    now = timezone.now()

    # Find products past their restock deadline
    overdue_products = Product.objects.filter(
        restock_deadline__isnull=False,
        restock_deadline__lt=now,
        is_active=False,
    )

    deleted_count = 0
    for product in overdue_products:
        seller_email = product.seller.user.email
        product_name = product.name

        # Send notification to seller before deleting
        _notify_product_deleted(product)

        product.delete()
        deleted_count += 1
        logger.info(
            f'Auto-deleted product "{product_name}" '
            f'from seller {seller_email} — restock deadline passed'
        )

    logger.info(f'check_restock_deadlines: deleted {deleted_count} products')
    return f'Deleted {deleted_count} products'


@shared_task
def update_product_visibility(product_id):
    """
    Called when a SKU stock changes.
    If ALL SKUs hit 0 → product goes invisible + starts restock timer.
    If ANY SKU has stock → product stays visible.
    """
    from .models import Product
    from datetime import timedelta

    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        return

    total_stock = product.skus.aggregate(
        total=Sum('stock')
    )['total'] or 0

    if total_stock == 0 and product.is_active:
        # All stock gone — hide product + start restock timer
        product.is_active = False
        product.restock_deadline = (
            timezone.now() +
            timedelta(days=14)
        )
        product.save(update_fields=['is_active', 'restock_deadline'])

        # Notify seller
        _notify_low_stock(product, total_stock)

        logger.info(
            f'Product "{product.name}" hidden — '
            f'stock hit 0. Restock deadline: {product.restock_deadline}'
        )

    elif total_stock > 0 and not product.is_active:
        # Stock restored — make product visible again
        product.is_active = True
        product.restock_deadline = None
        product.save(update_fields=['is_active', 'restock_deadline'])

        logger.info(
            f'Product "{product.name}" restored — '
            f'stock replenished to {total_stock}'
        )


@shared_task
def check_price_drops():
    """
    Runs daily at 9am.
    Checks all wishlist items.
    If current price < price_at_save → notify buyer.
    """
    from apps.products.models import Wishlist

    notified_count = 0
    for wishlist_item in Wishlist.objects.select_related(
        'product', 'user'
    ).filter(product__is_active=True):

        current_price = wishlist_item.product.effective_price
        saved_price = wishlist_item.price_at_save

        if current_price < saved_price:
            _notify_price_drop(wishlist_item, current_price, saved_price)
            # Update saved price so we don't spam
            wishlist_item.price_at_save = current_price
            wishlist_item.save(update_fields=['price_at_save'])
            notified_count += 1

    logger.info(
        f'check_price_drops: notified {notified_count} buyers'
    )
    return f'Notified {notified_count} buyers of price drops'


# ── HELPER FUNCTIONS ─────────────────────────────────────────

def _notify_low_stock(product, stock):
    """Creates in-app notification for seller when stock hits 0"""
    from apps.notifications.models import Notification
    Notification.objects.create(
        recipient=product.seller.user,
        notification_type='low_stock',
        title=f'"{product.name}" is out of stock',
        message=(
            f'Your product "{product.name}" has run out of stock. '
            f'Restock within 14 days or it will be automatically removed. '
            f'Go to your dashboard to restock.'
        ),
        link=f'/dashboard/seller/products/{product.pk}/restock/',
        related_object_id=product.pk,
        related_object_type='product',
    )


def _notify_product_deleted(product):
    """Creates in-app notification when product auto-deleted"""
    from apps.notifications.models import Notification
    Notification.objects.create(
        recipient=product.seller.user,
        notification_type='product_deleted',
        title=f'"{product.name}" was automatically removed',
        message=(
            f'Your product "{product.name}" was removed because '
            f'it was out of stock for more than 14 days. '
            f'You can relist it anytime from your dashboard.'
        ),
        related_object_type='product',
    )


def _notify_price_drop(wishlist_item, current_price, saved_price):
    """Creates in-app notification for buyer when price drops"""
    from apps.notifications.models import Notification
    product = wishlist_item.product
    savings = saved_price - current_price
    Notification.objects.create(
        recipient=wishlist_item.user,
        notification_type='price_drop',
        title=f'Price drop on "{product.name}"!',
        message=(
            f'Good news! "{product.name}" dropped from '
            f'₦{saved_price:,.0f} to ₦{current_price:,.0f}. '
            f'You save ₦{savings:,.0f}!'
        ),
        link=f'/products/{product.slug}/',
        related_object_id=product.pk,
        related_object_type='product',
    )