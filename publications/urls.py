# publications/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'publications', views.PublicationViewSet, basename='publication')
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'support-tickets', views.SupportTicketViewSet, basename='support-ticket')
router.register(r'support-messages', views.SupportMessageViewSet, basename='support-message')

urlpatterns = [
    path('', include(router.urls)),
]