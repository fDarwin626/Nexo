"""
fix_cloudinary_urls.py
──────────────────────
Run this from your Nexo root folder (where manage.py is):
    python fix_cloudinary_urls.py

What it does:
Strips full Cloudinary URLs stored in DB down to just the public ID.

BEFORE: https://res.cloudinary.com/dsep6atoj/image/upload/v1782466031/nexo/products/images/necklace-on-male-neck.jpg
AFTER:  nexo/products/images/necklace-on-male-neck.jpg

This lets the Cloudinary storage backend generate correct URLs automatically.
"""

import os
import re
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

# ── COUNTER ──────────────────────────────────────────────────
fixed = 0
skipped = 0


def extract_public_id(url):
    """
    Extracts the public ID from a full Cloudinary URL.

    Input:  https://res.cloudinary.com/dsep6atoj/image/upload/v1782466031/nexo/products/images/necklace-on-male-neck.jpg
    Output: nexo/products/images/necklace-on-male-neck.jpg

    Strips everything up to and including /upload/vXXXXXXXXX/
    Keeps the folder path + filename including extension.
    """
    # Match everything after /upload/vNNNNNNNN/
    match = re.search(r'/upload/v\d+/(.+)$', url)
    if match:
        return match.group(1)
    # Fallback — match everything after /upload/
    match = re.search(r'/upload/(.+)$', url)
    if match:
        return match.group(1)
    return None


def fix_product_images():
    global fixed, skipped
    from apps.products.models import ProductImage

    print('\n── Product Images ──────────────────────────────────')
    for record in ProductImage.objects.exclude(image=''):
        name = record.image.name
        if not name.startswith('http'):
            print(f'  SKIP (already clean): {name}')
            skipped += 1
            continue

        public_id = extract_public_id(name)
        if not public_id:
            print(f'  SKIP (could not parse): {name}')
            skipped += 1
            continue

        record.image.name = public_id
        # Use update() to bypass storage backend and write directly to DB
        ProductImage.objects.filter(pk=record.pk).update(image=public_id)
        print(f'  FIXED: {public_id}')
        fixed += 1


def fix_review_photos():
    global fixed, skipped
    from apps.products.models import Review

    print('\n── Review Photos ───────────────────────────────────')
    for record in Review.objects.exclude(photo='').exclude(photo=None):
        name = record.photo.name
        if not name.startswith('http'):
            print(f'  SKIP (already clean): {name}')
            skipped += 1
            continue

        public_id = extract_public_id(name)
        if not public_id:
            print(f'  SKIP (could not parse): {name}')
            skipped += 1
            continue

        Review.objects.filter(pk=record.pk).update(photo=public_id)
        print(f'  FIXED: {public_id}')
        fixed += 1


def fix_store_logos():
    global fixed, skipped
    from apps.stores.models import SellerProfile

    print('\n── Store Logos ─────────────────────────────────────')
    for record in SellerProfile.objects.exclude(logo='').exclude(logo=None):
        name = record.logo.name
        if not name.startswith('http'):
            print(f'  SKIP (already clean): {name}')
            skipped += 1
            continue

        public_id = extract_public_id(name)
        if not public_id:
            print(f'  SKIP (could not parse): {name}')
            skipped += 1
            continue

        SellerProfile.objects.filter(pk=record.pk).update(logo=public_id)
        print(f'  FIXED: {public_id}')
        fixed += 1


def fix_store_banners():
    global fixed, skipped
    from apps.stores.models import SellerProfile

    print('\n── Store Banners ───────────────────────────────────')
    for record in SellerProfile.objects.exclude(banner_image='').exclude(banner_image=None):
        name = record.banner_image.name
        if not name.startswith('http'):
            print(f'  SKIP (already clean): {name}')
            skipped += 1
            continue

        public_id = extract_public_id(name)
        if not public_id:
            print(f'  SKIP (could not parse): {name}')
            skipped += 1
            continue

        SellerProfile.objects.filter(pk=record.pk).update(banner_image=public_id)
        print(f'  FIXED: {public_id}')
        fixed += 1


def fix_storefront_images():
    global fixed, skipped
    from apps.stores.models import StorefrontImage

    print('\n── Storefront Template Images ──────────────────────')
    for record in StorefrontImage.objects.exclude(image=''):
        name = record.image.name
        if not name.startswith('http'):
            print(f'  SKIP (already clean): {name}')
            skipped += 1
            continue

        public_id = extract_public_id(name)
        if not public_id:
            print(f'  SKIP (could not parse): {name}')
            skipped += 1
            continue

        StorefrontImage.objects.filter(pk=record.pk).update(image=public_id)
        print(f'  FIXED: {public_id}')
        fixed += 1


if __name__ == '__main__':
    print('═' * 55)
    print('  NEXO — Fix Cloudinary URLs in Database')
    print('═' * 55)

    fix_product_images()
    fix_review_photos()
    fix_store_logos()
    fix_store_banners()
    fix_storefront_images()

    print('\n' + '═' * 55)
    print(f'  DONE')
    print(f'  Fixed   : {fixed}')
    print(f'  Skipped : {skipped}')
    print('═' * 55)