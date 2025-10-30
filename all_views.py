# ==================================================
# FICHIER: all_views.py
# DESCRIPTION: Tous les fichiers views des applications Django
# GÉNÉRÉ LE: Tue Oct 28 14:01:53 UTC 2025
# ==================================================


# ==================================================
# APPLICATION: users
# FICHIER: views.py
# ==================================================

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



# ==================================================
# APPLICATION: locations
# FICHIER: views.py
# ==================================================

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



# ==================================================
# APPLICATION: transport
# FICHIER: views.py
# ==================================================

# transport/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Count, Sum, Avg 
from .models import Route, Leg, Schedule, Vehicle, Trip, TripPassenger, TripEvent
from .serializers import (
    RouteSerializer, LegSerializer, ScheduleSerializer, VehicleSerializer,
    TripSerializer, TripPassengerSerializer, TripEventSerializer, AvailableTripSerializer
)
from core.permissions import (
    IsAuthenticatedAndVerified, IsAdmin, IsManager, IsClient,
    IsDriverOrAgencyStaff, IsCashierOrAgencyStaff, IsAgencyStaff,
    IsAgencyManager, IsChauffeur, IsOwnerOrAgencyStaff
)
from locations.models import City

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


class ScheduleViewSet(viewsets.ModelViewSet):
    queryset = Schedule.objects.filter(is_active=True)
    serializer_class = ScheduleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['leg', 'agency', 'is_active']
    
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
    def available_trips(self, request, pk=None):
        """Voyages disponibles pour un horaire"""
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
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticatedAndVerified, IsAgencyManager])
    def toggle_active(self, request, pk=None):
        """Activer/désactiver un horaire"""
        schedule = self.get_object()
        schedule.is_active = not schedule.is_active
        schedule.save()
        
        status_msg = 'activé' if schedule.is_active else 'désactivé'
        return Response({'status': f'Horaire {status_msg}'})


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

class LegViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet pour les tronçons de route"""
    queryset = Leg.objects.all()  # Retirer le filtre is_active qui n'existe pas
    serializer_class = LegSerializer
    permission_classes = [IsAuthenticatedAndVerified]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['route', 'origin_city', 'destination_city']  # Retirer is_active
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated and not user.is_admin():
            managed_agencies = user.get_managed_agencies()
            queryset = queryset.filter(route__agency__in=managed_agencies)
        
        return queryset





# ==================================================
# APPLICATION: reservations
# FICHIER: views.py
# ==================================================

# reservations/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse
from django.utils import timezone
import os
from django.conf import settings

from .models import Reservation, Ticket, Payment
from .serializers import (
    ReservationSerializer, ReservationCreateSerializer,
    TicketSerializer, TicketScanSerializer, ScanResultSerializer,
    PaymentSerializer, PaymentCreateSerializer
)
from core.permissions import (
    IsAuthenticatedAndVerified, IsClient, IsCaissier, IsOwnerOrStaff,
    CanScanTickets, IsOwnerOrAgencyStaff, IsCashierOrAgencyStaff,
    IsStaff, IsAgencyStaff
)


class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'travel_date', 'schedule']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ReservationCreateSerializer
        return ReservationSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticatedAndVerified]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAgencyStaff]
        elif self.action in ['confirm', 'cancel']:
            permission_classes = [IsAuthenticatedAndVerified, IsCashierOrAgencyStaff]
        else:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAgencyStaff]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_client():
            return Reservation.objects.filter(buyer=user)
        elif user.is_staff:
            managed_agencies = user.get_managed_agencies()
            return Reservation.objects.filter(
                schedule__agency__in=managed_agencies
            )
        else:
            return Reservation.objects.all()
    
    def perform_create(self, serializer):
        if self.request.user.is_client():
            reservation = serializer.save(buyer=self.request.user)
        else:
            reservation = serializer.save()
        
        reservation.total_price = reservation.schedule.leg.price * reservation.total_seats
        reservation.save()
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        reservation = self.get_object()
        reservation.confirm_reservation()
        return Response({'status': 'Réservation confirmée'})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        reservation = self.get_object()
        reason = request.data.get('reason', '')
        reservation.cancel_reservation(reason)
        return Response({'status': 'Réservation annulée'})
    
    @action(detail=True, methods=['get'])
    def tickets(self, request, pk=None):
        reservation = self.get_object()
        tickets = reservation.tickets.all()
        serializer = TicketSerializer(tickets, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_reservations(self, request):
        if not request.user.is_client():
            return Response(
                {'error': 'Accès réservé aux clients'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        reservations = Reservation.objects.filter(buyer=request.user)
        serializer = ReservationSerializer(reservations, many=True)
        return Response(serializer.data)


class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['reservation', 'trip', 'status', 'scanned_at']
    
    def get_permissions(self):
        if self.action == 'scan':
            permission_classes = [IsAuthenticatedAndVerified, CanScanTickets]
        else:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAgencyStaff]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_client():
            return Ticket.objects.filter(buyer=user)
        elif user.is_staff:
            managed_agencies = user.get_managed_agencies()
            return Ticket.objects.filter(
                trip__agency__in=managed_agencies
            )
        else:
            return Ticket.objects.all()
    
    @action(detail=False, methods=['post'])
    def scan(self, request):
        serializer = TicketScanSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        ticket = serializer.context['ticket']
        scan_location_id = serializer.validated_data.get('scan_location_id')
        
        scan_location = None
        if scan_location_id:
            from locations.models import City
            try:
                scan_location = City.objects.get(id=scan_location_id)
            except City.DoesNotExist:
                pass
        
        result = ticket.scan_ticket(request.user, scan_location)
        result_serializer = ScanResultSerializer(result)
        
        return Response(result_serializer.data)
    
    @action(detail=True, methods=['get'])
    def qr_code(self, request, pk=None):
        ticket = self.get_object()
        if ticket.qr_image:
            qr_path = os.path.join(settings.MEDIA_ROOT, ticket.qr_image.name)
            with open(qr_path, 'rb') as f:
                return HttpResponse(f.read(), content_type='image/png')
        else:
            return Response({'error': 'QR code non disponible'}, status=404)
    
    @action(detail=False, methods=['get'])
    def my_tickets(self, request):
        if not request.user.is_client():
            return Response(
                {'error': 'Accès réservé aux clients'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        tickets = Ticket.objects.filter(buyer=request.user)
        serializer = TicketSerializer(tickets, many=True, context={'request': request})
        return Response(serializer.data)


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['reservation', 'method', 'status', 'agency']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentCreateSerializer
        return PaymentSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticatedAndVerified, IsCashierOrAgencyStaff]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, IsCashierOrAgencyStaff]
        elif self.action in ['mark_completed', 'mark_failed']:
            permission_classes = [IsAuthenticatedAndVerified, IsCaissier]
        else:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAgencyStaff]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_caissier() or (user.is_staff and user.agency):
            return Payment.objects.filter(agency=user.agency)
        elif user.is_client():
            return Payment.objects.filter(reservation__buyer=user)
        else:
            return Payment.objects.all()
    
    def perform_create(self, serializer):
        payment = serializer.save()
        if self.request.user.is_caissier() and not payment.agency:
            payment.agency = self.request.user.agency
            payment.save()
    
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        payment = self.get_object()
        provider_ref = request.data.get('provider_ref')
        
        payment.mark_completed(provider_ref)
        return Response({'status': 'Paiement complété'})
    
    @action(detail=True, methods=['post'])
    def mark_failed(self, request, pk=None):
        payment = self.get_object()
        payment.mark_failed()
        return Response({'status': 'Paiement marqué comme échoué'})
    
    @action(detail=False, methods=['get'])
    def my_payments(self, request):
        if not request.user.is_client():
            return Response(
                {'error': 'Accès réservé aux clients'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        payments = Payment.objects.filter(reservation__buyer=request.user)
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)



# ==================================================
# APPLICATION: parcel
# FICHIER: views.py
# ==================================================

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



# ==================================================
# APPLICATION: publications
# FICHIER: views.py
# ==================================================

# publications/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import models

from .models import Publication, Notification, SupportTicket, SupportMessage
from .serializers import (
    PublicationSerializer, PublicationCreateSerializer,
    NotificationSerializer, SupportTicketSerializer, SupportMessageSerializer
)
from core.permissions import (
    IsAuthenticatedAndVerified, IsAdmin, IsManager, IsClient,
    IsOwnerOrAdmin, IsOwnerOrAgencyStaff, IsStaff,
    CanCreatePublication, CanManageSystemConfig, IsAgencyStaff
)


class PublicationViewSet(viewsets.ModelViewSet):
    queryset = Publication.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['publication_type', 'audience', 'status', 'is_active', 'author']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return PublicationCreateSerializer
        return PublicationSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticatedAndVerified, CanCreatePublication]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAdmin]
        elif self.action in ['publish', 'unpublish']:
            permission_classes = [IsAuthenticatedAndVerified, IsManager | IsAdmin]
        else:
            permission_classes = [IsAuthenticatedAndVerified]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated:
            if user.is_admin():
                return queryset
            
            visible_publications = []
            for publication in queryset:
                if publication.is_visible_to_user(user):
                    visible_publications.append(publication.id)
            
            return queryset.filter(id__in=visible_publications)
        
        return queryset.none()
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        publication = self.get_object()
        publication.publish()
        return Response({'status': 'Publication publiée'})
    
    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        publication = self.get_object()
        publication.unpublish()
        return Response({'status': 'Publication dépubliée'})
    
    @action(detail=True, methods=['post'])
    def increment_views(self, request, pk=None):
        publication = self.get_object()
        publication.increment_view_count()
        return Response({'status': 'Compteur de vues incrémenté'})
    
    @action(detail=False, methods=['get'])
    def my_publications(self, request):
        publications = Publication.objects.filter(author=request.user)
        serializer = PublicationSerializer(publications, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active_publications(self, request):
        publications = Publication.objects.filter(
            is_active=True,
            status=Publication.Status.PUBLISHED,
            start_date__lte=timezone.now(),
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=timezone.now())
        )
        
        visible_publications = [
            pub for pub in publications if pub.is_visible_to_user(request.user)
        ]
        
        serializer = PublicationSerializer(visible_publications, many=True)
        return Response(serializer.data)
    
    # publications/views.py - Améliorer PublicationViewSet
    @action(detail=False, methods=['post'])
    def broadcast_to_agencies(self, request):
        """Diffuser un communiqué aux agences gérées"""
        if not request.user.is_manager():
            return Response(
                {'error': 'Accès réservé aux managers'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        managed_agencies = request.user.get_managed_agencies()
        # Logique de diffusion aux agences
        
    


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['notification_type', 'status', 'channel']
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, IsAdmin]
        else:
            permission_classes = [IsAuthenticatedAndVerified]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        if not self.request.user.is_admin():
            return Response(
                {'error': 'Action non autorisée'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'status': 'Notification marquée comme lue'})
    
    @action(detail=True, methods=['post'])
    def mark_unread(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_unread()
        return Response({'status': 'Notification marquée comme non lue'})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        notifications = self.get_queryset().filter(status='unread')
        notifications.update(status='read', read_at=timezone.now())
        return Response({'status': 'Toutes les notifications marquées comme lues'})
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        unread_count = self.get_queryset().filter(status='unread').count()
        return Response({'unread_count': unread_count})


class SupportTicketViewSet(viewsets.ModelViewSet):
    queryset = SupportTicket.objects.all()
    serializer_class = SupportTicketSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'status', 'priority', 'assigned_to', 'agency']
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticatedAndVerified]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAgencyStaff]
        elif self.action == 'destroy':
            permission_classes = [IsAuthenticatedAndVerified, IsAdmin]
        elif self.action in ['assign', 'update_status']:
            permission_classes = [IsAuthenticatedAndVerified, IsStaff]
        else:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAgencyStaff]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated:
            if user.is_client():
                return queryset.filter(user=user)
            elif user.is_staff:
                if user.agency:
                    return queryset.filter(agency=user.agency)
                else:
                    return queryset
            elif user.is_manager():
                managed_agencies = user.get_managed_agencies()
                return queryset.filter(agency__in=managed_agencies)
        
        return queryset
    
    def perform_create(self, serializer):
        if self.request.user.agency:
            serializer.save(user=self.request.user, agency=self.request.user.agency)
        else:
            serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        ticket = self.get_object()
        agent_id = request.data.get('agent_id')
        
        from users.models import User
        try:
            agent = User.objects.get(id=agent_id)
            if not agent.is_staff:
                return Response(
                    {'error': 'L\'utilisateur n\'est pas membre du staff'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            ticket.assign_to_agent(agent, request.user)
            return Response({'status': 'Ticket assigné'})
        except User.DoesNotExist:
            return Response(
                {'error': 'Agent non trouvé'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        ticket = self.get_object()
        new_status = request.data.get('status')
        note = request.data.get('note', '')
        
        if new_status not in dict(SupportTicket.Status.choices):
            return Response(
                {'error': 'Statut invalide'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ticket.update_status(new_status, request.user, note)
        return Response({'status': f'Statut mis à jour: {new_status}'})
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        ticket = self.get_object()
        messages = ticket.messages.all()
        serializer = SupportMessageSerializer(messages, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_tickets(self, request):
        if not request.user.is_client():
            return Response(
                {'error': 'Accès réservé aux clients'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        tickets = SupportTicket.objects.filter(user=request.user)
        serializer = SupportTicketSerializer(tickets, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def assigned_tickets(self, request):
        if not request.user.is_staff:
            return Response(
                {'error': 'Accès réservé au staff'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        tickets = SupportTicket.objects.filter(assigned_to=request.user)
        serializer = SupportTicketSerializer(tickets, many=True)
        return Response(serializer.data)


class SupportMessageViewSet(viewsets.ModelViewSet):
    queryset = SupportMessage.objects.all()
    serializer_class = SupportMessageSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['ticket', 'message_type', 'user']
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [IsAuthenticatedAndVerified]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAdmin]
        else:
            permission_classes = [IsAuthenticatedAndVerified, IsOwnerOrAgencyStaff]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated:
            if user.is_client():
                return queryset.filter(ticket__user=user)
            elif user.is_staff:
                if user.agency:
                    return queryset.filter(ticket__agency=user.agency)
        
        return queryset
    
    def perform_create(self, serializer):
        ticket = serializer.validated_data['ticket']
        
        if not (ticket.user == self.request.user or 
                ticket.assigned_to == self.request.user or
                (self.request.user.is_staff and ticket.agency == self.request.user.agency) or
                self.request.user.is_admin()):
            return Response(
                {'error': 'Vous n\'avez pas la permission de répondre à ce ticket'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer.save(user=self.request.user)



# ==================================================
# APPLICATION: parameter
# FICHIER: views.py
# ==================================================

# parameter/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import CompanyConfig, SystemParameter
from .serializers import (
    CompanyConfigSerializer, CompanyConfigUpdateSerializer,
    SystemParameterSerializer, SystemParameterCreateSerializer,
    PublicCompanyInfoSerializer, BusinessRulesSerializer, SystemSettingsSerializer
)
from core.permissions import (
    IsAuthenticatedAndVerified, IsAdmin, IsManager,
    CanManageSystemConfig, CanViewFinancialData, IsStaff,
    IsAdminOrReadOnly, IsStaffOrReadOnly
)


class CompanyConfigViewSet(viewsets.ModelViewSet):
    queryset = CompanyConfig.objects.all()
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return CompanyConfigUpdateSerializer
        return CompanyConfigSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, CanManageSystemConfig]
        elif self.action in ['toggle_maintenance', 'reset_to_default']:
            permission_classes = [IsAuthenticatedAndVerified, IsAdmin]
        else:
            permission_classes = [IsAuthenticatedAndVerified]
        return [permission() for permission in permission_classes]
    
    def get_object(self):
        return CompanyConfig.get_cached_config()
    
    def list(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        return Response(
            {'error': _('Une configuration existe déjà. Utilisez la mise à jour.')},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get'])
    def public_info(self, request):
        config = CompanyConfig.get_cached_config()
        
        logo_url = None
        if config.logo and hasattr(config.logo, 'url'):
            logo_url = request.build_absolute_uri(config.logo.url)
        
        public_data = {
            'name': config.name,
            'slogan': config.slogan,
            'logo': logo_url,
            'phone': config.phone,
            'email': config.email,
            'address': config.full_address,
            'social_links': config.get_social_links(),
            'business_hours': config.business_hours,
        }
        
        serializer = PublicCompanyInfoSerializer(public_data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticatedAndVerified])
    def business_rules(self, request):
        config = CompanyConfig.get_cached_config()
        
        business_rules = {
            'max_seats_per_booking': config.max_seats_per_booking,
            'booking_expiry_minutes': config.booking_expiry_minutes,
            'allow_online_payment': config.allow_online_payment,
            'max_parcel_weight': float(config.max_parcel_weight),
            'parcel_insurance_required': config.parcel_insurance_required,
        }
        
        serializer = BusinessRulesSerializer(business_rules)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticatedAndVerified])
    def system_settings(self, request):
        config = CompanyConfig.get_cached_config()
        
        system_settings = {
            'maintenance_mode': config.maintenance_mode,
            'enable_sms_notifications': config.enable_sms_notifications,
            'enable_email_notifications': config.enable_email_notifications,
            'currency': config.currency,
            'timezone': config.timezone,
            'language': config.language,
        }
        
        serializer = SystemSettingsSerializer(system_settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticatedAndVerified])
    def contact_info(self, request):
        config = CompanyConfig.get_cached_config()
        return Response(config.get_contact_info())
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticatedAndVerified])
    def support_contacts(self, request):
        config = CompanyConfig.get_cached_config()
        return Response(config.get_support_contacts())
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticatedAndVerified, IsAdmin])
    def toggle_maintenance(self, request):
        config = CompanyConfig.get_cached_config()
        config.maintenance_mode = not config.maintenance_mode
        config.save()
        
        status_msg = _('activé') if config.maintenance_mode else _('désactivé')
        return Response({
            'status': _('Mode maintenance {}').format(status_msg),
            'maintenance_mode': config.maintenance_mode
        })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticatedAndVerified, IsAdmin])
    def reset_to_default(self, request):
        config = CompanyConfig.get_cached_config()
        default_config = CompanyConfig.create_default_config()
        
        for field in CompanyConfig._meta.fields:
            if field.name not in ['id', 'created', 'updated']:
                setattr(config, field.name, getattr(default_config, field.name))
        
        config.save()
        default_config.delete()
        
        return Response({'status': _('Configuration réinitialisée aux valeurs par défaut')})


class SystemParameterViewSet(viewsets.ModelViewSet):
    queryset = SystemParameter.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'data_type', 'is_public']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SystemParameterCreateSerializer
        return SystemParameterSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndVerified, CanManageSystemConfig]
        elif self.action == 'bulk_update':
            permission_classes = [IsAuthenticatedAndVerified, IsAdmin]
        else:
            permission_classes = [IsAuthenticatedAndVerified]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_authenticated and not user.is_admin():
            queryset = queryset.filter(is_public=True)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def public_parameters(self, request):
        parameters = SystemParameter.objects.filter(is_public=True)
        public_data = {}
        for param in parameters:
            public_data[param.key] = param.get_typed_value()
        
        return Response(public_data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticatedAndVerified])
    def by_category(self, request):
        categories = {}
        for category in SystemParameter.Category.choices:
            category_key = category[0]
            if self.request.user.is_admin():
                parameters = SystemParameter.objects.filter(category=category_key)
            else:
                parameters = SystemParameter.objects.filter(category=category_key, is_public=True)
            
            categories[category_key] = {
                'display_name': category[1],
                'parameters': SystemParameterSerializer(parameters, many=True).data
            }
        
        return Response(categories)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticatedAndVerified, IsAdmin])
    def bulk_update(self, request):
        parameters_data = request.data.get('parameters', {})
        
        updated = []
        errors = []
        
        for key, value in parameters_data.items():
            try:
                param = SystemParameter.objects.get(key=key)
                param.value = str(value)
                param.save()
                updated.append(key)
            except SystemParameter.DoesNotExist:
                errors.append(_("Paramètre {} non trouvé").format(key))
            except Exception as e:
                errors.append(_("Erreur avec {}: {}").format(key, str(e)))
        
        response_data = {
            'updated': updated,
            'errors': errors,
            'total_updated': len(updated),
            'total_errors': len(errors)
        }
        
        return Response(response_data)


class ParameterValidationAPIView(APIView):
    permission_classes = [IsAuthenticatedAndVerified]
    
    def post(self, request):
        validation_type = request.data.get('type')
        value = request.data.get('value')
        
        config = CompanyConfig.get_cached_config()
        
        if validation_type == 'booking_seats':
            try:
                config.validate_booking_seats(int(value))
                return Response({'valid': True, 'message': _('Nombre de sièges valide')})
            except ValueError as e:
                return Response({'valid': False, 'message': str(e)})
        
        elif validation_type == 'parcel_weight':
            try:
                from decimal import Decimal
                config.validate_parcel_weight(Decimal(value))
                return Response({'valid': True, 'message': _('Poids de colis valide')})
            except ValueError as e:
                return Response({'valid': False, 'message': str(e)})
        
        else:
            return Response(
                {'error': _('Type de validation non supporté')},
                status=status.HTTP_400_BAD_REQUEST
            )


class SystemStatusAPIView(APIView):
    permission_classes = [IsAuthenticatedAndVerified]
    
    def get(self, request):
        config = CompanyConfig.get_cached_config()
        
        status_info = {
            'maintenance_mode': config.maintenance_mode,
            'online_payment_available': config.is_online_payment_available,
            'sms_notifications_enabled': config.can_send_sms(),
            'email_notifications_enabled': config.can_send_email(),
            'system_time': timezone.now().isoformat(),
            'timezone': config.timezone,
        }
        
        return Response(status_info)



# ==================================================
# APPLICATION: core
# FICHIER: views.py
# ==================================================

from django.shortcuts import render

# Create your views here.



