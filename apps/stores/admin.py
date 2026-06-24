
# apps/stores/admin.py
from django.contrib import admin
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import SellerProfile, Subscription, DeliveryZone, FeaturedListing, StorefrontImage


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = [
        'store_name', 'user', 'account_type',
        'status', 'is_approved', 'rating_avg',
        'strike_count', 'created_at'
    ]
    list_filter = ['status', 'is_approved', 'account_type', 'allow_pod']
    search_fields = ['store_name', 'user__email', 'fw_subaccount_id']
    readonly_fields = [
        'store_slug', 'fw_subaccount_id', 'fw_subaccount_code',
        'rating_avg', 'rating_count', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at']

    def save_model(self, request, obj, form, change):
        """
        Fires when admin saves a SellerProfile.
        Detects approval or rejection and sends email to seller.
        """
        if change:  # Only on updates not creation
            # Get original object from DB before save
            try:
                original = SellerProfile.objects.get(pk=obj.pk)
            except SellerProfile.DoesNotExist:
                original = None

            if original:
                # ── APPROVAL ─────────────────────────────────
                # Was pending, now approved
                just_approved = (
                    not original.is_approved and
                    obj.is_approved and
                    obj.status == 'active'
                )

                # ── REJECTION ────────────────────────────────
                # Had no rejection reason before, now has one
                just_rejected = (
                    not original.rejection_reason and
                    obj.rejection_reason and
                    not obj.is_approved
                )

                if just_approved:
                    # Set approval metadata
                    obj.approved_by = request.user
                    obj.approved_by = request.user
                    obj.approved_at = timezone.now()
                    # Send approval email
                    self._send_approval_email(obj)

                elif just_rejected:
                    # Send rejection email
                    self._send_rejection_email(obj)

        super().save_model(request, obj, form, change)

    def _send_approval_email(self, seller_profile):
        """Sends approval email to seller"""
        user = seller_profile.user
        subject = 'Your Nexo store has been approved!'
        message = (
            f'Hi {user.get_short_name()},\n\n'
            f'Great news! Your store "{seller_profile.store_name}" '
            f'has been approved and is now live on Nexo.\n\n'
            f'You can now:\n'
            f'- Add your products\n'
            f'- Customize your store banner\n'
            f'- Start receiving orders\n\n'
            f'Login to your dashboard to get started:\n'
            f'{settings.FRONTEND_URL}/auth/login/\n\n'
            f'Welcome to Nexo!\n\n'
            f'The Nexo Team'
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

    def _send_rejection_email(self, seller_profile):
        """Sends rejection email to seller with reason"""
        user = seller_profile.user
        subject = 'Update on your Nexo store application'
        message = (
            f'Hi {user.get_short_name()},\n\n'
            f'Thank you for applying to sell on Nexo.\n\n'
            f'Unfortunately, your store application for '
            f'"{seller_profile.store_name}" was not approved '
            f'at this time.\n\n'
            f'Reason:\n{seller_profile.rejection_reason}\n\n'
            f'You are welcome to address the issue and reapply.\n'
            f'If you have questions contact us at '
            f'{settings.DEFAULT_FROM_EMAIL}\n\n'
            f'The Nexo Team'
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Filter 'approved_by' field to show only admin/staff users.
        No more scrolling through thousands of buyers to find admin.
        """
        if db_field.name == 'approved_by':
            from django.contrib.auth import get_user_model
            User = get_user_model()
            kwargs['queryset'] = User.objects.filter(
                role='admin'
            ) | User.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(StorefrontImage)
class StorefrontImageAdmin(admin.ModelAdmin):
    list_display = ['title', 'category_hint', 'is_active', 'created_at']
    list_filter = ['is_active', 'category_hint']
    search_fields = ['title']

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'seller', 'plan', 'status',
        'start_date', 'end_date', 'days_remaining'
    ]
    list_filter = ['plan', 'status']
    search_fields = ['seller__store_name', 'fw_transaction_ref']
    readonly_fields = ['created_at']

    def days_remaining(self, obj):
        return f'{obj.days_remaining} days'
    days_remaining.short_description = 'Days Left'


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = ['seller', 'state', 'fee', 'estimated_days', 'is_active']
    list_filter = ['state', 'is_active']
    search_fields = ['seller__store_name', 'state']


@admin.register(FeaturedListing)
class FeaturedListingAdmin(admin.ModelAdmin):
    list_display = [
        'seller', 'listing_type', 'is_active',
        'starts_at', 'ends_at'
    ]
    list_filter = ['listing_type', 'is_active']
    search_fields = ['seller__store_name']





