"""
migrate_media_to_cloudinary.py
──────────────────────────────
Run this from your Nexo root folder (where manage.py is):
    python migrate_media_to_cloudinary.py

What it does:
1. Finds every local image in your media/ folder
2. Uploads it to Cloudinary
3. Updates the database record to point to the new Cloudinary URL
4. Reports what was done

After running successfully — you can delete your local media/ folder.
"""

import os
import sys
import django

# ── DJANGO SETUP ─────────────────────────────────────────────
# Must happen before any Django imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

# ── IMPORTS ──────────────────────────────────────────────────
import cloudinary
import cloudinary.uploader
from django.conf import settings
from pathlib import Path

# ── CLOUDINARY CONFIG ────────────────────────────────────────
cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET'],
)

# ── COUNTERS ─────────────────────────────────────────────────
uploaded = 0
skipped  = 0
failed   = 0
errors   = []

def upload_file(local_path, cloudinary_folder):
    """
    Uploads a single file to Cloudinary.
    Returns the Cloudinary public URL or None if failed.
    """
    try:
        result = cloudinary.uploader.upload(
            str(local_path),
            folder=cloudinary_folder,
            use_filename=True,
            unique_filename=False,
            overwrite=True,
            resource_type='image',
        )
        return result.get('secure_url')
    except Exception as e:
        return None, str(e)


def migrate_product_images():
    """Updates ProductImage records"""
    global uploaded, skipped, failed

    from apps.products.models import ProductImage

    print('\n── Product Images ──────────────────────────────────')
    records = ProductImage.objects.exclude(image='')

    for record in records:
        local_path = settings.MEDIA_ROOT / record.image.name

        # Skip if already a Cloudinary URL
        if str(record.image.name).startswith('http'):
            print(f'  SKIP (already Cloudinary): {record.image.name}')
            skipped += 1
            continue

        if not local_path.exists():
            print(f'  SKIP (file not found): {local_path}')
            skipped += 1
            continue

        print(f'  Uploading: {local_path}')
        result = upload_file(local_path, 'nexo/products/images')

        if isinstance(result, tuple):
            # Got an error tuple back
            print(f'  FAILED: {result[1]}')
            errors.append(f'ProductImage {record.id}: {result[1]}')
            failed += 1
        else:
            # Update DB record with Cloudinary URL
            record.image = result
            record.save(update_fields=['image'])
            print(f'  OK: {result}')
            uploaded += 1


def migrate_review_photos():
    """Updates Review photo records"""
    global uploaded, skipped, failed

    from apps.products.models import Review

    print('\n── Review Photos ───────────────────────────────────')
    records = Review.objects.exclude(photo='').exclude(photo=None)

    for record in records:
        local_path = settings.MEDIA_ROOT / record.photo.name

        if str(record.photo.name).startswith('http'):
            print(f'  SKIP (already Cloudinary): {record.photo.name}')
            skipped += 1
            continue

        if not local_path.exists():
            print(f'  SKIP (file not found): {local_path}')
            skipped += 1
            continue

        print(f'  Uploading: {local_path}')
        result = upload_file(local_path, 'nexo/reviews/photos')

        if isinstance(result, tuple):
            print(f'  FAILED: {result[1]}')
            errors.append(f'Review {record.id}: {result[1]}')
            failed += 1
        else:
            record.photo = result
            record.save(update_fields=['photo'])
            print(f'  OK: {result}')
            uploaded += 1


def migrate_store_logos():
    """Updates SellerProfile logo records"""
    global uploaded, skipped, failed

    from apps.stores.models import SellerProfile

    print('\n── Store Logos ─────────────────────────────────────')
    records = SellerProfile.objects.exclude(logo='').exclude(logo=None)

    for record in records:
        local_path = settings.MEDIA_ROOT / record.logo.name

        if str(record.logo.name).startswith('http'):
            print(f'  SKIP (already Cloudinary): {record.logo.name}')
            skipped += 1
            continue

        if not local_path.exists():
            print(f'  SKIP (file not found): {local_path}')
            skipped += 1
            continue

        print(f'  Uploading: {local_path}')
        result = upload_file(local_path, 'nexo/stores/logos')

        if isinstance(result, tuple):
            print(f'  FAILED: {result[1]}')
            errors.append(f'SellerProfile {record.id} logo: {result[1]}')
            failed += 1
        else:
            record.logo = result
            record.save(update_fields=['logo'])
            print(f'  OK: {result}')
            uploaded += 1


def migrate_store_banners():
    """Updates SellerProfile banner_image records"""
    global uploaded, skipped, failed

    from apps.stores.models import SellerProfile

    print('\n── Store Banners ───────────────────────────────────')
    records = SellerProfile.objects.exclude(banner_image='').exclude(banner_image=None)

    for record in records:
        local_path = settings.MEDIA_ROOT / record.banner_image.name

        if str(record.banner_image.name).startswith('http'):
            print(f'  SKIP (already Cloudinary): {record.banner_image.name}')
            skipped += 1
            continue

        if not local_path.exists():
            print(f'  SKIP (file not found): {local_path}')
            skipped += 1
            continue

        print(f'  Uploading: {local_path}')
        result = upload_file(local_path, 'nexo/stores/banners')

        if isinstance(result, tuple):
            print(f'  FAILED: {result[1]}')
            errors.append(f'SellerProfile {record.id} banner: {result[1]}')
            failed += 1
        else:
            record.banner_image = result
            record.save(update_fields=['banner_image'])
            print(f'  OK: {result}')
            uploaded += 1


def migrate_storefront_images():
    """Updates StorefrontImage records"""
    global uploaded, skipped, failed

    from apps.stores.models import StorefrontImage

    print('\n── Storefront Template Images ──────────────────────')
    records = StorefrontImage.objects.exclude(image='')

    for record in records:
        local_path = settings.MEDIA_ROOT / record.image.name

        if str(record.image.name).startswith('http'):
            print(f'  SKIP (already Cloudinary): {record.image.name}')
            skipped += 1
            continue

        if not local_path.exists():
            print(f'  SKIP (file not found): {local_path}')
            skipped += 1
            continue

        print(f'  Uploading: {local_path}')
        result = upload_file(local_path, 'nexo/storefront/templates')

        if isinstance(result, tuple):
            print(f'  FAILED: {result[1]}')
            errors.append(f'StorefrontImage {record.id}: {result[1]}')
            failed += 1
        else:
            record.image = result
            record.save(update_fields=['image'])
            print(f'  OK: {result}')
            uploaded += 1


# ── MAIN ─────────────────────────────────────────────────────
if __name__ == '__main__':
    print('═' * 55)
    print('  NEXO — Migrate Local Media to Cloudinary')
    print('═' * 55)

    migrate_product_images()
    migrate_review_photos()
    migrate_store_logos()
    migrate_store_banners()
    migrate_storefront_images()

    print('\n═' * 55)
    print(f'  DONE')
    print(f'  Uploaded : {uploaded}')
    print(f'  Skipped  : {skipped}')
    print(f'  Failed   : {failed}')

    if errors:
        print('\n  Errors:')
        for e in errors:
            print(f'  • {e}')

    if failed == 0:
        print('\n  ✓ All files migrated. Safe to delete your local media/ folder.')
    else:
        print('\n  ✗ Some files failed. Fix errors above before deleting local media/.')

    print('═' * 55)