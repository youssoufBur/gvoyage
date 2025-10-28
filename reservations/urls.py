# reservations/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'reservations', views.ReservationViewSet, basename='reservation')
router.register(r'tickets', views.TicketViewSet, basename='ticket')
router.register(r'payments', views.PaymentViewSet, basename='payment')

urlpatterns = [
    path('', include(router.urls)),
]