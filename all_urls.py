# ==================================================
# FICHIER: all_urls.py
# DESCRIPTION: Tous les fichiers urls des applications Django
# GÉNÉRÉ LE: Tue Oct 28 14:01:53 UTC 2025
# ==================================================


# ==================================================
# APPLICATION: users
# FICHIER: urls.py
# ==================================================

# users/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/password-change/', views.PasswordChangeView.as_view(), name='password-change'),
]



# ==================================================
# APPLICATION: locations
# FICHIER: urls.py
# ==================================================

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



# ==================================================
# APPLICATION: transport
# FICHIER: urls.py
# ==================================================

# transport/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'routes', views.RouteViewSet, basename='route')
router.register(r'schedules', views.ScheduleViewSet, basename='schedule')
router.register(r'vehicles', views.VehicleViewSet, basename='vehicle')
router.register(r'trips', views.TripViewSet, basename='trip')
router.register(r'trip-passengers', views.TripPassengerViewSet, basename='trip-passenger')
router.register(r'trip-events', views.TripEventViewSet, basename='trip-event')

urlpatterns = [
    path('', include(router.urls)),
]



# ==================================================
# APPLICATION: reservations
# FICHIER: urls.py
# ==================================================

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



# ==================================================
# APPLICATION: parcel
# FICHIER: urls.py
# ==================================================

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



# ==================================================
# APPLICATION: publications
# FICHIER: urls.py
# ==================================================

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



# ==================================================
# APPLICATION: parameter
# FICHIER: urls.py
# ==================================================

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



# ==================================================
# APPLICATION: core
# FICHIER: urls.py
# ==================================================




