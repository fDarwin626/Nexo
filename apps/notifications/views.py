# apps/notifications/views.py
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import Notification


@login_required
def notification_list(request):
    """Full notifications page — all notifications for this user"""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:50]

    # Mark all as read when they open the full list
    unread = notifications.filter(is_read=False)
    for n in unread:
        n.is_read = True
        n.read_at = timezone.now()
    Notification.objects.bulk_update(unread, ['is_read', 'read_at'])

    return render(request, 'notifications/list.html', {
        'notifications': notifications,
    })


@login_required
def unread_count(request):
    """
    Returns unread count as JSON.
    Called by navbar bell icon via fetch() every 30 seconds.
    """
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()

    return JsonResponse({'count': count})


@login_required
def mark_read(request, notification_id):
    """Marks a single notification as read and redirects to its link"""
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        recipient=request.user,
    )
    notification.mark_read()

    # Redirect to the notification's link if it has one
    if notification.link:
        return redirect(notification.link)

    return redirect('notifications:list')


@login_required
def mark_all_read(request):
    """Marks all notifications as read — called from bell dropdown"""
    if request.method == 'POST':
        Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(is_read=True, read_at=timezone.now())

    return JsonResponse({'status': 'ok'})