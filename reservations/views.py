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