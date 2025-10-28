# parcel/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'parcels', views.ParcelViewSet, basename='parcel')
router.register(r'tracking-events', views.TrackingEventViewSet, basename='tracking-event')

urlpatterns = [
    path('', include(router.urls)),
]