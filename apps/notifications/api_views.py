# apps/notifications/api_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from .models import Notification


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_notifications(request):
    """Get notifications for logged in user"""
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:50]

    data = [
        {
            'id': n.pk,
            'type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'link': n.link,
            'is_read': n.is_read,
            'created_at': n.created_at,
        }
        for n in notifications
    ]

    unread_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()

    return Response({
        'unread_count': unread_count,
        'results': data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True, read_at=timezone.now())

    return Response({'message': 'All notifications marked as read'})