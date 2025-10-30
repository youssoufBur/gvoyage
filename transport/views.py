# transport/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Count, Sum, Avg 
from .models import Route, Leg, Schedule, Vehicle, Trip, TripPassenger, TripEvent
from .serializers import (
    LegScheduleSerializer, LegSearchSerializer, RouteSerializer, LegSerializer, ScheduleForLegSerializer, ScheduleSerializer, VehicleSerializer,
    TripSerializer, TripPassengerSerializer, TripEventSerializer, AvailableTripSerializer
)
from core.permissions import (
    IsAuthenticatedAndVerified, IsAdmin, IsManager, IsClient,
    IsDriverOrAgencyStaff, IsCashierOrAgencyStaff, IsAgencyStaff,
    IsAgencyManager, IsChauffeur, IsOwnerOrAgencyStaff
)
# transport/views.py
from rest_framework.views import APIView
from locations.models import City
from django_filters import rest_framework as django_filters

from rest_framework import serializers
from django.db import models

class RouteViewSet(viewsets.ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['origin', 'destination', 'agency']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, IsAgencyManager]
        else:
            permission_classes = [IsAuthenticatedAndVerified]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated and not user.is_admin():
            managed_agencies = user.get_managed_agencies()
            queryset = queryset.filter(agency__in=managed_agencies)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def available_schedules(self, request, pk=None):
        """Horaires disponibles pour une route"""
        route = self.get_object()
        date = request.GET.get('date', timezone.now().date())
        
        schedules = route.get_available_schedules(date)
        serializer = ScheduleSerializer(schedules, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search_routes(self, request):
        """Recherche de routes (pour clients)"""
        origin_id = request.GET.get('origin_id')
        destination_id = request.GET.get('destination_id')
        travel_date = request.GET.get('travel_date', timezone.now().date())
        
        if not origin_id or not destination_id:
            return Response(
                {'error': 'Les paramètres origin_id et destination_id sont requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            routes = Route.objects.filter(
                origin_id=origin_id,
                destination_id=destination_id
            )
            
            available_routes = []
            for route in routes:
                schedules = route.get_available_schedules(travel_date)
                if schedules:
                    available_routes.append({
                        'route': RouteSerializer(route).data,
                        'schedules': ScheduleSerializer(schedules, many=True).data
                    })
            
            return Response(available_routes)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# transport/views.py - Modifiez ScheduleViewSet
class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.filter(is_active=True)
    serializer_class = ScheduleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['leg', 'agency', 'is_active']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, IsAgencyManager]
        else:
            permission_classes = [IsAuthenticatedAndVerified]  # Lecture pour tous les authentifiés
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # LES CLIENTS VOIENT TOUS LES SCHEDULES ACTIFS
        if user.is_client():
            return queryset.select_related('leg', 'leg__origin', 'leg__destination', 'agency')
        
        # Les staff voient seulement les schedules de leurs agences
        if user.is_authenticated and not user.is_admin():
            managed_agencies = user.get_managed_agencies()
            queryset = queryset.filter(agency__in=managed_agencies)
        
        return queryset
    
    @action(detail=True, methods=['get'])
    def available_trips(self, request, pk=None):
        """Voyages disponibles pour un horaire - Accessible aux clients"""
        schedule = self.get_object()
        date = request.GET.get('date', timezone.now().date())
        
        trips = schedule.get_next_trips(date)
        available_trips = []
        
        for trip in trips:
            available_seats = trip.get_available_seats()
            if available_seats > 0:
                available_trips.append({
                    'trip_id': trip.id,
                    'departure_dt': trip.departure_dt,
                    'available_seats': available_seats,
                    'vehicle_plate': trip.vehicle.plate,
                    'driver_name': trip.driver.full_name,
                    'price': schedule.leg.price
                })
        
        serializer = AvailableTripSerializer(available_trips, many=True)
        return Response(serializer.data)

# transport/views.py
class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.filter(is_active=True)
    serializer_class = VehicleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['agency', 'type', 'is_active']  # Retirer 'status' qui cause l'erreur
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticatedAndVerified, IsAgencyManager]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsAuthenticatedAndVerified, IsAgencyStaff]
        elif self.action == 'destroy':
            permission_classes = [IsAuthenticatedAndVerified, IsAdmin]
        elif self.action in ['mark_maintenance', 'update_status']:
            permission_classes = [IsAuthenticatedAndVerified, IsDriverOrAgencyStaff]
        else:
            permission_classes = [IsAuthenticatedAndVerified]
        return [permission() for permission in permission_classes]

    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated:
            if user.is_chauffeur():
                return queryset.filter(trip__driver=user).distinct()
            elif not user.is_admin():
                managed_agencies = user.get_managed_agencies()
                queryset = queryset.filter(agency__in=managed_agencies)
        
        return queryset
    
    def perform_create(self, serializer):
        if self.request.user.agency and not serializer.validated_data.get('agency'):
            serializer.save(agency=self.request.user.agency)
        else:
            serializer.save()
    
    @action(detail=True, methods=['post'])
    def mark_maintenance(self, request, pk=None):
        """Marquer un véhicule comme en maintenance"""
        vehicle = self.get_object()
        vehicle.mark_maintenance()
        return Response({'status': 'Véhicule marqué en maintenance'})
    
    @action(detail=True, methods=['post'])
    def mark_available(self, request, pk=None):
        """Marquer un véhicule comme disponible"""
        vehicle = self.get_object()
        vehicle.mark_available()
        return Response({'status': 'Véhicule marqué comme disponible'})
    
    @action(detail=False, methods=['get'])
    def available_vehicles(self, request):
        """Véhicules disponibles (pour affectation aux voyages)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Accès réservé au staff'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        vehicles = Vehicle.objects.filter(
            status='available',
            is_active=True,
            agency=request.user.agency
        )
        serializer = VehicleSerializer(vehicles, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def maintenance_history(self, request, pk=None):
        """Historique de maintenance d'un véhicule"""
        vehicle = self.get_object()
        # Implémenter la logique d'historique de maintenance
        return Response({'maintenance_history': []})


class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['schedule', 'agency', 'vehicle', 'driver', 'status']
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticatedAndVerified, IsAgencyManager]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsAuthenticatedAndVerified, IsAgencyStaff]
        elif self.action == 'destroy':
            permission_classes = [IsAuthenticatedAndVerified, IsAdmin]
        elif self.action in ['update_status', 'add_event']:
            permission_classes = [IsAuthenticatedAndVerified, IsDriverOrAgencyStaff]
        else:
            permission_classes = [IsAuthenticatedAndVerified]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated:
            if user.is_client():
                return queryset.filter(departure_dt__gte=timezone.now())
            elif user.is_chauffeur():
                return queryset.filter(driver=user)
            elif not user.is_admin():
                managed_agencies = user.get_managed_agencies()
                queryset = queryset.filter(agency__in=managed_agencies)
        
        return queryset
    
    def perform_create(self, serializer):
        vehicle = serializer.validated_data.get('vehicle')
        driver = serializer.validated_data.get('driver')
        
        if vehicle.agency != driver.agency:
         
            raise serializers.ValidationError(
                "Le chauffeur et le véhicule doivent appartenir à la même agence"
            )
        
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Mettre à jour le statut d'un voyage"""
        trip = self.get_object()
        new_status = request.data.get('status')
        
        if request.user.is_chauffeur() and trip.driver != request.user:
            return Response(
                {'error': 'Vous ne pouvez modifier que vos propres voyages'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if trip.update_status(new_status):
            return Response({'status': 'Statut mis à jour'})
        else:
            return Response(
                {'error': 'Statut invalide'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def passengers(self, request, pk=None):
        """Liste des passagers d'un voyage"""
        trip = self.get_object()
        passengers = trip.passengers.all()
        serializer = TripPassengerSerializer(passengers, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def events(self, request, pk=None):
        """Événements d'un voyage"""
        trip = self.get_object()
        events = trip.events.all().order_by('timestamp')
        serializer = TripEventSerializer(events, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_trips(self, request):
        """Mes voyages (pour chauffeurs)"""
        if not request.user.is_chauffeur():
            return Response(
                {'error': 'Accès réservé aux chauffeurs'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        trips = Trip.objects.filter(driver=request.user)
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def today_trips(self, request):
        """Voyages du jour (pour staff)"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Accès réservé au staff'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        today = timezone.now().date()
        trips = Trip.objects.filter(
            departure_dt__date=today,
            agency=request.user.agency
        )
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_event(self, request, pk=None):
        """Ajouter un événement au voyage"""
        trip = self.get_object()
        
        if request.user.is_chauffeur() and trip.driver != request.user:
            return Response(
                {'error': 'Vous ne pouvez ajouter des événements qu\'à vos propres voyages'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        event_data = {
            'trip': trip.id,
            'event_type': request.data.get('event_type'),
            'city_id': request.data.get('city_id'),
            'note': request.data.get('note', ''),
            'created_by': request.user.id
        }
        
        event_serializer = TripEventSerializer(data=event_data)
        if event_serializer.is_valid():
            event_serializer.save()
            return Response({'status': 'Événement ajouté'})
        else:
            return Response(event_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TripPassengerViewSet(viewsets.ModelViewSet):
    queryset = TripPassenger.objects.all()
    serializer_class = TripPassengerSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['trip', 'client', 'is_onboard']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, IsAgencyStaff]
        elif self.action in ['mark_boarded', 'mark_disembarked']:
            permission_classes = [IsAuthenticatedAndVerified, IsDriverOrAgencyStaff]
        else:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAgencyStaff]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated:
            if user.is_client():
                return queryset.filter(client=user)
            elif user.is_chauffeur():
                return queryset.filter(trip__driver=user)
            elif not user.is_admin():
                managed_agencies = user.get_managed_agencies()
                return queryset.filter(trip__agency__in=managed_agencies)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def mark_boarded(self, request, pk=None):
        """Marquer un passager comme embarqué"""
        passenger = self.get_object()
        
        if request.user.is_chauffeur() and passenger.trip.driver != request.user:
            return Response(
                {'error': 'Vous ne pouvez embarquer que les passagers de vos voyages'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        passenger.mark_boarded()
        return Response({'status': 'Passager embarqué'})
    
    @action(detail=True, methods=['post'])
    def mark_disembarked(self, request, pk=None):
        """Marquer un passager comme débarqué"""
        passenger = self.get_object()
        city_id = request.data.get('city_id')
        
        if request.user.is_chauffeur() and passenger.trip.driver != request.user:
            return Response(
                {'error': 'Vous ne pouvez débarquer que les passagers de vos voyages'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            city = City.objects.get(id=city_id)
            passenger.mark_disembarked(city)
            return Response({'status': 'Passager débarqué'})
        except City.DoesNotExist:
            return Response(
                {'error': 'Ville invalide'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def my_passengers(self, request):
        """Mes passagers (pour chauffeurs)"""
        if not request.user.is_chauffeur():
            return Response(
                {'error': 'Accès réservé aux chauffeurs'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        passengers = TripPassenger.objects.filter(trip__driver=request.user)
        serializer = TripPassengerSerializer(passengers, many=True)
        return Response(serializer.data)


class TripEventViewSet(viewsets.ModelViewSet):
    queryset = TripEvent.objects.all()
    serializer_class = TripEventSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['trip', 'event_type', 'city']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, IsDriverOrAgencyStaff]
        else:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAgencyStaff]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated:
            if user.is_chauffeur():
                return queryset.filter(trip__driver=user)
            elif user.is_client():
                return queryset.filter(trip__passengers__client=user).distinct()
            elif not user.is_admin():
                managed_agencies = user.get_managed_agencies()
                return queryset.filter(trip__agency__in=managed_agencies)
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def trip_events(self, request):
        """Événements d'un voyage spécifique"""
        trip_id = request.GET.get('trip_id')
        if not trip_id:
            return Response(
                {'error': 'Le paramètre trip_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            events = TripEvent.objects.filter(trip_id=trip_id).order_by('timestamp')
            serializer = TripEventSerializer(events, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    # transport/views.py - Ajouter dans TripEventViewSet
    @action(detail=False, methods=['get'])
    def agency_incidents(self, request):
        """Incidents par agence (pour chefs)"""
        user = request.user
        agency_filter = user._get_agency_filter()
        
        incidents = TripEvent.objects.filter(
            **agency_filter,
            event_type__in=['incident', 'accident', 'delay']
        )
        
        # Statistiques par agence
        stats = incidents.values('trip__agency__name').annotate(
            total=Count('id'),
            serious=Count('id', filter=models.Q(event_type='accident'))
        )
        
        return Response(stats)


class LegFilter(django_filters.FilterSet):
    origin_city = django_filters.CharFilter(field_name='origin__name', lookup_expr='icontains')
    destination_city = django_filters.CharFilter(field_name='destination__name', lookup_expr='icontains')
    
    class Meta:
        model = Leg
        fields = ['route', 'origin', 'destination']

# transport/views.py - Modifiez SEULEMENT LegViewSet
class LegViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Leg.objects.all()
    serializer_class = LegSerializer
    permission_classes = [IsAuthenticatedAndVerified]  # Garder seulement l'authentification
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['route', 'origin', 'destination']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # LES CLIENTS VOIENT TOUS LES LEGS
        if user.is_client():
            return queryset.select_related('origin', 'destination', 'origin__country', 'destination__country')
        
        # Les staff voient seulement les legs de leurs agences
        if user.is_authenticated and not user.is_admin():
            managed_agencies = user.get_managed_agencies()
            queryset = queryset.filter(route__agency__in=managed_agencies)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Recherche de trajets par villes - Accessible aux clients"""
        origin_city = request.GET.get('origin_city')
        destination_city = request.GET.get('destination_city')
        origin_country = request.GET.get('origin_country')
        destination_country = request.GET.get('destination_country')
        
        queryset = self.get_queryset()
        
        if origin_city:
            queryset = queryset.filter(origin__name__icontains=origin_city)
        if destination_city:
            queryset = queryset.filter(destination__name__icontains=destination_city)
        if origin_country:
            queryset = queryset.filter(origin__country__name__icontains=origin_country)
        if destination_country:
            queryset = queryset.filter(destination__country__name__icontains=destination_country)
        
        serializer = LegSearchSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def schedules(self, request, pk=None):
        """Récupérer les horaires d'un trajet - Accessible aux clients"""
        leg = self.get_object()
        schedules = leg.schedules.filter(is_active=True)
        serializer = ScheduleForLegSerializer(schedules, many=True)
        return Response(serializer.data)

class LegScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.all()
    serializer_class = LegScheduleSerializer
