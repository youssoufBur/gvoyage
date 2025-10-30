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


# users/serializers.py - UserCreateSerializer
class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    
    class Meta:
        model = User
        fields = [
            'phone', 'full_name', 'email', 'role', 'agency', 
            'password', 'gender', 'date_of_birth', 'address', 'city'
        ]
        extra_kwargs = {
            'role': {'required': False}  # Le rôle peut être automatique
        }
    
    def validate(self, attrs):
        # Pour les créations non authentifiées, forcer le rôle client
        request = self.context.get('request')
        if request and not request.user.is_authenticated:
            attrs['role'] = 'client'
        
        # Valider que le numéro de téléphone est unique
        phone = attrs.get('phone')
        if phone and User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError({
                'phone': _('Un utilisateur avec ce numéro de téléphone existe déjà.')
            })
        
        return attrs
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        
        # S'assurer que le rôle est client pour les inscriptions publiques
        request = self.context.get('request')
        if request and not request.user.is_authenticated:
            validated_data['role'] = 'client'
            validated_data['is_verified'] = True  # Les clients sont vérifiés automatiquement
        
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