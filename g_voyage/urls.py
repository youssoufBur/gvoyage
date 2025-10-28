# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from django.views.generic import RedirectView
from rest_framework_simplejwt import views as jwt_views
urlpatterns = [
    # Redirection de la racine vers Swagger
    path('', RedirectView.as_view(url='/api/docs/', permanent=False)),
    
    # Administration Django
    path('admin/', admin.site.urls),
    
    # API Routes - Toutes les applications
    #path('api/', include('core.urls')),           # Modèles de base
    path('api/', include('users.urls')),          # Gestion des utilisateurs
    path('api/', include('locations.urls')),      # Pays, villes, agences
    path('api/', include('parameter.urls')),      # Configuration entreprise
    path('api/', include('transport.urls')),      # Routes, véhicules, voyages
    path('api/', include('reservations.urls')),   # Réservations, billets, paiements
    path('api/', include('parcel.urls')),         # Colis et suivi
    path('api/', include('publications.urls')),   # Publications, notifications, support
    
    # Documentation API Swagger/OpenAPI (racine de la documentation)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # Authentification
    path('api/auth/', include('rest_framework.urls')),     

# ... dans vos urlpatterns ...
    path('api/token/', jwt_views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', jwt_views.TokenRefreshView.as_view(), name='token_refresh'),
  
]

# Servir les fichiers média et statiques en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)