# parameter/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'company-config', views.CompanyConfigViewSet, basename='company-config')
router.register(r'system-parameters', views.SystemParameterViewSet, basename='system-parameter')

urlpatterns = [
    path('', include(router.urls)),
    path('validate-parameter/', views.ParameterValidationAPIView.as_view(), name='validate-parameter'),
    path('system-status/', views.SystemStatusAPIView.as_view(), name='system-status'),
]