# apps/accounts/api_views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User


@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    """Register a new buyer account"""
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')
    full_name = request.data.get('full_name', '').strip()

    if not email or not password or not full_name:
        return Response(
            {'error': 'email, password and full_name are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if User.objects.filter(email=email).exists():
        return Response(
            {'error': 'An account with this email already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if len(password) < 8:
        return Response(
            {'error': 'Password must be at least 8 characters'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
        role='buyer',
    )

    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            'id': user.pk,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    """Login and get JWT tokens"""
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password', '')

    if not email or not password:
        return Response(
            {'error': 'email and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = authenticate(request, email=email, password=password)

    if not user:
        return Response(
            {'error': 'Invalid email or password'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Check ban status
    if user.ban_status == 'hard' or user.ban_status == 'permanent':
        return Response(
            {'error': 'This account has been suspended'},
            status=status.HTTP_403_FORBIDDEN
        )

    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            'id': user.pk,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role,
            'is_email_verified': user.is_email_verified,
            'currency_preference': user.currency_preference,
        }
    })


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def api_profile(request):
    """Get or update own profile"""
    user = request.user

    if request.method == 'GET':
        return Response({
            'id': user.pk,
            'email': user.email,
            'full_name': user.full_name,
            'phone': user.phone,
            'role': user.role,
            'is_email_verified': user.is_email_verified,
            'currency_preference': user.currency_preference,
            'date_joined': user.date_joined,
        })

    # PATCH — update allowed fields only
    allowed = ['full_name', 'phone', 'currency_preference']
    for field in allowed:
        if field in request.data:
            setattr(user, field, request.data[field])
    user.save()

    return Response({'message': 'Profile updated successfully'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_logout(request):
    """Blacklist refresh token on logout"""
    try:
        refresh_token = request.data.get('refresh')
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'message': 'Logged out successfully'})
    except Exception:
        return Response(
            {'error': 'Invalid token'},
            status=status.HTTP_400_BAD_REQUEST
        )