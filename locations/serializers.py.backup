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