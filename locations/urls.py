# locations/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'countries', views.CountryViewSet, basename='country')
router.register(r'cities', views.CityViewSet, basename='city')
router.register(r'agencies', views.AgencyViewSet, basename='agency')

urlpatterns = [
    path('', include(router.urls)),
]