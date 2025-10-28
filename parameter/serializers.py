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