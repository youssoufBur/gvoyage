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