# parcel/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import models

from .models import Parcel, TrackingEvent
from .serializers import (
    ParcelSerializer, ParcelCreateSerializer, TrackingEventSerializer,
    ParcelTrackingSerializer, ParcelStatusUpdateSerializer
)
from core.permissions import (
    IsAuthenticatedAndVerified, IsClient, IsLivreur,
    CanManageParcels, IsOwnerOrAgencyStaff, IsAgencyStaff,
    IsAdmin, IsStaff
)


class ParcelViewSet(viewsets.ModelViewSet):
    queryset = Parcel.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        'status', 'origin_agency', 'destination_agency', 'current_agency',
        'category', 'sender'
    ]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ParcelCreateSerializer
        return ParcelSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticatedAndVerified, IsClient]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsAuthenticatedAndVerified, CanManageParcels]
        elif self.action == 'destroy':
            permission_classes = [IsAuthenticatedAndVerified, IsAdmin]
        elif self.action in ['update_status', 'mark_delivered']:
            permission_classes = [IsAuthenticatedAndVerified, CanManageParcels]
        else:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAgencyStaff]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated:
            if user.is_client():
                return queryset.filter(sender=user)
            elif user.is_livreur():
                return queryset.filter(last_handled_by=user)
            elif user.is_staff and not user.is_admin():
                managed_agencies = user.get_managed_agencies()
                return queryset.filter(
                    models.Q(origin_agency__in=managed_agencies) |
                    models.Q(destination_agency__in=managed_agencies) |
                    models.Q(current_agency__in=managed_agencies)
                )
        
        return queryset
    
    def perform_create(self, serializer):
        parcel = serializer.save(
            sender=self.request.user,
            origin_agency=self.request.user.agency if self.request.user.agency else None
        )
        parcel.generate_delivery_code()
    
    @action(detail=True, methods=['get'])
    def tracking(self, request, pk=None):
        parcel = self.get_object()
        
        tracking_data = {
            'tracking_code': parcel.tracking_code,
            'current_status': parcel.status,
            'current_location': parcel.get_current_location(),
            'timeline': [event.to_dict() for event in parcel.get_tracking_history()],
            'estimated_delivery': parcel.estimated_delivery
        }
        
        serializer = ParcelTrackingSerializer(tracking_data)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        parcel = self.get_object()
        serializer = ParcelStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        agency = None
        trip = None
        
        if serializer.validated_data.get('agency_id'):
            from locations.models import Agency
            agency = Agency.objects.get(id=serializer.validated_data['agency_id'])
        
        if serializer.validated_data.get('trip_id'):
            from transport.models import Trip
            trip = Trip.objects.get(id=serializer.validated_data['trip_id'])
        
        parcel.update_status(
            serializer.validated_data['status'],
            request.user,
            agency,
            trip,
            serializer.validated_data.get('note', '')
        )
        
        return Response({'status': 'Statut mis à jour'})
    
    @action(detail=True, methods=['post'])
    def mark_delivered(self, request, pk=None):
        parcel = self.get_object()
        
        if request.user.is_livreur() and parcel.last_handled_by != request.user:
            return Response(
                {'error': 'Vous ne pouvez pas livrer un colis qui ne vous est pas assigné'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        parcel.mark_delivered(
            request.user,
            request.FILES.get('proof'),
            request.FILES.get('signature'),
            request.data.get('note', 'Colis livré avec succès')
        )
        
        return Response({'status': 'Colis marqué comme livré'})
    
    @action(detail=False, methods=['get'])
    def track_by_code(self, request):
        tracking_code = request.GET.get('tracking_code')
        if not tracking_code:
            return Response(
                {'error': 'Code de suivi requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            parcel = Parcel.objects.get(tracking_code=tracking_code)
            serializer = ParcelSerializer(parcel, context={'request': request})
            return Response(serializer.data)
        except Parcel.DoesNotExist:
            return Response(
                {'error': 'Colis non trouvé'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def my_parcels(self, request):
        if not request.user.is_client():
            return Response(
                {'error': 'Accès réservé aux clients'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        parcels = Parcel.objects.filter(sender=request.user)
        serializer = ParcelSerializer(parcels, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_deliveries(self, request):
        if not request.user.is_livreur():
            return Response(
                {'error': 'Accès réservé aux livreurs'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        parcels = Parcel.objects.filter(last_handled_by=request.user)
        serializer = ParcelSerializer(parcels, many=True, context={'request': request})
        return Response(serializer.data)


class TrackingEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TrackingEvent.objects.all()
    serializer_class = TrackingEventSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['parcel', 'event', 'agency', 'city']
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticatedAndVerified, CanManageParcels]
        else:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAgencyStaff]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated:
            if user.is_client():
                return queryset.filter(parcel__sender=user)
            elif user.is_livreur():
                return queryset.filter(parcel__last_handled_by=user)
            elif not user.is_admin():
                managed_agencies = user.get_managed_agencies()
                return queryset.filter(agency__in=managed_agencies)
        
        return queryset