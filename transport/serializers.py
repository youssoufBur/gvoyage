# transport/serializers.py
from rest_framework import serializers

from .models import Route, Leg, Schedule, Vehicle, Trip, TripPassenger, TripEvent

from django.utils import timezone
from rest_framework import serializers
from .models import Leg


class LegSerializer(serializers.ModelSerializer):
    origin_name = serializers.CharField(source='origin.name', read_only=True)
    destination_name = serializers.CharField(source='destination.name', read_only=True)
    schedule_count = serializers.SerializerMethodField()  # ✅ à ajouter ici

    class Meta:
        model = Leg
        fields = [
            'id',
            'route',
            'origin',
            'origin_name',
            'destination',
            'destination_name',
            'order',
            'price',
            'duration_minutes',
            'created',
            'updated',
            'schedule_count',  # ✅ tu peux le laisser ici maintenant
        ]

    def get_schedule_count(self, obj):
        """Compte uniquement les horaires actifs liés à ce tronçon"""
        return obj.schedules.filter(is_active=True).count()


class RouteSerializer(serializers.ModelSerializer):
    origin_name = serializers.CharField(source='origin.name', read_only=True)
    destination_name = serializers.CharField(source='destination.name', read_only=True)
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    legs = LegSerializer(many=True, read_only=True)
    total_duration = serializers.IntegerField(read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Route
        fields = [
            'id', 'code', 'origin', 'origin_name', 'destination', 'destination_name',
            'distance_km', 'agency', 'agency_name', 'legs', 'total_duration',
            'total_price', 'created', 'updated'
        ]


class ScheduleSerializer(serializers.ModelSerializer):
    leg_info = LegSerializer(source='leg', read_only=True)
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    
    class Meta:
        model = Schedule
        fields = [
            'id', 'leg', 'leg_info', 'agency', 'agency_name', 'departure_time',
            'days_of_week', 'is_active', 'created', 'updated'
        ]


class VehicleSerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'plate', 'capacity', 'type', 'agency', 'agency_name',
            'is_active', 'created', 'updated'
        ]


class TripSerializer(serializers.ModelSerializer):
    schedule_info = ScheduleSerializer(source='schedule', read_only=True)
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    driver_name = serializers.CharField(source='driver.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    available_seats = serializers.IntegerField(read_only=True)
    #passenger_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = Trip
        fields = [
            'id', 'schedule', 'schedule_info', 'agency', 'agency_name',
            'vehicle', 'vehicle_plate', 'driver', 'driver_name',
            'departure_dt', 'status', 'status_display', 'available_seats',
            'created', 'updated'
        ]


class TripPassengerSerializer(serializers.ModelSerializer):
    passenger_name = serializers.CharField(read_only=True)
    trip_info = TripSerializer(source='trip', read_only=True)
    client_name = serializers.CharField(source='client.full_name', read_only=True)
    
    class Meta:
        model = TripPassenger
        fields = [
            'id', 'trip', 'trip_info', 'ticket', 'client', 'client_name',
            'passenger_name', 'seat_number', 'boarded_at', 'disembarked_at',
            'disembarked_city', 'is_onboard', 'created', 'updated'
        ]


class TripEventSerializer(serializers.ModelSerializer):
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = TripEvent
        fields = [
            'id', 'trip', 'event_type', 'event_type_display', 'city', 'city_name',
            'note', 'timestamp', 'created_by', 'created_by_name', 'created', 'updated'
        ]


class AvailableTripSerializer(serializers.Serializer):
    trip_id = serializers.IntegerField()
    departure_dt = serializers.DateTimeField()
    available_seats = serializers.IntegerField()
    vehicle_plate = serializers.CharField()
    driver_name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)



# transport/serializers.py
class LegSearchSerializer(serializers.ModelSerializer):
    origin_city = serializers.CharField(source='origin.name', read_only=True)
    destination_city = serializers.CharField(source='destination.name', read_only=True)
    origin_country = serializers.CharField(source='origin.country.name', read_only=True)
    destination_country = serializers.CharField(source='destination.country.name', read_only=True)
    origin_country_code = serializers.CharField(source='origin.country.code', read_only=True)
    destination_country_code = serializers.CharField(source='destination.country.code', read_only=True)
    total_duration = serializers.IntegerField(source='duration_minutes', read_only=True)
    base_price = serializers.DecimalField(source='price', max_digits=10, decimal_places=2, read_only=True)
    available_schedules_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Leg
        fields = [
            'id', 'origin_city', 'destination_city', 
            'origin_country', 'destination_country',
            'origin_country_code', 'destination_country_code',
            'total_duration', 'base_price', 'available_schedules_count'
        ]
    
    def get_available_schedules_count(self, obj):
        return obj.schedules.filter(is_active=True).count()

class ScheduleForLegSerializer(serializers.ModelSerializer):
    departure_time = serializers.TimeField(format='%H:%M')
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    days_of_week_display = serializers.SerializerMethodField()
    is_available_today = serializers.SerializerMethodField()
    
    class Meta:
        model = Schedule
        fields = [
            'id', 'departure_time', 'days_of_week', 'days_of_week_display',
            'agency_name', 'is_active', 'is_available_today'
        ]
    
    def get_days_of_week_display(self, obj):
        day_mapping = {
            'mon': 'Lundi', 'tue': 'Mardi', 'wed': 'Mercredi',
            'thu': 'Jeudi', 'fri': 'Vendredi', 'sat': 'Samedi', 'sun': 'Dimanche'
        }
        if obj.days_of_week == 'daily':
            return 'Tous les jours'
        days = [day_mapping.get(day.strip(), day) for day in obj.days_of_week.split(',')]
        return ', '.join(days)
    
    def get_is_available_today(self, obj):
        
        today = timezone.now().date()
        day_mapping = {
            'monday': 'mon', 'tuesday': 'tue', 'wednesday': 'wed',
            'thursday': 'thu', 'friday': 'fri', 'saturday': 'sat', 'sunday': 'sun'
        }
        day_of_week = day_mapping[today.strftime('%A').lower()]
        return obj.days_of_week == 'daily' or day_of_week in obj.days_of_week
    


class LegScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = '__all__'
