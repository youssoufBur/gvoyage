# Create your views here.
# locations/views.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from .models import Country, City, Agency
from .serializers import (
    CountrySerializer, CitySerializer, AgencySerializer,
    AgencyCreateSerializer, AgencyStatsSerializer
)
from core.permissions import IsAuthenticatedAndVerified, IsAdminOrAgencyManager
from users.serializers import UserSerializer


class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = [IsAuthenticatedAndVerified]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'code']


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = City.objects.all()
    serializer_class = CitySerializer
    permission_classes = [IsAuthenticatedAndVerified]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name', 'country']


class AgencyViewSet(viewsets.ModelViewSet):
    queryset = Agency.objects.filter(is_active=True)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['city', 'level', 'type', 'is_active']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AgencyCreateSerializer
        return AgencySerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminOrAgencyManager]
        else:
            permission_classes = [IsAuthenticatedAndVerified]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated and not user.is_admin():
            managed_agencies = user.get_managed_agencies()
            queryset = queryset.filter(id__in=managed_agencies)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def employees(self, request, pk=None):
        agency = self.get_object()
        employees = agency.employees.filter(is_active=True)
        serializer = UserSerializer(employees, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        agency = self.get_object()
        
        stats = {
            'total_employees': agency.employees.filter(is_active=True).count(),
            'active_vehicles': agency.vehicles.filter(is_active=True).count(),
            'today_trips': agency.trip_set.filter(
                departure_dt__date=timezone.now().date()
            ).count(),
            'monthly_revenue': 0
        }
        
        serializer = AgencyStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        agency = self.get_object()
        agency.is_active = False
        agency.save()
        return Response({'status': 'Agence désactivée'})