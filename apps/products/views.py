# apps/products/views.py
# ─────────────────────────────────────────────────────────────
# PRODUCTS VIEWS
# product_create     — seller adds new product
# product_edit       — seller edits existing product
# product_delete     — seller deletes product
# product_detail     — public product detail page
# add_product_images — seller uploads product images
# get_category_variants — AJAX: returns required variants for category
# ─────────────────────────────────────────────────────────────

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
import json

from .models import (
    Product, ProductSKU, ProductImage,
    Category, VariantType, VariantOption
)
from .forms import ProductForm, ProductImageForm, FlashSaleForm
from apps.stores.models import SellerProfile


def _get_seller_profile(user):
    """
    Gets seller profile for logged in user.
    Returns None if user is not an approved seller.
    """
    try:
        profile = user.seller_profile
        if not profile.is_approved or profile.status != 'active':
            return None
        return profile
    except SellerProfile.DoesNotExist:
        return None


@login_required
def product_create(request):
    """
    Seller creates a new product.
    Handles:
    - Product details form
    - SKU builder (variant combinations)
    - Image uploads
    All in one page — saved together.
    """
    seller = _get_seller_profile(request.user)

    # Admin can also add products
    if not seller and not request.user.is_staff:
        messages.error(
            request,
            'You need an approved seller account to add products.'
        )
        return redirect('/')

    if request.method == 'POST':
        # Handle new subcategory creation before form validation
        new_subcategory_name = request.POST.get('new_subcategory', '').strip()
        parent_category_id = request.POST.get('parent_category_id', '').strip()

        if new_subcategory_name and parent_category_id:
            try:
                parent_cat = Category.objects.get(
                    pk=parent_category_id,
                    parent__isnull=True,
                    is_active=True,
                )
                sub, created = Category.objects.get_or_create(
                    name__iexact=new_subcategory_name,
                    parent=parent_cat,
                    defaults={
                        'name': new_subcategory_name,
                        'parent': parent_cat,
                        'is_active': True,
                        'icon': 'mdi:tag',
                    }
                )
                # Inject the new subcategory id into POST data
                post_data = request.POST.copy()
                post_data['category'] = sub.pk
                form = ProductForm(post_data)
            except Category.DoesNotExist:
                form = ProductForm(request.POST)
        else:
            form = ProductForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                product = form.save(commit=False)
                if seller:
                    product.seller = seller
                elif request.user.is_staff:
                    # Admin posting — get or create admin seller profile
                    admin_profile, created = SellerProfile.objects.get_or_create(
                        user=request.user,
                        defaults={
                            'store_name': 'Nexo Official',
                            'store_slug': 'nexo-official',
                            'status': 'active',
                            'is_approved': True,
                        }
                    )
                    product.seller = admin_profile
                else:
                    messages.error(
                        request,
                        'You need an approved seller account to add products.'
                    )
                    return redirect('/')

                product.save()

                # Process SKUs from POST data
                # SKUs are submitted as JSON in hidden field
                skus_data = request.POST.get('skus_data', '[]')
                try:
                    skus = json.loads(skus_data)
                except json.JSONDecodeError:
                    skus = []

                for sku_data in skus:
                    variant_option_ids = sku_data.get('variant_options', [])
                    stock = sku_data.get('stock', 0)
                    price_override = sku_data.get('price_override') or None

                    sku = ProductSKU.objects.create(
                        product=product,
                        stock=stock,
                        price_override=price_override,
                    )

                    # Add variant options to SKU
                    if variant_option_ids:
                        options = VariantOption.objects.filter(
                            id__in=variant_option_ids
                        )
                        sku.variant_options.set(options)

                messages.success(
                    request,
                    f'Product "{product.name}" created successfully! '
                    'Now add some images.'
                )
                return redirect(
                    'products:add_images',
                    product_id=product.pk
                )
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = ProductForm()

    # Get all categories with their required variants for Alpine.js
    categories_with_variants = {}
    for cat in Category.objects.filter(
        is_active=True
    ).prefetch_related('required_variants'):
        categories_with_variants[cat.pk] = {
            'name': cat.name,
            'required_variants': [
                {
                    'id': vt.pk,
                    'name': vt.name,
                    'options': list(
                        VariantOption.objects.filter(
                            variant_type=vt,
                            is_active=True
                        ).values('id', 'value')
                    )
                }
                for vt in cat.required_variants.filter(is_active=True)
            ]
        }

    return render(request, 'products/create.html', {
        'form': form,
        'categories_with_variants': json.dumps(categories_with_variants),
        'seller': seller,
    })


@login_required
def add_product_images(request, product_id):
    """
    Step 2 after product creation — upload images.
    Primary image must be PNG.
    Gallery images can be PNG or JPG.
    """
    product = get_object_or_404(Product, pk=product_id)

    # Verify ownership
    seller = _get_seller_profile(request.user)
    if seller and product.seller != seller:
        messages.error(request, 'You do not own this product.')
        return redirect('dashboard:seller')

    if request.method == 'POST':
        images = request.FILES.getlist('images')
        is_primary_set = False

        for i, image_file in enumerate(images):
            # First image is primary
            is_primary = (i == 0 and not is_primary_set)
            if is_primary:
                is_primary_set = True

            # Validate PNG for primary
            if is_primary and not image_file.name.lower().endswith('.png'):
                messages.error(
                    request,
                    f'Primary image must be PNG. '
                    f'"{image_file.name}" was skipped.'
                )
                continue

            ProductImage.objects.create(
                product=product,
                image=image_file,
                is_primary=is_primary,
                order=i,
                alt_text=f'{product.name} image {i + 1}'
            )

        messages.success(
            request,
            f'{len(images)} image(s) uploaded successfully!'
        )
        return redirect('dashboard:seller')

    existing_images = product.images.all().order_by('order')

    return render(request, 'products/add_images.html', {
        'product': product,
        'existing_images': existing_images,
    })


@login_required
def product_edit(request, product_id):
    """Seller edits an existing product"""
    product = get_object_or_404(Product, pk=product_id)
    seller = _get_seller_profile(request.user)

    # Verify ownership
    if seller and product.seller != seller:
        messages.error(request, 'You do not own this product.')
        return redirect('dashboard:seller')

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated successfully!')
            return redirect('dashboard:seller')
    else:
        form = ProductForm(instance=product)

    return render(request, 'products/edit.html', {
        'form': form,
        'product': product,
    })


@login_required
def product_delete(request, product_id):
    """
    Seller deletes a product.
    POST only — prevents accidental deletion.
    Cannot delete if product has active orders.
    """
    product = get_object_or_404(Product, pk=product_id)
    seller = _get_seller_profile(request.user)

    if seller and product.seller != seller:
        messages.error(request, 'You do not own this product.')
        return redirect('dashboard:seller')

    if request.method == 'POST':
        # Check for active orders
        from apps.orders.models import OrderItem, SellerOrder
        active_orders = OrderItem.objects.filter(
            sku__product=product,
            seller_order__status__in=[
                'pending', 'payment_confirmed',
                'processing', 'shipped', 'out_for_delivery'
            ]
        ).exists()

        if active_orders:
            messages.error(
                request,
                'Cannot delete product with active orders. '
                'Wait for all orders to complete first.'
            )
            return redirect('dashboard:seller')

        product_name = product.name
        product.delete()
        messages.success(
            request,
            f'"{product_name}" has been deleted.'
        )
        return redirect('dashboard:seller')

    return render(request, 'products/delete_confirm.html', {
        'product': product
    })


def product_detail(request, product_slug):
    """
    Public product detail page.
    Visible to everyone — no login required.
    Shows product info, variants, images, reviews.
    """
    product = get_object_or_404(
        Product,
        slug=product_slug,
        is_active=True,
        seller__status='active',
        seller__is_approved=True,
    )

    # Get all SKUs with their variant options
    skus = product.skus.filter(
        is_active=True
    ).prefetch_related('variant_options__variant_type')

    # Build SKU map for Alpine.js variant selector
    sku_map = {}

    for sku in skus:
        option_ids = sorted([opt.pk for opt in sku.variant_options.all()])
        key = '-'.join(str(i) for i in option_ids)
        sku_map[key] = {
            'id': sku.pk,
            'stock': sku.stock,
            'price': float(sku.effective_price),
            'sku_code': sku.sku_code,
        }

    # Get reviews
    reviews = product.reviews.all().select_related(
        'buyer'
    ).order_by('-created_at')[:10]

    # Check if in wishlist
    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = product.wishlisted_by.filter(
            user=request.user
        ).exists()

    # Related products (same category, same seller)
    related_products = Product.objects.filter(
        category=product.category,
        is_active=True,
        seller__is_approved=True,
    ).exclude(pk=product.pk)[:6]

    from collections import defaultdict
    variant_groups = defaultdict(list)
    seen = set()
    for sku in skus:
        for opt in sku.variant_options.all():
            key = (opt.variant_type.pk, opt.pk)
            if key not in seen:
                seen.add(key)
                variant_groups[opt.variant_type.name].append({
                    'type_id': opt.variant_type.pk,
                    'option_id': opt.pk,
                    'value': opt.value,
                })
    variant_groups = dict(variant_groups)

    return render(request, 'products/detail.html', {
        'product': product,
        'skus': skus,
        'sku_map': json.dumps(sku_map),
        'reviews': reviews,
        'in_wishlist': in_wishlist,
        'related_products': related_products,
        'seller': product.seller,
        'variant_groups': variant_groups,
        'variant_type_count': len(variant_groups),
    })


def get_category_variants(request, category_id):
    """
    AJAX endpoint — returns required variants for a category.
    Called by Alpine.js when seller selects a category.
    Returns JSON with variant types and their options.
    """
    try:
        category = Category.objects.get(pk=category_id, is_active=True)
    except Category.DoesNotExist:
        return JsonResponse({'variants': []})

    variants = []
    for vt in category.required_variants.filter(is_active=True):
        options = list(
            VariantOption.objects.filter(
                variant_type=vt,
                is_active=True
            ).values('id', 'value').order_by('value')
        )
        variants.append({
            'id': vt.pk,
            'name': vt.name,
            'slug': vt.slug,
            'options': options,
        })

    return JsonResponse({'variants': variants, 'category': category.name})


@login_required
def restock_product(request, product_id):
    """
    Seller restocks a product that hit 0 stock.
    Clears restock_deadline and makes product visible again.
    """
    product = get_object_or_404(Product, pk=product_id)
    seller = _get_seller_profile(request.user)

    if seller and product.seller != seller:
        messages.error(request, 'You do not own this product.')
        return redirect('dashboard:seller')

    if request.method == 'POST':
        sku_id = request.POST.get('sku_id')
        new_stock = request.POST.get('stock', 0)

        try:
            sku = ProductSKU.objects.get(
                pk=sku_id,
                product=product
            )
            sku.stock = int(new_stock)
            sku.save(update_fields=['stock'])

            # If product has stock again — make it active
            if product.total_stock > 0:
                product.is_active = True
                product.restock_deadline = None
                product.save(update_fields=['is_active', 'restock_deadline'])

            messages.success(
                request,
                f'Stock updated to {new_stock} units.'
            )
        except ProductSKU.DoesNotExist:
            messages.error(request, 'SKU not found.')

    return redirect('dashboard:seller')

# ─────────────────────────────────────────────────────────────
#                 REVIEWS
# ─────────────────────────────────────────────────────────────

@login_required
def create_review(request, order_item_id):
    """
    Buyer creates a review for a delivered order item.
    Gates:
    - Must be logged in
    - OrderItem must belong to this buyer
    - Order must be DELIVERED or COMPLETED
    - No review already exists for this order item
    """
    from apps.orders.models import OrderItem
    from .models import Review

    order_item = get_object_or_404(
        OrderItem,
        pk=order_item_id,
        seller_order__order__buyer=request.user,
    )

    # Gate 1 — order must be delivered
    deliverable_statuses = ['delivered', 'delivered_paid', 'completed']
    if order_item.seller_order.status not in deliverable_statuses:
        messages.error(
            request,
            'You can only review items from delivered orders.'
        )
        return redirect('orders:order_detail',
                        order_ref=order_item.seller_order.order.order_ref)

    # Gate 2 — no existing review
    if hasattr(order_item, 'review'):
        messages.info(request, 'You have already reviewed this item.')
        return redirect('products:detail',
                        product_slug=order_item.seller_order.order.order_ref)

    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()
        photo = request.FILES.get('photo')

        # Validate rating
        try:
            rating = int(rating)
            if not 1 <= rating <= 5:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, 'Rating must be between 1 and 5.')
            return redirect('products:create_review',
                            order_item_id=order_item_id)

        if not comment:
            messages.error(request, 'Please write a comment.')
            return redirect('products:create_review',
                            order_item_id=order_item_id)

        with transaction.atomic():
            product = _get_product_from_order_item(order_item)
            if not product:
                messages.error(
                    request,
                    'This product no longer exists and cannot be reviewed.'
                )
                return redirect('orders:order_list')

            review = Review.objects.create(
                product=product,
                buyer=request.user,
                order_item=order_item,
                rating=rating,
                comment=comment,
                photo=photo,
            )

            # Update product rating_avg and rating_count
            _update_product_rating(review.product)

            # Notify seller
            from apps.notifications.models import Notification
            Notification.objects.create(
                recipient=order_item.seller_order.seller.user,
                notification_type='new_review',
                title=f'New {rating}★ review on your product',
                message=(
                    f'{request.user.get_short_name()} left a {rating}-star '
                    f'review on "{review.product.name}".'
                ),
                link=f'/products/{review.product.slug}/',
                related_object_id=review.product.pk,
                related_object_type='product',
            )

        messages.success(request, 'Review submitted. Thank you!')
        return redirect('products:detail',
                        product_slug=review.product.slug)

    return render(request, 'products/create_review.html', {
        'order_item': order_item,
    })


@login_required
def seller_reply_review(request, review_id):
    """
    Seller replies to a review on their product.
    One reply only — cannot edit after submitting.
    """
    from .models import Review

    review = get_object_or_404(Review, pk=review_id)
    seller = _get_seller_profile(request.user)

    # Gate — must be the seller who owns the product
    if not seller or review.product.seller != seller:
        messages.error(request, 'You cannot reply to this review.')
        return redirect('products:detail',
                        product_slug=review.product.slug)

    # Gate — cannot reply twice
    if review.seller_reply:
        messages.info(request, 'You have already replied to this review.')
        return redirect('products:detail',
                        product_slug=review.product.slug)

    if request.method == 'POST':
        reply = request.POST.get('reply', '').strip()

        if not reply:
            messages.error(request, 'Reply cannot be empty.')
            return redirect('products:seller_reply_review',
                            review_id=review_id)

        review.seller_reply = reply
        review.replied_at = timezone.now()
        review.save(update_fields=['seller_reply', 'replied_at'])

        messages.success(request, 'Reply posted.')
        return redirect('products:detail',
                        product_slug=review.product.slug)

    return render(request, 'products/seller_reply_review.html', {
        'review': review,
    })


# ── REVIEW HELPERS ────────────────────────────────────────────

def _get_product_from_order_item(order_item):
    """Gets the Product from an OrderItem via its SKU"""
    try:
        return order_item.sku.product
    except Exception:
        return None


def _update_product_rating(product):
    """Recalculates and saves product rating_avg and rating_count"""
    from django.db.models import Avg, Count
    if not product:
        return
    result = product.reviews.aggregate(
        avg=Avg('rating'),
        count=Count('id')
    )
    product.rating_avg = result['avg'] or 0
    product.rating_count = result['count'] or 0
    product.save(update_fields=['rating_avg', 'rating_count'])