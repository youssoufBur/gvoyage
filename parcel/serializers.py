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