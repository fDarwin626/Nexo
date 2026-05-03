# apps/products/management/commands/seed_categories.py
# ─────────────────────────────────────────────────────────────
# SEED COMMAND
# Run once to populate:
# - Categories + subcategories
# - Variant types (Size, Color, Storage etc)
# - Variant options (XL, Red, 128GB etc)
# - Category → required variant mappings
#
# Run with: python manage.py seed_categories
# ─────────────────────────────────────────────────────────────

from django.core.management.base import BaseCommand
from apps.products.models import Category, VariantType, VariantOption


class Command(BaseCommand):
    help = 'Seeds categories, variant types and variant options'

    def handle(self, *args, **options):
        self.stdout.write('🌱 Seeding categories and variants...')

        # ── VARIANT TYPES ─────────────────────────────────────
        self.stdout.write('Creating variant types...')

        variant_types = {}
        variant_type_data = [
            ('Size', 'size'),
            ('Color', 'color'),
            ('Storage', 'storage'),
            ('RAM', 'ram'),
            ('Material', 'material'),
            ('Weight', 'weight'),
            ('Length', 'length'),
            ('Voltage', 'voltage'),
        ]

        for name, slug in variant_type_data:
            vt, created = VariantType.objects.get_or_create(
                slug=slug,
                defaults={'name': name}
            )
            variant_types[slug] = vt
            status = '✓ Created' if created else '→ Already exists'
            self.stdout.write(f'  {status}: {name}')

        # ── VARIANT OPTIONS ───────────────────────────────────
        self.stdout.write('Creating variant options...')

        options_data = {
            'size': [
                'XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL',
                '36', '37', '38', '39', '40', '41', '42',
                '43', '44', '45', '46',
            ],
            'color': [
                'Black', 'White', 'Red', 'Blue', 'Green',
                'Yellow', 'Orange', 'Purple', 'Pink', 'Brown',
                'Grey', 'Gold', 'Silver', 'Navy', 'Beige',
                'Maroon', 'Teal', 'Coral', 'Cream', 'Burgundy',
            ],
            'storage': [
                '16GB', '32GB', '64GB', '128GB', '256GB',
                '512GB', '1TB', '2TB',
            ],
            'ram': [
                '2GB', '3GB', '4GB', '6GB', '8GB',
                '12GB', '16GB', '32GB', '64GB',
            ],
            'material': [
                'Cotton', 'Polyester', 'Leather', 'Wool',
                'Denim', 'Silk', 'Linen', 'Nylon', 'Suede',
                'Canvas', 'Rubber', 'Plastic', 'Metal', 'Wood',
            ],
            'weight': [
                '250g', '500g', '1kg', '2kg', '5kg',
                '10kg', '20kg', '50kg',
            ],
            'length': [
                '30cm', '50cm', '1m', '1.5m', '2m',
                '3m', '5m', '10m',
            ],
            'voltage': [
                '110V', '220V', '240V', '12V', '24V',
            ],
        }

        for type_slug, values in options_data.items():
            vt = variant_types.get(type_slug)
            if not vt:
                continue
            for value in values:
                obj, created = VariantOption.objects.get_or_create(
                    variant_type=vt,
                    value=value,
                )
            self.stdout.write(
                f'  ✓ {vt.name}: {len(values)} options seeded'
            )

        # ── CATEGORIES ────────────────────────────────────────
        self.stdout.write('Creating categories...')

        categories_data = [
            # (name, icon, parent_slug, required_variant_slugs)
            # TOP LEVEL
            ('Fashion & Clothing', 'mdi:hanger', None, []),
            ('Electronics', 'heroicons:device-phone-mobile', None, []),
            ('Shoes & Footwear', 'mdi:shoe-heel', None, []),
            ('Home & Furniture', 'mdi:sofa', None, []),
            ('Beauty & Personal Care', 'mdi:lipstick', None, []),
            ('Sports & Fitness', 'mdi:basketball', None, []),
            ('Books & Education', 'mdi:book-open', None, []),
            ('Gaming', 'mdi:gamepad-variant', None, []),
            ('Automobiles & Vehicles', 'mdi:car', None, []),
            ('Food & Groceries', 'mdi:food', None, []),
            ('Baby & Kids', 'mdi:baby-carriage', None, []),
            ('Health & Wellness', 'mdi:heart-pulse', None, []),
            ('Office & Stationery', 'mdi:briefcase', None, []),
            ('Art & Collectibles', 'mdi:palette', None, []),
            ('Other', 'mdi:tag', None, []),

            # FASHION SUBCATEGORIES
            ('Men\'s Clothing', 'mdi:tshirt-crew', 'fashion-clothing', ['size', 'color']),
            ('Women\'s Clothing', 'mdi:hanger', 'fashion-clothing', ['size', 'color']),
            ('Kids Clothing', 'mdi:hanger', 'fashion-clothing', ['size', 'color']),
            ('Traditional Wear', 'mdi:hanger', 'fashion-clothing', ['size', 'color']),
            ('Bags & Accessories', 'mdi:bag-personal', 'fashion-clothing', ['color']),
            ('Watches', 'mdi:watch', 'fashion-clothing', ['color']),
            ('Jewellery', 'mdi:diamond-stone', 'fashion-clothing', ['color']),

            # ELECTRONICS SUBCATEGORIES
            ('Phones & Tablets', 'mdi:cellphone', 'electronics', ['storage', 'color']),
            ('Laptops & Computers', 'mdi:laptop', 'electronics', ['storage', 'ram', 'color']),
            ('TV & Audio', 'mdi:television', 'electronics', ['color']),
            ('Cameras & Photography', 'mdi:camera', 'electronics', ['color']),
            ('Smart Home', 'mdi:home-automation', 'electronics', ['color']),
            ('Gaming Consoles', 'mdi:gamepad', 'electronics', ['color']),
            ('Accessories & Cables', 'mdi:cable-data', 'electronics', ['color']),

            # SHOES SUBCATEGORIES
            ('Men\'s Shoes', 'mdi:shoe-formal', 'shoes-footwear', ['size', 'color']),
            ('Women\'s Shoes', 'mdi:shoe-heel', 'shoes-footwear', ['size', 'color']),
            ('Kids Shoes', 'mdi:shoe-sneaker', 'shoes-footwear', ['size', 'color']),
            ('Sneakers', 'mdi:shoe-sneaker', 'shoes-footwear', ['size', 'color']),
            ('Sandals & Slippers', 'mdi:shoe-cleat', 'shoes-footwear', ['size', 'color']),

            # HOME SUBCATEGORIES
            ('Furniture', 'mdi:sofa', 'home-furniture', ['color', 'material']),
            ('Kitchen & Dining', 'mdi:pot-steam', 'home-furniture', ['color']),
            ('Bedding & Bath', 'mdi:bed', 'home-furniture', ['color', 'size']),
            ('Home Decor', 'mdi:lamp', 'home-furniture', ['color']),
            ('Appliances', 'mdi:washing-machine', 'home-furniture', ['color']),
        ]

        # First pass — create top-level categories
        created_categories = {}
        for name, icon, parent_slug, _ in categories_data:
            if parent_slug is None:
                from django.utils.text import slugify
                slug = slugify(name)
                cat, created = Category.objects.get_or_create(
                    slug=slug,
                    defaults={
                        'name': name,
                        'icon': icon,
                    }
                )
                created_categories[slug] = cat
                status = '✓ Created' if created else '→ Exists'
                self.stdout.write(f'  {status}: {name}')

        # Second pass — create subcategories + assign variants
        for name, icon, parent_slug, variant_slugs in categories_data:
            if parent_slug is not None:
                from django.utils.text import slugify
                slug = slugify(name)
                parent = created_categories.get(parent_slug)

                if not parent:
                    # Try to find parent by slug
                    try:
                        parent = Category.objects.get(
                            slug=parent_slug
                        )
                    except Category.DoesNotExist:
                        self.stdout.write(
                            f'  ✗ Parent not found: {parent_slug}'
                        )
                        continue

                cat, created = Category.objects.get_or_create(
                    slug=slug,
                    defaults={
                        'name': name,
                        'icon': icon,
                        'parent': parent,
                    }
                )

                # Assign required variants
                if variant_slugs:
                    for vs in variant_slugs:
                        vt = variant_types.get(vs)
                        if vt:
                            cat.required_variants.add(vt)

                created_categories[slug] = cat
                status = '✓ Created' if created else '→ Exists'
                self.stdout.write(f'  {status}: {name} (under {parent.name})')

        self.stdout.write(
            self.style.SUCCESS(
                '\n✅ Seeding complete!\n'
                f'Categories: {Category.objects.count()}\n'
                f'Variant Types: {VariantType.objects.count()}\n'
                f'Variant Options: {VariantOption.objects.count()}\n'
            )
        )