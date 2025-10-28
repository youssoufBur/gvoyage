# users/views.py
from datetime import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.translation import gettext_lazy as _

from .models import User
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    LoginSerializer, PasswordChangeSerializer, DashboardStatsSerializer
)
from core.permissions import (
    IsAuthenticatedAndVerified, IsAdmin, IsManager, IsOwnerOrAdmin,
    CanManageUsers, IsAdminOrCanManageUser, IsStaff, IsClient
)
from rest_framework_simplejwt.tokens import RefreshToken


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['role', 'status', 'agency', 'is_active']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticatedAndVerified, CanManageUsers]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, IsAdminOrCanManageUser]
        elif self.action == 'list':
            permission_classes = [IsAuthenticatedAndVerified, IsStaff]
        else:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAdmin]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated:
            if user.is_client():
                return queryset.filter(id=user.id)
            elif user.is_manager():
                managed_agencies = user.get_managed_agencies()
                return queryset.filter(agency__in=managed_agencies)
            elif user.is_staff and not user.is_admin():
                if user.agency:
                    return queryset.filter(agency=user.agency)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def profile(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put'])
    def update_profile(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        stats = request.user.get_dashboard_statistics(start_date, end_date)
        serializer = DashboardStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.is_verified = True
        user.save()
        return Response({'status': _('Utilisateur activé')})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({'status': _('Utilisateur désactivé')})
    
    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        temporary_password = User.objects.generate_temporary_password()
        user.set_password(temporary_password)
        user.save()
        
        return Response({
            'status': _('Mot de passe réinitialisé'),
            'temporary_password': temporary_password
        })

    # users/views.py - Ajouter dans UserViewSet
    @action(detail=False, methods=['get'])
    def managed_users(self, request):
        """Utilisateurs gérés selon la hiérarchie"""
        user = request.user
        managed_agencies = user.get_managed_agencies()
        
        users = User.objects.filter(agency__in=managed_agencies)
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
    

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        user.last_login_ip = self.get_client_ip(request)
        user.login_count += 1
        user.save()
        
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data
        
        return Response({
            'user': user_data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticatedAndVerified]
    
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, 
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.last_password_change = timezone.now()
        user.save()
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'status': _('Mot de passe modifié avec succès'),
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })