# transport/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'routes', views.RouteViewSet, basename='route')
router.register(r'schedules', views.ScheduleViewSet, basename='schedule')
router.register(r'vehicles', views.VehicleViewSet, basename='vehicle')
router.register(r'legs', views.LegViewSet, basename='leg')
router.register(r'leg-schedules', views.LegScheduleViewSet, basename='leg-schedule')  # 🆕 ajouté
router.register(r'trips', views.TripViewSet, basename='trip')
router.register(r'trip-passengers', views.TripPassengerViewSet, basename='trip-passenger')
router.register(r'trip-events', views.TripEventViewSet, basename='trip-event')

urlpatterns = [
    path('', include(router.urls)),
]
