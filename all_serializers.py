# ==================================================
# FICHIER: all_serializers.py
# DESCRIPTION: Tous les fichiers serializers des applications Django
# GÉNÉRÉ LE: Tue Oct 28 14:01:53 UTC 2025
# ==================================================


# ==================================================
# APPLICATION: users
# FICHIER: serializers.py
# ==================================================

# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import User


class UserSerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'phone', 'full_name', 'email', 'role', 'role_display',
            'status', 'status_display', 'agency', 'agency_name', 'is_active',
            'is_verified', 'date_joined', 'last_login', 'gender',
            'date_of_birth', 'address', 'city'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = [
            'phone', 'full_name', 'email', 'role', 'agency', 
            'password', 'gender', 'date_of_birth', 'address', 'city'
        ]
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create_user(**validated_data, password=password)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'full_name', 'email', 'gender', 'date_of_birth',
            'address', 'city', 'national_id', 'phone_secondary'
        ]


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        phone = attrs.get('phone')
        password = attrs.get('password')
        
        if phone and password:
            user = authenticate(phone=phone, password=password)
            if not user:
                raise serializers.ValidationError(_('Identifiants invalides'))
            if not user.is_active:
                raise serializers.ValidationError(_('Compte désactivé'))
            if not user.is_verified and not user.is_client():
                raise serializers.ValidationError(_('Compte non vérifié'))
        else:
            raise serializers.ValidationError(_('Phone et mot de passe requis'))
        
        attrs['user'] = user
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_('Ancien mot de passe incorrect'))
        return value


class DashboardStatsSerializer(serializers.Serializer):
    period = serializers.DictField()
    user_role = serializers.CharField()
    user_agency = serializers.CharField(allow_null=True)
    total_tickets = serializers.IntegerField(required=False)
    total_spent = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_trips = serializers.IntegerField(required=False)
    completed_trips = serializers.IntegerField(required=False)
    total_payments = serializers.IntegerField(required=False)
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    total_parcels = serializers.IntegerField(required=False)
    delivered_parcels = serializers.IntegerField(required=False)



# ==================================================
# APPLICATION: locations
# FICHIER: serializers.py
# ==================================================

# locations/serializers.py
from rest_framework import serializers

from .models import Country, City, Agency


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'created', 'updated']


class CitySerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    country_code = serializers.CharField(source='country.code', read_only=True)
    
    class Meta:
        model = City
        fields = ['id', 'name', 'country', 'country_name', 'country_code', 'created', 'updated']


class AgencySerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source='city.name', read_only=True)
    country_name = serializers.CharField(source='city.country.name', read_only=True)
    parent_agency_name = serializers.CharField(source='parent_agency.name', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    class Meta:
        model = Agency
        fields = [
            'id', 'name', 'code', 'city', 'city_name', 'country_name',
            'level', 'level_display', 'type', 'type_display',
            'parent_agency', 'parent_agency_name', 'address',
            'phone', 'email', 'is_active', 'created', 'updated'
        ]


class AgencyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agency
        fields = [
            'name', 'code', 'city', 'level', 'type', 
            'parent_agency', 'address', 'phone', 'email'
        ]
    
    def validate_code(self, value):
        if Agency.objects.filter(code=value).exists():
            raise serializers.ValidationError("Ce code d'agence existe déjà")
        return value


class AgencyStatsSerializer(serializers.Serializer):
    total_employees = serializers.IntegerField()
    active_vehicles = serializers.IntegerField()
    today_trips = serializers.IntegerField()
    monthly_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)



# ==================================================
# APPLICATION: transport
# FICHIER: serializers.py
# ==================================================

# transport/serializers.py
from rest_framework import serializers

from .models import Route, Leg, Schedule, Vehicle, Trip, TripPassenger, TripEvent


class LegSerializer(serializers.ModelSerializer):
    origin_name = serializers.CharField(source='origin.name', read_only=True)
    destination_name = serializers.CharField(source='destination.name', read_only=True)
    
    class Meta:
        model = Leg
        fields = [
            'id', 'route', 'origin', 'origin_name', 'destination', 'destination_name',
            'order', 'price', 'duration_minutes', 'created', 'updated'
        ]


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



# ==================================================
# APPLICATION: reservations
# FICHIER: serializers.py
# ==================================================

# reservations/serializers.py
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from .models import Reservation, Ticket, Payment


class ReservationSerializer(serializers.ModelSerializer):
    buyer_name = serializers.CharField(source='buyer.full_name', read_only=True)
    schedule_info = serializers.CharField(source='schedule.__str__', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    travel_details = serializers.DictField(read_only=True)
    
    class Meta:
        model = Reservation
        fields = [
            'id', 'code', 'buyer', 'buyer_name', 'schedule', 'schedule_info',
            'travel_date', 'total_seats', 'total_price', 'status', 'status_display',
            'expires_at', 'notes', 'travel_details', 'created', 'updated'
        ]
        read_only_fields = ['code', 'status', 'expires_at']


class ReservationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = ['schedule', 'travel_date', 'total_seats', 'notes']
    
    def validate(self, attrs):
        schedule = attrs.get('schedule')
        travel_date = attrs.get('travel_date')
        total_seats = attrs.get('total_seats', 1)
        
        available_seats = schedule.get_available_seats(travel_date)
        if total_seats > available_seats:
            raise serializers.ValidationError(
                f"Seulement {available_seats} sièges disponibles"
            )
        
        return attrs
    
    def create(self, validated_data):
        validated_data['buyer'] = self.context['request'].user
        return super().create(validated_data)


class TicketSerializer(serializers.ModelSerializer):
    reservation_code = serializers.CharField(source='reservation.code', read_only=True)
    trip_info = serializers.CharField(source='trip.__str__', read_only=True)
    buyer_name = serializers.CharField(source='buyer.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    qr_code_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_code', 'reservation', 'reservation_code', 'trip', 'trip_info',
            'buyer', 'buyer_name', 'passenger_name', 'passenger_phone', 'passenger_email',
            'passenger_id', 'seat_number', 'status', 'status_display', 'scanned_at',
            'scanned_by', 'boarding_time', 'scan_location', 'qr_code_url',
            'created', 'updated'
        ]
        read_only_fields = ['ticket_code', 'qr_token', 'qr_image']
    
    def get_qr_code_url(self, obj):
        request = self.context.get('request')
        if request and obj.qr_image:
            return request.build_absolute_uri(obj.qr_image.url)
        return None


class TicketScanSerializer(serializers.Serializer):
    ticket_code = serializers.CharField()
    scan_location_id = serializers.IntegerField(required=False)
    
    def validate_ticket_code(self, value):
        try:
            ticket = Ticket.objects.get(ticket_code=value)
        except Ticket.DoesNotExist:
            raise serializers.ValidationError("Ticket non trouvé")
        
        self.context['ticket'] = ticket
        return value


class ScanResultSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    ticket_status = serializers.CharField()
    trip_status = serializers.CharField(allow_null=True)
    already_boarded = serializers.BooleanField()
    trip_departed = serializers.BooleanField()
    trip_completed = serializers.BooleanField()
    current_location = serializers.DictField(allow_null=True)


class PaymentSerializer(serializers.ModelSerializer):
    reservation_code = serializers.CharField(source='reservation.code', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    agency_name = serializers.CharField(source='agency.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'reservation', 'reservation_code', 'method', 'method_display',
            'amount', 'status', 'status_display', 'provider_ref', 'paid_at',
            'agency', 'agency_name', 'created', 'updated'
        ]
        read_only_fields = ['status', 'paid_at', 'provider_ref']


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['reservation', 'method', 'agency']
    
    def validate(self, attrs):
        reservation = attrs.get('reservation')
        
        if reservation.status != Reservation.Status.CONFIRMED:
            raise serializers.ValidationError(
                "La réservation doit être confirmée pour le paiement"
            )
        
        attrs['amount'] = reservation.total_price
        return attrs



# ==================================================
# APPLICATION: parcel
# FICHIER: serializers.py
# ==================================================

# parcel/serializers.py
from rest_framework import serializers

from .models import Parcel, TrackingEvent


class ParcelSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    origin_agency_name = serializers.CharField(source='origin_agency.name', read_only=True)
    destination_agency_name = serializers.CharField(source='destination_agency.name', read_only=True)
    current_agency_name = serializers.CharField(source='current_agency.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    tracking_url = serializers.SerializerMethodField()
    qr_code_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Parcel
        fields = [
            'id', 'tracking_code', 'sender', 'sender_name', 'sender_phone', 'sender_address',
            'receiver_name', 'receiver_phone', 'receiver_address', 'receiver_city',
            'origin_agency', 'origin_agency_name', 'destination_agency', 'destination_agency_name',
            'origin_city', 'destination_city', 'category', 'category_display', 'description',
            'weight_kg', 'dimensions', 'declared_value', 'base_price', 'insurance_fee',
            'delivery_fee', 'total_price', 'status', 'status_display', 'current_city',
            'current_agency', 'current_agency_name', 'current_trip', 'requires_signature',
            'requires_delivery_confirmation', 'home_delivery', 'insurance_required',
            'delivery_proof', 'recipient_signature', 'delivery_code', 'last_handled_by',
            'estimated_delivery', 'actual_delivery', 'delivery_attempts', 'tracking_url',
            'qr_code_url', 'created', 'updated'
        ]
        read_only_fields = ['tracking_code', 'qr_token', 'qr_image', 'delivery_code']
    
    def get_tracking_url(self, obj):
        request = self.context.get('request')
        return obj.get_tracking_url(request) if request else None
    
    def get_qr_code_url(self, obj):
        request = self.context.get('request')
        return obj.get_qr_code_url(request) if request else None


class ParcelCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parcel
        fields = [
            'receiver_name', 'receiver_phone', 'receiver_address', 'receiver_city',
            'destination_agency', 'category', 'description', 'weight_kg', 'dimensions',
            'declared_value', 'requires_signature', 'home_delivery', 'insurance_required'
        ]
    
    def create(self, validated_data):
        validated_data['sender'] = self.context['request'].user
        validated_data['origin_agency'] = self.context['request'].user.agency
        return super().create(validated_data)


class TrackingEventSerializer(serializers.ModelSerializer):
    event_display = serializers.CharField(source='get_event_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    actor_name = serializers.CharField(source='actor.full_name', read_only=True)
    
    class Meta:
        model = TrackingEvent
        fields = [
            'id', 'parcel', 'event', 'event_display', 'status', 'status_display',
            'city', 'city_name', 'agency', 'agency_name', 'trip', 'note',
            'actor', 'actor_name', 'ts', 'latitude', 'longitude', 'photos',
            'created', 'updated'
        ]


class ParcelTrackingSerializer(serializers.Serializer):
    tracking_code = serializers.CharField()
    current_status = serializers.CharField()
    current_location = serializers.DictField()
    timeline = serializers.ListField()
    estimated_delivery = serializers.DateTimeField(allow_null=True)


class ParcelStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Parcel.Status.choices)
    agency_id = serializers.IntegerField(required=False)
    trip_id = serializers.IntegerField(required=False)
    note = serializers.CharField(required=False)



# ==================================================
# APPLICATION: publications
# FICHIER: serializers.py
# ==================================================

# publications/serializers.py
from rest_framework import serializers

from .models import Publication, Notification, SupportTicket, SupportMessage


class PublicationSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    type_display = serializers.CharField(source='get_publication_type_display', read_only=True)
    audience_display = serializers.CharField(source='get_audience_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    absolute_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Publication
        fields = [
            'id', 'title', 'content', 'excerpt', 'publication_type', 'type_display',
            'audience', 'audience_display', 'status', 'status_display', 'target_agencies',
            'target_users', 'is_active', 'is_featured', 'is_pinned', 'start_date',
            'end_date', 'priority', 'image', 'attachment', 'action_url', 'action_text',
            'view_count', 'click_count', 'share_count', 'author', 'author_name',
            'meta_title', 'meta_description', 'slug', 'absolute_url', 'created', 'updated'
        ]
        read_only_fields = ['slug', 'view_count', 'click_count', 'share_count']


class PublicationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publication
        fields = [
            'title', 'content', 'excerpt', 'publication_type', 'audience',
            'target_agencies', 'target_users', 'is_featured', 'is_pinned',
            'start_date', 'end_date', 'priority', 'image', 'attachment',
            'action_url', 'action_text', 'meta_title', 'meta_description'
        ]
    
    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_id', 'user', 'user_name', 'title', 'message',
            'notification_type', 'type_display', 'status', 'status_display',
            'channel', 'channel_display', 'related_publication', 'related_reservation',
            'related_parcel', 'related_trip', 'related_support', 'action_url',
            'action_label', 'icon', 'image', 'sent_at', 'read_at', 'dismissed_at',
            'should_send_email', 'should_send_sms', 'should_send_push', 'email_sent',
            'sms_sent', 'push_sent', 'created', 'updated'
        ]
        read_only_fields = ['notification_id']


class SupportTicketSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    
    class Meta:
        model = SupportTicket
        fields = [
            'id', 'ticket_id', 'user', 'user_name', 'category', 'category_display',
            'status', 'status_display', 'priority', 'priority_display', 'subject',
            'description', 'attachment', 'assigned_to', 'assigned_to_name', 'agency',
            'agency_name', 'response_time', 'resolution_time', 'satisfaction_rating',
            'satisfaction_comment', 'first_response_at', 'resolved_at', 'closed_at',
            'related_reservation', 'related_parcel', 'related_trip', 'created', 'updated'
        ]
        read_only_fields = ['ticket_id']


class SupportMessageSerializer(serializers.ModelSerializer):
    message_type_display = serializers.CharField(source='get_message_type_display', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    
    class Meta:
        model = SupportMessage
        fields = [
            'id', 'ticket', 'user', 'user_name', 'message', 'message_type',
            'message_type_display', 'is_system', 'is_internal', 'is_first_response',
            'attachment', 'read_by_customer', 'read_by_agent', 'created', 'updated'
        ]



# ==================================================
# APPLICATION: parameter
# FICHIER: serializers.py
# ==================================================

# parameter/serializers.py
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from .models import CompanyConfig, SystemParameter


class CompanyConfigSerializer(serializers.ModelSerializer):
    full_address = serializers.CharField(read_only=True)
    primary_contact = serializers.CharField(read_only=True)
    social_links = serializers.DictField(read_only=True)
    business_hours = serializers.CharField(read_only=True)
    is_online_payment_available = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CompanyConfig
        fields = [
            'id', 'name', 'legal_name', 'slogan', 'logo', 'logo_light', 'logo_dark',
            'favicon', 'phone', 'phone_secondary', 'email', 'email_support', 'email_sales',
            'address', 'city', 'country', 'postal_code', 'website', 'facebook', 'twitter',
            'linkedin', 'instagram', 'whatsapp', 'rc_number', 'nif', 'nis', 'ai_number',
            'currency', 'timezone', 'language', 'max_seats_per_booking', 'booking_expiry_minutes',
            'allow_online_payment', 'max_parcel_weight', 'parcel_insurance_required',
            'maintenance_mode', 'enable_sms_notifications', 'enable_email_notifications',
            'meta_title', 'meta_description', 'keywords', 'full_address', 'primary_contact',
            'social_links', 'business_hours', 'is_online_payment_available', 'created', 'updated'
        ]
        read_only_fields = ['id', 'created', 'updated']


class CompanyConfigUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyConfig
        fields = [
            'name', 'legal_name', 'slogan', 'logo', 'logo_light', 'logo_dark', 'favicon',
            'phone', 'phone_secondary', 'email', 'email_support', 'email_sales',
            'address', 'city', 'country', 'postal_code', 'website', 'facebook', 'twitter',
            'linkedin', 'instagram', 'whatsapp', 'rc_number', 'nif', 'nis', 'ai_number',
            'currency', 'timezone', 'language', 'max_seats_per_booking', 'booking_expiry_minutes',
            'allow_online_payment', 'max_parcel_weight', 'parcel_insurance_required',
            'maintenance_mode', 'enable_sms_notifications', 'enable_email_notifications',
            'meta_title', 'meta_description', 'keywords'
        ]


class SystemParameterSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    data_type_display = serializers.CharField(source='get_data_type_display', read_only=True)
    typed_value = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemParameter
        fields = [
            'id', 'key', 'value', 'category', 'category_display', 'description',
            'data_type', 'data_type_display', 'is_public', 'typed_value',
            'created', 'updated'
        ]
        read_only_fields = ['id', 'created', 'updated']
    
    def get_typed_value(self, obj):
        return obj.get_typed_value()


class SystemParameterCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemParameter
        fields = ['key', 'value', 'category', 'description', 'data_type', 'is_public']
    
    def validate_key(self, value):
        if SystemParameter.objects.filter(key=value).exists():
            raise serializers.ValidationError(_("Cette clé existe déjà"))
        return value


class PublicCompanyInfoSerializer(serializers.Serializer):
    name = serializers.CharField()
    slogan = serializers.CharField(allow_null=True)
    logo = serializers.URLField(allow_null=True)
    phone = serializers.CharField()
    email = serializers.EmailField()
    address = serializers.CharField()
    social_links = serializers.DictField()
    business_hours = serializers.CharField()


class BusinessRulesSerializer(serializers.Serializer):
    max_seats_per_booking = serializers.IntegerField()
    booking_expiry_minutes = serializers.IntegerField()
    allow_online_payment = serializers.BooleanField()
    max_parcel_weight = serializers.FloatField()
    parcel_insurance_required = serializers.BooleanField()


class SystemSettingsSerializer(serializers.Serializer):
    maintenance_mode = serializers.BooleanField()
    enable_sms_notifications = serializers.BooleanField()
    enable_email_notifications = serializers.BooleanField()
    currency = serializers.CharField()
    timezone = serializers.CharField()
    language = serializers.CharField()



# ==================================================
# APPLICATION: core
# FICHIER: serializers.py
# ==================================================




