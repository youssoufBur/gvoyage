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