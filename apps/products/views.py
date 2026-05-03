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
        form = ProductForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                # Save product
                product = form.save(commit=False)
                if seller:
                    product.seller = seller
                else:
                    # Admin posting — use admin's seller profile
                    # or create products under a special admin store
                    # For now redirect to Django admin for admin products
                    messages.info(
                        request,
                        'Admin products can be managed via Django admin.'
                    )
                    return redirect('/admin/products/product/add/')

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
        key = '-'.join(
            str(opt.pk)
            for opt in sku.variant_options.all().order_by('variant_type__pk')
        )
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

    return render(request, 'products/detail.html', {
        'product': product,
        'skus': skus,
        'sku_map': json.dumps(sku_map),
        'reviews': reviews,
        'in_wishlist': in_wishlist,
        'related_products': related_products,
        'seller': product.seller,
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