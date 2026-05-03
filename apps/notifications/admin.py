# apps/notifications/admin.py
from django.contrib import admin
from .models import Notification, EmailLog


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'recipient', 'notification_type',
        'title', 'is_read', 'created_at'
    ]
    list_filter = ['notification_type', 'is_read']
    search_fields = ['recipient__email', 'title']
    readonly_fields = ['created_at', 'read_at']


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = [
        'recipient_email', 'email_type',
        'status', 'sent_at', 'created_at'
    ]
    list_filter = ['status', 'email_type']
    search_fields = ['recipient_email', 'subject']
    readonly_fields = ['created_at', 'sent_at']

    def has_change_permission(self, request, obj=None):
        return False