"""
Django settings for g_voyage project
"""

import os
from pathlib import Path
from datetime import timedelta

# ---------------------------------------------------------------------
# 1. BASE_DIR
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# 2. Paramètres de base
# ---------------------------------------------------------------------
SECRET_KEY = 'django-insecure-xn(tl$t9@x5tfz_b^ee^zknirml7)#@j+wh!5rs80nv0%9rt=='
DEBUG = True
# settings.py

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '.mondomaine.com',
    'gvoyage.pythonanywhere.com',
    'localhost:4200',   # ✅ Angular (dev)
    '127.0.0.1:4200',   # ✅ Angular (dev)
]


# ---------------------------------------------------------------------
# 3. Base de données
# ---------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / "db.sqlite3",
    }
}

# PostgreSQL (décommenter si nécessaire)
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'travel',
#         'USER': 'sana',
#         'PASSWORD': 'p@Ssw0rd',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

# ---------------------------------------------------------------------
# 4. Email
# ---------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'cyber.dev.226@gmail.com'
EMAIL_HOST_PASSWORD = 'monmotdepassegmail'
DEFAULT_FROM_EMAIL = 'cyber.dev.226@gmail.com'
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ---------------------------------------------------------------------
# 5. Static et Media
# ---------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
# settings.py
AUTHENTICATION_BACKENDS = [
    'users.backends.PhoneBackend',  # Backend personnalisé pour le téléphone
    'django.contrib.auth.backends.ModelBackend',  # Backend par défaut
]
# ---------------------------------------------------------------------
# 6. Applications installées
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',

    # Applications tierces
    'drf_spectacular',
    'django_countries',
    'phonenumber_field',
    'widget_tweaks',
    'corsheaders',
    'django_feather',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',

    # Applications internes
    'core',
    'users',
    'locations',
    'parameter', 
    'transport',
    'reservations',
    'parcel',
    'publications',
]

# ---------------------------------------------------------------------
# 7. Middleware
# ---------------------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'g_voyage.urls'
WSGI_APPLICATION = 'g_voyage.wsgi.application'

# ---------------------------------------------------------------------
# 8. Templates
# ---------------------------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

# ---------------------------------------------------------------------
# 9. Internationalisation
# ---------------------------------------------------------------------
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Ouagadougou'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------
# 10. Sécurité
# ---------------------------------------------------------------------
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# ---------------------------------------------------------------------
# 11. Authentification
# ---------------------------------------------------------------------
AUTH_USER_MODEL = 'users.User'
LOGIN_URL = '/connexion/'
LOGIN_REDIRECT_URL = '/home/'
LOGOUT_REDIRECT_URL = '/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------
# 12. Django REST Framework
# ---------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

# ---------------------------------------------------------------------
# 13. CORS Settings
# ---------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = DEBUG

# ---------------------------------------------------------------------
# 14. Logging
# ---------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'debug.log',
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file', 'mail_admins'],
            'level': 'INFO' if DEBUG else 'WARNING',
            'propagate': False,
        },
        'g_voyage': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# ---------------------------------------------------------------------
# 15. Stripe
# ---------------------------------------------------------------------
STRIPE_SECRET_KEY = 'sk_test_51MvV6oKp8nJ7Rx9...'
STRIPE_PUBLIC_KEY = 'pk_test_51MvV6oKp8nJ7Rx9...'

# ---------------------------------------------------------------------
# 16. Paramètres spécifiques à l'application
# ---------------------------------------------------------------------
PHONENUMBER_DB_FORMAT = 'INTERNATIONAL'
PHONENUMBER_DEFAULT_REGION = 'BF'

# ---------------------------------------------------------------------
# 17. Sécurité Production
# ---------------------------------------------------------------------
if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    
    LOGGING['loggers']['django']['level'] = 'WARNING'
    LOGGING['loggers']['g_voyage']['level'] = 'INFO'

# ---------------------------------------------------------------------
# 18. DRF Spectacular Settings (OpenAPI)
# ---------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    'TITLE': 'G-Travel API',
    'DESCRIPTION': """
    API Complete de Gestion de Transport - G-Travel
    
    Description:
    Plateforme digitale de gestion de transport unifiant reservations de voyages et envoi de colis.
    Systeme hybride supportant a la fois les canaux digitaux et physiques.
    
    Fonctionnalites Principales:
    - Gestion des agences et routes
    - Reservations de billets en ligne
    - Suivi de colis en temps reel
    - Paiements securises
    - QR Codes pour embarquement
    - Gestion multi-roles (Client, Chauffeur, Caissier, Admin)
    
    Authentification:
    - JWT Token Based Authentication
    - Roles et permissions granulaires
    - Support mobile et web
    
    Developpeur:
    SANA Issouf (cyberdev)
    Email: cyber.dev.226@gmail.com
    Telephone: +226 66 60 55 72
    WhatsApp: +226 60 95 58 60
    
    Architecture:
    - Django REST Framework
    - PostgreSQL
    - JWT Authentication
    - QR Code Generation
    """,
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {
        'name': 'SANA Issouf (cyberdev)',
        'email': 'cyber.dev.226@gmail.com',
        'url': 'https://github.com/youssoufBur',
    },
    'LICENSE': {
        'name': 'Proprietary',
        'url': '',
    },
    'TAGS': [
        {
            'name': 'Authentication',
            'description': 'Endpoints pour la gestion des utilisateurs et authentification'
        },
        {
            'name': 'Location',
            'description': 'Gestion des pays, villes et agences'
        },
        {
            'name': 'Transport',
            'description': 'Routes, vehicules, horaires et voyages'
        },
        {
            'name': 'Reservation',
            'description': 'Reservations, billets et paiements'
        },
        {
            'name': 'Parcel',
            'description': 'Envoi et suivi de colis'
        },
        {
            'name': 'User Management',
            'description': 'Gestion des profils utilisateurs'
        },
        {
            'name': 'Publication',
            'description': 'Publications, notifications et support'
        },
    ],
    'COMPONENTS': {
        'SECURITY_SCHEMES': {
            'JWT': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            },
            'Token': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'Authorization',
                'description': 'Token-based authentication'
            }
        }
    },
    'SECURITY': [{'JWT': []}],
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
        'filter': True,
        'docExpansion': 'none',
        'tagsSorter': 'alpha',
        'operationsSorter': 'alpha',
        'defaultModelsExpandDepth': 1,
        'defaultModelExpandDepth': 1,
    },
    'REDOC_UI_SETTINGS': {
        'hideDownloadButton': False,
        'expandResponses': '200,201',
        'pathInMiddlePanel': True,
    },
    'ENUM_NAME_OVERRIDES': {
        'UserRole': 'users.models.User.ROLE_CHOICES',
        'Gender': 'users.models.User.GENDER_CHOICES',
    },
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
    ],
}

# ---------------------------------------------------------------------
# 19. Paramètres personnalisés
# ---------------------------------------------------------------------
G_TRAVEL_CONFIG = {
    'MAX_SEATS_PER_BOOKING': 10,
    'BOOKING_EXPIRY_MINUTES': 30,
    'MAX_PARCEL_WEIGHT': 50.0,
    'DEFAULT_CURRENCY': 'FCFA',
    'SUPPORT_PHONE': '+226 66 60 55 72',
    'SUPPORT_EMAIL': 'cyber.dev.226@gmail.com',
}

# ---------------------------------------------------------------------
# 20. Cache
# ---------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Cache Redis pour la production:
# CACHES = {
#     'default': {
#         'BACKEND': 'django_redis.cache.RedisCache',
#         'LOCATION': 'redis://127.0.0.1:6379/1',
#         'OPTIONS': {
#             'CLIENT_CLASS': 'django_redis.client.DefaultClient',
#         }
#     }
# }