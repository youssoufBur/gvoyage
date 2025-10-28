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