# ==================================================
# FICHIER: all_models.py
# DESCRIPTION: Tous les fichiers models des applications Django
# GÉNÉRÉ LE: Fri Oct 24 22:51:15 UTC 2025
# ==================================================


# ==================================================
# APPLICATION: users
# FICHIER: models.py
# ==================================================

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from parcel.models import Parcel
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.cache import cache
import uuid
import secrets
import string
from core.models import TimeStampedModel
from reservations.models import Payment
from transport.models import TripEvent
from reservations.models import Payment, Ticket
from transport.models import Trip, TripEvent
from django.db.models import Count, Sum, Avg
from datetime import datetime, time
from datetime import datetime, time, timedelta  # ← AJOUT timedelta
from django.db.models import Sum


class UserManager(BaseUserManager):
    """Gestionnaire personnalisé pour le modèle User"""
    
    def generate_temporary_password(self, length=8):
        """Génère un mot de passe temporaire sécurisé de 8 caractères"""
        alphabet = string.ascii_letters + string.digits + "!@#$%"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError(_("Le numéro de téléphone est obligatoire"))

        phone = self.normalize_phone(phone)
        user = self.model(phone=phone, **extra_fields)
        
        # Générer un mot de passe temporaire pour les non-clients
        temporary_password = None
        if not user.is_client() and not password:
            temporary_password = self.generate_temporary_password()
            password = temporary_password
            
        user.set_password(password)
        user.temporary_password = temporary_password
        user.save(using=self._db)
        
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        return self.create_user(phone, password, **extra_fields)

    def normalize_phone(self, phone):
        if hasattr(phone, 'as_international'):
            return phone.as_international
        return str(phone)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """Modèle d'utilisateur personnalisé avec hiérarchie complète"""
    
        
    class Role(models.TextChoices):
        CLIENT = "client", _("Client")
        CHAUFFEUR = "chauffeur", _("Chauffeur")
        CAISSIER = "caissier", _("Caissier")
        LIVREUR = "livreur", _("Livreur")
        AGENT = "agent", _("Agent d'Agence")  # ← NOUVEAU RÔLE
        AGENCY_MANAGER = "agency_manager", _("Chef d'Agence")
        CENTRAL_MANAGER = "central_manager", _("Chef d'Agence Centrale")
        NATIONAL_MANAGER = "national_manager", _("Chef d'Agence Nationale")
        DG = "dg", _("Directeur Général")
        ADMIN = "admin", _("Administrateur")

    class Gender(models.TextChoices):
        MALE = "male", _("Homme")
        FEMALE = "female", _("Femme")
        OTHER = "other", _("Autre")
    
    class Status(models.TextChoices):
        ACTIVE = "active", _("Actif")
        INACTIVE = "inactive", _("Inactif")
        SUSPENDED = "suspended", _("Suspendu")
        PENDING = "pending", _("En attente")

    # Informations personnelles
    full_name = models.CharField(max_length=255, blank=True, verbose_name=_("Nom complet"))
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, null=True, verbose_name=_("Genre"))
    date_of_birth = models.DateField(blank=True, null=True, verbose_name=_("Date de naissance"))
    photo = models.ImageField(upload_to="users/photos/%Y/%m/", blank=True, null=True, verbose_name=_("Photo de profil"))
    national_id = models.CharField(max_length=50, blank=True, verbose_name=_("Numéro de pièce d'identité"))
    
    # Informations de contact
    phone = PhoneNumberField(unique=True, region=None, verbose_name=_("Numéro de téléphone principal"))
    phone_secondary = PhoneNumberField(blank=True, null=True, region=None, verbose_name=_("Numéro de téléphone secondaire"))
    email = models.EmailField(blank=True, null=True, verbose_name=_("Adresse email"))
    address = models.TextField(blank=True, verbose_name=_("Adresse personnelle"))
    city = models.CharField(max_length=100, blank=True, verbose_name=_("Ville"))
    
    # Informations professionnelles
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT, verbose_name=_("Rôle"))
    agency = models.ForeignKey("locations.Agency", on_delete=models.PROTECT, related_name="employees", null=True, blank=True, verbose_name=_("Agence"))
    employee_id = models.CharField(max_length=50, blank=True, verbose_name=_("Matricule employé"))
    hire_date = models.DateField(blank=True, null=True, verbose_name=_("Date d'embauche"))
    department = models.CharField(max_length=100, blank=True, verbose_name=_("Département"))
    
    # Statut et permissions
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name=_("Statut"))
    is_active = models.BooleanField(default=True, verbose_name=_("Compte activé"))
    is_staff = models.BooleanField(default=False, verbose_name=_("Accès administration"))
    is_superuser = models.BooleanField(default=False, verbose_name=_("Superutilisateur"))
    is_verified = models.BooleanField(default=False, verbose_name=_("Compte vérifié"))
    
    # Sécurité et activation
    activation_token = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Token d'activation"))
    activation_token_expires = models.DateTimeField(blank=True, null=True, verbose_name=_("Expiration du token"))
    last_login_ip = models.GenericIPAddressField(blank=True, null=True, verbose_name=_("Dernière IP de connexion"))
    login_count = models.PositiveIntegerField(default=0, verbose_name=_("Nombre de connexions"))
    
    # Métadonnées
    date_joined = models.DateTimeField(default=timezone.now, verbose_name=_("Date d'inscription"))
    last_updated = models.DateTimeField(auto_now=True, verbose_name=_("Dernière mise à jour"))
    last_password_change = models.DateTimeField(blank=True, null=True, verbose_name=_("Dernier changement de mot de passe"))

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        verbose_name = _("Utilisateur")
        verbose_name_plural = _("Utilisateurs")
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.full_name or str(self.phone)} ({self.get_role_display()})"

    # =========================================================================
    # MÉTHODES DE RÔLE AVEC HIÉRARCHIE
    # =========================================================================

    def is_client(self):
        return self.role == self.Role.CLIENT

    def is_chauffeur(self):
        return self.role == self.Role.CHAUFFEUR

    def is_caissier(self):
        return self.role == self.Role.CAISSIER

    def is_livreur(self):
        return self.role == self.Role.LIVREUR

    def is_agency_manager(self):
        return self.role == self.Role.AGENCY_MANAGER

    def is_central_manager(self):
        return self.role == self.Role.CENTRAL_MANAGER

    def is_national_manager(self):
        return self.role == self.Role.NATIONAL_MANAGER

    def is_dg(self):
        return self.role == self.Role.DG

    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser
    
    def is_employee(self):
        return self.role in [
            self.Role.CHAUFFEUR, self.Role.CAISSIER, self.Role.LIVREUR,
            self.Role.AGENCY_MANAGER, self.Role.CENTRAL_MANAGER, 
            self.Role.NATIONAL_MANAGER, self.Role.DG, self.Role.ADMIN
        ]

    def is_manager(self):
        return self.role in [
            self.Role.AGENCY_MANAGER, self.Role.CENTRAL_MANAGER,
            self.Role.NATIONAL_MANAGER, self.Role.DG, self.Role.ADMIN
        ]

    def get_hierarchy_level(self):
        """Retourne le niveau hiérarchique de l'utilisateur"""
        hierarchy = {
            self.Role.CLIENT: 0,
            self.Role.CHAUFFEUR: 1,
            self.Role.CAISSIER: 1,
            self.Role.LIVREUR: 1,
            self.Role.AGENCY_MANAGER: 2,
            self.Role.CENTRAL_MANAGER: 3,
            self.Role.NATIONAL_MANAGER: 4,
            self.Role.DG: 5,
            self.Role.ADMIN: 6
        }
        return hierarchy.get(self.role, 0)

    # =========================================================================
    # MÉTHODES DE GESTION DES PERMISSIONS
    # =========================================================================

    def can_manage_agency(self, agency):
        """Vérifie si l'utilisateur peut gérer une agence spécifique"""
        if self.is_dg() or self.is_admin():
            return True
        elif self.is_national_manager():
            return agency.country in self.get_managed_countries()
        elif self.is_central_manager():
            return agency in self.get_managed_agencies()
        elif self.is_agency_manager():
            return self.agency == agency
        return False

    def get_managed_agencies(self):
        """Retourne les agences que l'utilisateur peut gérer"""
        from locations.models import Agency
        
        if self.is_dg() or self.is_admin():
            return Agency.objects.all()
        elif self.is_national_manager():
            # Retourne toutes les agences des pays gérés
            managed_countries = self.get_managed_countries()
            return Agency.objects.filter(city__country__in=managed_countries)
        elif self.is_central_manager():
            # Retourne les agences de l'agence centrale et ses enfants
            return Agency.objects.filter(
                models.Q(id=self.agency.id) | 
                models.Q(parent_agency=self.agency)
            )
        elif self.is_agency_manager():
            return Agency.objects.filter(id=self.agency.id)
        else:
            return Agency.objects.none()

    def get_managed_countries(self):
        """Retourne les pays que l'utilisateur peut gérer"""
        from locations.models import Country
        
        if self.is_dg() or self.is_admin():
            return Country.objects.all()
        elif self.is_national_manager():
            # À implémenter selon la logique métier
            return Country.objects.filter(managers=self)
        return Country.objects.none()

    # =========================================================================
    # MÉTHODES MÉTIER ENRICHIES
    # =========================================================================

    def get_dashboard_statistics(self, start_date=None, end_date=None):
        """Retourne les statistiques du dashboard selon le rôle"""
        if not start_date:
            start_date = timezone.now().date() - timezone.timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()

        stats = {
            'period': {'start': start_date, 'end': end_date},
            'user_role': self.role,
            'user_agency': self.agency.name if self.agency else None,
        }

        # Filtre commun pour la période
        date_filter = {'created__date__range': [start_date, end_date]}
        agency_filter = self._get_agency_filter()

        if self.is_client():
            stats.update(self._get_client_stats(date_filter))
        elif self.is_chauffeur():
            stats.update(self._get_chauffeur_stats(date_filter))
        elif self.is_caissier():
            stats.update(self._get_caissier_stats(date_filter))
        elif self.is_livreur():
            stats.update(self._get_livreur_stats(date_filter))
        elif self.is_manager():
            stats.update(self._get_manager_stats(date_filter, agency_filter))

        return stats

    def _get_agency_filter(self):
        """Retourne le filtre d'agence selon les permissions"""
        if self.is_dg() or self.is_admin():
            return {}
        elif self.is_national_manager():
            managed_countries = self.get_managed_countries()
            return {'agency__city__country__in': managed_countries}
        elif self.is_central_manager():
            managed_agencies = self.get_managed_agencies()
            return {'agency__in': managed_agencies}
        elif self.is_agency_manager():
            return {'agency': self.agency}
        else:
            return {'agency': self.agency} if self.agency else {}

    def _get_client_stats(self, date_filter):
        """Statistiques pour les clients"""
        
        
        tickets = Ticket.objects.filter(client=self, **date_filter)
        parcels = Parcel.objects.filter(sender=self, **date_filter)
        
        return {
            'total_tickets': tickets.count(),
            'active_tickets': tickets.filter(status__in=['confirmed', 'pending']).count(),
            'total_spent': tickets.aggregate(total=Sum('total_price'))['total'] or 0,
            'total_parcels': parcels.count(),
            'pending_parcels': parcels.filter(status='pending').count(),
            'delivered_parcels': parcels.filter(status='delivered').count(),
        }

    def _get_chauffeur_stats(self, date_filter):
        """Statistiques pour les chauffeurs"""
      
        
        trips = Trip.objects.filter(driver=self, **date_filter)
        
        return {
            'total_trips': trips.count(),
            'completed_trips': trips.filter(status='completed').count(),
            'in_progress_trips': trips.filter(status__in=['boarding', 'in_progress']).count(),
            'total_passengers': trips.aggregate(total=Count('passengers'))['total'] or 0,
            'on_time_rate': self._calculate_on_time_rate(trips),
        }

    def _get_caissier_stats(self, date_filter):
        """Statistiques pour les caissiers"""
        
        payments = Payment.objects.filter(created_by=self, **date_filter)
        today_payments = payments.filter(created__date=timezone.now().date())
        
        return {
            'total_payments': payments.count(),
            'successful_payments': payments.filter(status='completed').count(),
            'today_payments': today_payments.count(),
            'total_revenue': payments.aggregate(total=Sum('amount'))['total'] or 0,
            'today_revenue': today_payments.aggregate(total=Sum('amount'))['total'] or 0,
            'cash_revenue': payments.filter(payment_method='cash').aggregate(total=Sum('amount'))['total'] or 0,
            'mobile_revenue': payments.filter(payment_method='mobile_money').aggregate(total=Sum('amount'))['total'] or 0,
        }

    # Dans users/models.py - Correction de la méthode _get_livreur_stats

    def _get_livreur_stats(self, date_filter):
        """Statistiques pour les livreurs"""
        try:
            # Utiliser apps.get_model pour éviter les imports circulaires
            Parcel = apps.get_model('parcel', 'Parcel')
            
            parcels = Parcel.objects.filter(
                last_handled_by=self,
                **date_filter
            )
            
            deliveries = parcels.filter(
                status__in=[Parcel.Status.OUT_FOR_DELIVERY, Parcel.Status.DELIVERED]
            )
            
            return {
                'total_deliveries': deliveries.count(),
                'completed_deliveries': deliveries.filter(status=Parcel.Status.DELIVERED).count(),
                'pending_deliveries': deliveries.filter(status=Parcel.Status.OUT_FOR_DELIVERY).count(),
                'average_delivery_time': self._calculate_avg_delivery_time(deliveries),
                'customer_rating': self._calculate_avg_rating(deliveries),
            }
        except (LookupError, ImportError):
            # Retourner des valeurs par défaut si le modèle n'est pas disponible
            return {
                'total_deliveries': 0,
                'completed_deliveries': 0,
                'pending_deliveries': 0,
                'average_delivery_time': 0,
                'customer_rating': 0,
            }

    def _calculate_avg_delivery_time(self, deliveries):
        """Calcule le temps moyen de livraison"""
        try:
            completed_deliveries = deliveries.filter(status=Parcel.Status.DELIVERED)
            
            if not completed_deliveries:
                return 0
            
            total_seconds = 0
            count = 0
            
            for parcel in completed_deliveries:
                if parcel.actual_delivery and parcel.created:
                    delivery_time = parcel.actual_delivery - parcel.created
                    total_seconds += delivery_time.total_seconds()
                    count += 1
            
            return total_seconds / count / 3600 if count > 0 else 0
        except (LookupError, ImportError):
            return 0

    def _calculate_avg_rating(self, deliveries):
        """Calcule la note moyenne des clients"""
        # À implémenter selon votre logique métier
        # Pour l'instant, retourner une valeur par défaut
        return 4.5

    def _get_manager_stats(self, date_filter, agency_filter):
        """Statistiques pour les managers"""
        
        
        today_start = datetime.combine(timezone.now().date(), time.min)
        today_end = datetime.combine(timezone.now().date(), time.max)
        today_filter = {'created__range': [today_start, today_end]}
        
        # Statistiques financières
        payments = Payment.objects.filter(**agency_filter, **date_filter)
        today_payments = Payment.objects.filter(**agency_filter, **today_filter)
        
        # Statistiques voyages
        trips = Trip.objects.filter(**agency_filter, **date_filter)
        today_trips = Trip.objects.filter(**agency_filter, **today_filter)
        
        # Statistiques incidents
        incidents = TripEvent.objects.filter(
            **agency_filter, 
            event_type__in=['incident', 'accident'],
            **date_filter
        )
        
        # Statistiques colis
        parcels = Parcel.objects.filter(**agency_filter, **date_filter)
        
        return {
            'financial': {
                'total_revenue': payments.aggregate(total=Sum('amount'))['total'] or 0,
                'today_revenue': today_payments.aggregate(total=Sum('amount'))['total'] or 0,
                'cash_revenue': payments.filter(payment_method='cash').aggregate(total=Sum('amount'))['total'] or 0,
                'mobile_revenue': payments.filter(payment_method='mobile_money').aggregate(total=Sum('amount'))['total'] or 0,
                'total_transactions': payments.count(),
                'success_rate': (payments.filter(status='completed').count() / payments.count() * 100) if payments.count() > 0 else 0,
            },
            'operations': {
                'total_trips': trips.count(),
                'today_trips': today_trips.count(),
                'completed_trips': trips.filter(status='completed').count(),
                'active_trips': trips.filter(status__in=['boarding', 'in_progress']).count(),
                'total_passengers': Ticket.objects.filter(**agency_filter, **date_filter).count(),
                'today_passengers': Ticket.objects.filter(**agency_filter, **today_filter).count(),
            },
            'incidents': {
                'total_incidents': incidents.count(),
                'serious_incidents': incidents.filter(event_type='accident').count(),
                'today_incidents': incidents.filter(timestamp__date=timezone.now().date()).count(),
                'incident_rate': (incidents.count() / trips.count() * 100) if trips.count() > 0 else 0,
            },
            'parcels': {
                'total_parcels': parcels.count(),
                'delivered_parcels': parcels.filter(status='delivered').count(),
                'in_transit_parcels': parcels.filter(status='in_transit').count(),
                'pending_parcels': parcels.filter(status='pending').count(),
                'delivery_success_rate': (parcels.filter(status='delivered').count() / parcels.count() * 100) if parcels.count() > 0 else 0,
            }
        }

    def _calculate_on_time_rate(self, trips):
        """Calcule le taux de ponctualité d'un chauffeur"""
        completed_trips = trips.filter(status='completed')
        if not completed_trips:
            return 100
        
        on_time_count = 0
        for trip in completed_trips:
            estimated_arrival = trip.get_estimated_arrival()
            actual_arrival = trip.events.filter(event_type='arrival').first()
            if actual_arrival and (actual_arrival.timestamp - estimated_arrival).total_seconds() <= 900:  # 15 minutes de tolérance
                on_time_count += 1
        
        return (on_time_count / completed_trips.count()) * 100

    # =========================================================================
    # MÉTHODES DE RAPPORT AVANCÉES
    # =========================================================================

    def generate_financial_report(self, start_date, end_date, report_type='daily'):
        """Génère un rapport financier détaillé"""
        agency_filter = self._get_agency_filter()
        payments = Payment.objects.filter(
            **agency_filter,
            created__date__range=[start_date, end_date],
            status='completed'
        )
        
        report = {
            'period': {'start': start_date, 'end': end_date},
            'report_type': report_type,
            'summary': {
                'total_revenue': payments.aggregate(total=Sum('amount'))['total'] or 0,
                'total_transactions': payments.count(),
                'average_transaction': payments.aggregate(avg=Avg('amount'))['avg'] or 0,
            },
            'breakdown': {
                'by_payment_method': dict(payments.values('payment_method').annotate(
                    total=Sum('amount'), count=Count('id')
                ).values_list('payment_method', 'total')),
                'by_agency': dict(payments.values('agency__name').annotate(
                    total=Sum('amount'), count=Count('id')
                ).values_list('agency__name', 'total')),
            }
        }
        
        return report

    def get_incident_analytics(self, start_date, end_date):
        """Retourne l'analytique des incidents"""
        agency_filter = self._get_agency_filter()
        incidents = TripEvent.objects.filter(
            **agency_filter,
            event_type__in=['incident', 'accident'],
            timestamp__date__range=[start_date, end_date]
        )
        
        return {
            'total_incidents': incidents.count(),
            'by_type': dict(incidents.values('event_type').annotate(count=Count('id')).values_list('event_type', 'count')),
            'by_severity': self._categorize_incidents(incidents),
            'trends': self._calculate_incident_trends(incidents, start_date, end_date),
        }

    # =========================================================================
    # MÉTHODES UTILITAIRES
    # =========================================================================

    def get_display_name(self):
        return self.full_name or f"Utilisateur #{self.id}"

    @property
    def agency_name(self):
        return self.agency.name if self.agency else "-"

    @property
    def needs_activation(self):
        return bool(self.activation_token)

    @property
    def can_login(self):
        return (self.is_active and 
                self.is_verified and 
                not self.needs_activation)

    def clean(self):
        super().clean()
        
        if self.is_employee() and not self.agency:
            raise ValidationError(_("Les {}s doivent être associés à une agence.").format(self.get_role_display()))
        
        if self.is_employee() and not self.email:
            raise ValidationError(_("Les {}s doivent avoir une adresse email.").format(self.get_role_display()))

    def save(self, *args, **kwargs):
        # Logique de sauvegarde existante
        is_new_user = not self.pk
        if is_new_user and self.is_employee() and not self.activation_token:
            self.activation_token = str(uuid.uuid4())
            self.activation_token_expires = timezone.now() + timezone.timedelta(hours=24)

        if is_new_user and self.is_employee() and not self.employee_id:
            self.employee_id = self._generate_employee_id()

        super().save(*args, **kwargs)
        
        # Envoi d'email d'activation
        if (is_new_user and self.is_employee() and self.activation_token and
            not getattr(self, '_activation_email_sent', False)):
            
            temporary_password = getattr(self, 'temporary_password', None)
            self._send_activation_email(temporary_password)
            self._activation_email_sent = True

    def _generate_employee_id(self):
        prefix = {
            self.Role.CHAUFFEUR: 'CH', self.Role.CAISSIER: 'CA', 
            self.Role.LIVREUR: 'LV', self.Role.AGENCY_MANAGER: 'AM',
            self.Role.CENTRAL_MANAGER: 'CM', self.Role.NATIONAL_MANAGER: 'NM',
            self.Role.DG: 'DG', self.Role.ADMIN: 'AD'
        }.get(self.role, 'EM')
        
        timestamp = timezone.now().strftime('%y%m%d')
        random_part = str(uuid.uuid4().int)[:6]
        return f"{prefix}{timestamp}{random_part}"
    
    def _send_activation_email(self, temporary_password=None):
        subject = _("Activation de votre compte employé")
        context = {
            'user': self,
            'activation_link': f"{settings.FRONTEND_URL}/activate/{self.activation_token}/",
            'temporary_password': temporary_password,
        }
        html_message = render_to_string('emails/employee_activation.html', context)
        plain_message = strip_tags(html_message)
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [self.email],
            html_message=html_message,
        )


    def _calculate_incident_trends(self, incidents, start_date, end_date):
        """Calcule les tendances des incidents"""
        if not incidents:
            return {'weekly_trend': 'stable', 'comparison_previous_period': 0}
        
        # Logique simplifiée
        total_incidents = incidents.count()
        
        # Calculer la période précédente pour comparaison
        period_days = (end_date - start_date).days
        previous_start = start_date - timedelta(days=period_days)
        previous_end = start_date - timedelta(days=1)
        
        previous_incidents = incidents.filter(
            timestamp__date__range=[previous_start, previous_end]
        ).count()
        
        if previous_incidents == 0:
            trend = 'stable'
            comparison = 0
        else:
            change = ((total_incidents - previous_incidents) / previous_incidents) * 100
            if change > 10:
                trend = 'increasing'
            elif change < -10:
                trend = 'decreasing'
            else:
                trend = 'stable'
            comparison = round(change, 2)
        
        return {
            'weekly_trend': trend,
            'comparison_previous_period': comparison
        }



# ==================================================
# APPLICATION: locations
# FICHIER: models.py
# ==================================================

from django.db import models
from django.utils.translation import gettext_lazy as _
from core.models import TimeStampedModel


class Country(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=3, unique=True, help_text="Code ISO-3166 alpha-2/3")

    class Meta:
        verbose_name = _("Pays")
        verbose_name_plural = _("Pays")

    def __str__(self):
        return f"{self.name} ({self.code})"


class City(TimeStampedModel):
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="cities")
    name = models.CharField(max_length=120)

    class Meta:
        unique_together = ("country", "name")
        indexes = [models.Index(fields=["country", "name"])]
        verbose_name = _("Ville")
        verbose_name_plural = _("Villes")

    def __str__(self):
        return f"{self.name}, {self.country.code}"


class Agency(TimeStampedModel):
    class Level(models.TextChoices):
        NATIONAL = "national", "Siège national"
        CENTRAL = "central", "Agence centrale (ville)"
        LOCAL = "local", "Agence de quartier"

    class Type(models.TextChoices):
        DEPARTURE = "departure", "Agence de départ"
        ARRIVAL = "arrival", "Agence d'arrivée"
        CARGO = "cargo", "Agence de colis"
        SALES = "sales", "Point de vente / Caisse"
        SERVICE = "service", "Service administratif"
        OTHER = "other", "Autre"

    name = models.CharField(max_length=120, verbose_name=_("Nom de l'agence"))
    code = models.CharField(max_length=10, unique=True, verbose_name=_("Code agence"))
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="agencies")

    level = models.CharField(max_length=20, choices=Level.choices, default=Level.LOCAL)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.SALES)

    parent_agency = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_agencies"
    )

    address = models.TextField(verbose_name=_("Adresse complète"))
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True, verbose_name=_("Agence active"))

    class Meta:
        verbose_name = _("Agence")
        verbose_name_plural = _("Agences")
        indexes = [
            models.Index(fields=['city', 'is_active']),
            models.Index(fields=['code']),
            models.Index(fields=['level']),
            models.Index(fields=['type']),
        ]
        ordering = ["city__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_level_display()} - {self.get_type_display()})"



# ==================================================
# APPLICATION: transport
# FICHIER: models.py
# ==================================================

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, Sum, Count

from core.models import TimeStampedModel

from django.utils.dateparse import parse_date

class Route(TimeStampedModel):
    """
    Modèle représentant une route entre deux villes avec plusieurs tronçons.
    
    Attributes:
        code (str): Code unique identifiant la route
        origin (City): Ville de départ de la route
        destination (City): Ville d'arrivée de la route  
        distance_km (Decimal): Distance totale en kilomètres
        agency (Agency): Agence propriétaire de la route
    """
    code = models.CharField(
        max_length=20, 
        unique=True,
        verbose_name=_("Code de la route")
    )
    origin = models.ForeignKey(
        "locations.City", 
        on_delete=models.PROTECT, 
        related_name="routes_origin",
        verbose_name=_("Ville de départ")
    )
    destination = models.ForeignKey(
        "locations.City", 
        on_delete=models.PROTECT, 
        related_name="routes_destination",
        verbose_name=_("Ville d'arrivée")
    )
    distance_km = models.DecimalField(
        max_digits=7, 
        decimal_places=2,
        verbose_name=_("Distance (km)")
    )
    agency = models.ForeignKey(
        "locations.Agency", 
        on_delete=models.PROTECT, 
        related_name="routes",
        verbose_name=_("Agence")
    )

    class Meta:
        verbose_name = _("Route")
        verbose_name_plural = _("Routes")

    def __str__(self):
        return f"{self.origin} → {self.destination}"

    def get_active_legs(self):
        """Retourne les tronçons actifs de la route triés par ordre"""
        return self.legs.all().order_by('order')
    
    def get_total_duration(self):
        """Calcule la durée totale de la route en minutes"""
        total = self.legs.aggregate(
            total_duration=Sum('duration_minutes')
        )['total_duration'] or 0
        return total
    
    def get_total_price(self):
        """Calcule le prix total de la route"""
        total = self.legs.aggregate(
            total_price=Sum('price')
        )['total_price'] or 0
        return total
    
    def get_available_schedules(self, date=None):
        """
        Retourne les horaires disponibles pour une date donnée
        
        Args:
            date (date, optional): Date pour filtrer les horaires. Par défaut aujourd'hui.
            
        Returns:
            QuerySet: Horaires disponibles pour la date
        """
    
        
        if not date:
            date = timezone.now().date()
        elif isinstance(date, str):
            date = parse_date(date)
        
        # Convertir la date en jour de la semaine
        day_mapping = {
            'monday': 'mon',
            'tuesday': 'tue', 
            'wednesday': 'wed',
            'thursday': 'thu',
            'friday': 'fri',
            'saturday': 'sat',
            'sunday': 'sun'
        }
        day_of_week = day_mapping[date.strftime('%A').lower()]
        
        schedules = Schedule.objects.filter(
            leg__route=self,
            is_active=True
        ).filter(
            Q(days_of_week__contains=day_of_week) | 
            Q(days_of_week='daily')
        ).select_related('leg', 'agency')
        
        return schedules

    def to_json(self):
        """Serialise la route en format JSON pour l'API"""
        return {
            'id': self.id,
            'code': self.code,
            'origin': {
                'id': self.origin.id,
                'name': self.origin.name,
            },
            'destination': {
                'id': self.destination.id,
                'name': self.destination.name,
            },
            'distance_km': float(self.distance_km),
            'agency': {
                'id': self.agency.id,
                'name': self.agency.name,
            },
            'total_duration': self.get_total_duration(),
            'total_price': float(self.get_total_price()),
            'legs': [leg.to_json() for leg in self.get_active_legs()],
            'created': self.created.isoformat() if self.created else None,
            'updated': self.updated.isoformat() if self.updated else None,
        }


class Leg(TimeStampedModel):
    """
    Modèle représentant un tronçon d'une route entre deux villes.
    
    Attributes:
        route (Route): Route parente du tronçon
        origin (City): Ville de départ du tronçon
        destination (City): Ville d'arrivée du tronçon
        order (int): Ordre du tronçon dans la route
        price (Decimal): Prix du tronçon en FCFA
        duration_minutes (int): Durée du trajet en minutes
    """
    route = models.ForeignKey(
        Route, 
        on_delete=models.CASCADE, 
        related_name="legs",
        verbose_name=_("Route")
    )
    origin = models.ForeignKey(
        "locations.City", 
        on_delete=models.PROTECT, 
        related_name="legs_origin",
        verbose_name=_("Départ")
    )
    destination = models.ForeignKey(
        "locations.City", 
        on_delete=models.PROTECT, 
        related_name="legs_destination",
        verbose_name=_("Arrivée")
    )
    order = models.PositiveIntegerField(verbose_name=_("Ordre"))
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name=_("Prix (FCFA)")
    )
    duration_minutes = models.PositiveIntegerField(
        default=60,
        verbose_name=_("Durée (minutes)")
    )
    
    class Meta:
        ordering = ["order"]
        unique_together = ("route", "origin", "destination")
        verbose_name = _("Tronçon")
        verbose_name_plural = _("Tronçons")

    def __str__(self):
        return f"{self.origin.name} → {self.destination.name} ({self.price} FCFA)"
    
    def get_available_schedules(self):
        """Retourne les horaires disponibles pour ce tronçon"""
        return Schedule.objects.filter(
            leg=self,
            is_active=True
        ).select_related('agency')
    
    def get_next_trips(self, from_datetime=None, limit=5):
        """
        Retourne les prochains voyages pour ce tronçon
        
        Args:
            from_datetime (datetime, optional): Date de référence. Par défaut maintenant.
            limit (int): Nombre maximum de voyages à retourner
            
        Returns:
            QuerySet: Prochains voyages
        """
        if not from_datetime:
            from_datetime = timezone.now()
        
        return Trip.objects.filter(
            schedule__leg=self,
            departure_dt__gte=from_datetime,
            status__in=[Trip.Status.PLANNED, Trip.Status.BOARDING]
        ).select_related('schedule', 'vehicle', 'driver')[:limit]
    
    def to_json(self):
        """Serialise le tronçon en format JSON pour l'API"""
        return {
            'id': self.id,
            'route_id': self.route_id,
            'origin': {
                'id': self.origin.id,
                'name': self.origin.name,
            },
            'destination': {
                'id': self.destination.id,
                'name': self.destination.name,
            },
            'order': self.order,
            'price': float(self.price),
            'duration_minutes': self.duration_minutes,
            'created': self.created.isoformat() if self.created else None,
            'updated': self.updated.isoformat() if self.updated else None,
        }


class Schedule(TimeStampedModel):
    """
    Modèle représentant un horaire de départ pour un tronçon.
    
    Attributes:
        leg (Leg): Tronçon associé à l'horaire
        agency (Agency): Agence responsable de l'horaire
        departure_time (Time): Heure de départ
        days_of_week (str): Jours de circulation (ex: 'mon,tue,wed' ou 'daily')
        is_active (bool): Indique si l'horaire est actif
    """
    leg = models.ForeignKey(
        Leg, 
        on_delete=models.PROTECT, 
        related_name="schedules",
        verbose_name=_("Tronçon")
    )
    agency = models.ForeignKey(
        "locations.Agency", 
        on_delete=models.PROTECT, 
        related_name="schedules",
        verbose_name=_("Agence")
    )
    departure_time = models.TimeField(verbose_name=_("Heure de départ"))
    days_of_week = models.CharField(
        max_length=50, 
        help_text=_("Ex: 'lun,mar,mer' ou 'quotidien'"),
        verbose_name=_("Jours de circulation")
    )
    is_active = models.BooleanField(
        default=True, 
        verbose_name=_("Actif")
    )
    
    class Meta:
        verbose_name = _("Horaire")
        verbose_name_plural = _("Horaires")

    def __str__(self):
        return f"{self.leg.origin}→{self.leg.destination} à {self.departure_time}"
    
    def get_next_trips(self, date=None, limit=10):
        """
        Retourne les prochains voyages pour cet horaire
        
        Args:
            date (date, optional): Date de recherche. Par défaut aujourd'hui.
            limit (int): Nombre maximum de voyages à retourner
            
        Returns:
            QuerySet: Prochains voyages
        """
        if not date:
            date = timezone.now().date()
        
        return Trip.objects.filter(
            schedule=self,
            departure_dt__date=date,
            departure_dt__gte=timezone.now(),
            status__in=[Trip.Status.PLANNED, Trip.Status.BOARDING]
        ).select_related('vehicle', 'driver')[:limit]
    
    def get_available_seats(self, trip_date):
        """
        Calcule les sièges disponibles pour une date donnée
        
        Args:
            trip_date (date): Date du voyage
            
        Returns:
            int: Nombre de sièges disponibles
        """
        trips = Trip.objects.filter(
            schedule=self,
            departure_dt__date=trip_date
        )
        
        total_capacity = sum(trip.vehicle.capacity for trip in trips)
        total_passengers = TripPassenger.objects.filter(
            trip__in=trips
        ).count()
        
        return max(0, total_capacity - total_passengers)
    
    def to_json(self):
        """Serialise l'horaire en format JSON pour l'API"""
        return {
            'id': self.id,
            'leg': self.leg.to_json(),
            'agency': {
                'id': self.agency.id,
                'name': self.agency.name,
            },
            'departure_time': self.departure_time.strftime('%H:%M'),
            'days_of_week': self.days_of_week,
            'is_active': self.is_active,
            'created': self.created.isoformat() if self.created else None,
            'updated': self.updated.isoformat() if self.updated else None,
        }


class Vehicle(TimeStampedModel):
    """
    Modèle représentant un véhicule de transport.
    
    Attributes:
        plate (str): Numéro d'immatriculation unique
        capacity (int): Capacité maximale de passagers
        type (str): Type de véhicule (bus, minibus, etc.)
        agency (Agency): Agence propriétaire du véhicule
        is_active (bool): Indique si le véhicule est actif
    """
    plate = models.CharField(
        max_length=20, 
        unique=True,
        verbose_name=_("Plaque d'immatriculation")
    )
    capacity = models.PositiveIntegerField(verbose_name=_("Capacité"))
    type = models.CharField(
        max_length=30, 
        default="bus",
        verbose_name=_("Type de véhicule")
    )
    agency = models.ForeignKey(
        "locations.Agency", 
        on_delete=models.PROTECT, 
        related_name="vehicles",
        verbose_name=_("Agence")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Actif")
    )

    class Meta:
        verbose_name = _("Véhicule")
        verbose_name_plural = _("Véhicules")

    def __str__(self):
        return f"{self.plate} ({self.capacity})"
    
    def get_available_seats(self, trip):
        """
        Calcule les sièges disponibles pour un voyage donné
        
        Args:
            trip (Trip): Voyage concerné
            
        Returns:
            int: Nombre de sièges disponibles
        """
        booked_seats = TripPassenger.objects.filter(
            trip=trip,
            trip__vehicle=self
        ).count()
        return max(0, self.capacity - booked_seats)
    
    def to_json(self):
        """Serialise le véhicule en format JSON pour l'API"""
        return {
            'id': self.id,
            'plate': self.plate,
            'capacity': self.capacity,
            'type': self.type,
            'agency': {
                'id': self.agency.id,
                'name': self.agency.name,
            },
            'is_active': self.is_active,
            'created': self.created.isoformat() if self.created else None,
            'updated': self.updated.isoformat() if self.updated else None,
        }


class Trip(TimeStampedModel):
    """
    Modèle représentant un voyage spécifique planifié.
    
    Attributes:
        schedule (Schedule): Horaire de référence
        agency (Agency): Agence organisatrice
        vehicle (Vehicle): Véhicule affecté
        driver (User): Chauffeur assigné
        departure_dt (DateTime): Date et heure de départ
        status (str): Statut du voyage
    """
    class Status(models.TextChoices):
        PLANNED = "planned", _("Planifié")
        BOARDING = "boarding", _("Embarquement")
        IN_PROGRESS = "in_progress", _("En cours")
        COMPLETED = "completed", _("Terminé")
        CANCELLED = "cancelled", _("Annulé")

    schedule = models.ForeignKey(
        Schedule, 
        on_delete=models.PROTECT, 
        related_name="trips",
        verbose_name=_("Horaire")
    )
    agency = models.ForeignKey(
        "locations.Agency", 
        on_delete=models.PROTECT,
        verbose_name=_("Agence")
    )
    vehicle = models.ForeignKey(
        Vehicle, 
        on_delete=models.PROTECT,
        verbose_name=_("Véhicule")
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        limit_choices_to={'role': 'chauffeur'},
        verbose_name=_("Chauffeur")
    )
    departure_dt = models.DateTimeField(verbose_name=_("Date et heure de départ"))
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.BOARDING,
        verbose_name=_("Statut")
    )

    class Meta:
        verbose_name = _("Voyage")
        verbose_name_plural = _("Voyages")

    def __str__(self):
        return f"{self.schedule.leg.origin}→{self.schedule.leg.destination} ({self.departure_dt})"
    
    def get_available_seats(self):
        """Retourne le nombre de sièges disponibles"""
        booked_count = self.passengers.count()
        return max(0, self.vehicle.capacity - booked_count)
    
    def get_current_passengers(self):
        """Retourne les passagers actuellement à bord"""
        return self.passengers.filter(is_onboard=True)
    
    def update_status(self, new_status):
        """
        Met à jour le statut du voyage
        
        Args:
            new_status (str): Nouveau statut
            
        Returns:
            bool: True si la mise à jour a réussi
        """
        if new_status in dict(self.Status.choices):
            self.status = new_status
            self.save()
            return True
        return False
    
    def to_json(self):
        """Serialise le voyage en format JSON pour l'API"""
        return {
            'id': self.id,
            'schedule': self.schedule.to_json(),
            'agency': {
                'id': self.agency.id,
                'name': self.agency.name,
            },
            'vehicle': self.vehicle.to_json(),
            'driver': {
                'id': self.driver.id,
                'name': self.driver.get_full_name(),
            },
            'departure_dt': self.departure_dt.isoformat(),
            'status': self.status,
            'status_display': self.get_status_display(),
            'available_seats': self.get_available_seats(),
            'created': self.created.isoformat() if self.created else None,
            'updated': self.updated.isoformat() if self.updated else None,
        }


class TripPassenger(TimeStampedModel):
    """
    Modèle représentant un passager dans un voyage.
    
    Attributes:
        trip (Trip): Voyage concerné
        ticket (Ticket): Ticket associé
        client (User): Client qui a réservé
        passenger_name (str): Nom du passager
        seat_number (int): Numéro de siège
        boarded_at (DateTime): Date/heure d'embarquement
        disembarked_at (DateTime): Date/heure de débarquement
        disembarked_city (City): Ville de débarquement
        is_onboard (bool): Indique si le passager est à bord
    """
    trip = models.ForeignKey(
        Trip, 
        on_delete=models.CASCADE, 
        related_name="passengers",
        verbose_name=_("Voyage")
    )
    ticket = models.OneToOneField(
        "reservations.Ticket", 
        on_delete=models.PROTECT, 
        related_name="trip_passenger",
        verbose_name=_("Ticket")
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name="trip_passengers",
        verbose_name=_("Client")
    )
    passenger_name = models.CharField(
        max_length=255,
        verbose_name=_("Nom du passager")
    )
    seat_number = models.PositiveIntegerField(
        null=True, 
        blank=True,
        verbose_name=_("Numéro de siège")
    )
    boarded_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_("Embarqué à")
    )
    disembarked_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_("Débarqué à")
    )
    disembarked_city = models.ForeignKey(
        "locations.City", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name=_("Ville de débarquement")
    )
    is_onboard = models.BooleanField(
        default=True,
        verbose_name=_("À bord")
    )

    class Meta:
        verbose_name = _("Passager voyage")
        verbose_name_plural = _("Passagers voyage")

    def mark_disembarked(self, city):
        """
        Marque le passager comme débarqué
        
        Args:
            city (City): Ville de débarquement
        """
        self.is_onboard = False
        self.disembarked_city = city
        self.disembarked_at = timezone.now()
        self.save(update_fields=["is_onboard", "disembarked_city", "disembarked_at"])

    def mark_boarded(self):
        """Marque le passager comme embarqué"""
        self.is_onboard = True
        self.boarded_at = timezone.now()
        self.save(update_fields=["is_onboard", "boarded_at"])

    def __str__(self):
        return f"{self.passenger_name} ({'à bord' if self.is_onboard else 'descendu'})"
    
    def to_json(self):
        """Serialise le passager en format JSON pour l'API"""
        return {
            'id': self.id,
            'trip_id': self.trip_id,
            'ticket_id': self.ticket_id,
            'client': {
                'id': self.client.id,
                'name': self.client.get_full_name(),
            },
            'passenger_name': self.passenger_name,
            'seat_number': self.seat_number,
            'boarded_at': self.boarded_at.isoformat() if self.boarded_at else None,
            'disembarked_at': self.disembarked_at.isoformat() if self.disembarked_at else None,
            'disembarked_city': {
                'id': self.disembarked_city.id,
                'name': self.disembarked_city.name,
            } if self.disembarked_city else None,
            'is_onboard': self.is_onboard,
            'created': self.created.isoformat() if self.created else None,
            'updated': self.updated.isoformat() if self.updated else None,
        }


class TripEvent(TimeStampedModel):
    """
    Modèle représentant un événement survenu pendant un voyage.
    
    Attributes:
        trip (Trip): Voyage concerné
        event_type (str): Type d'événement
        city (City): Ville où l'événement s'est produit
        note (str): Notes supplémentaires
        timestamp (DateTime): Date/heure de l'événement
        created_by (User): Utilisateur ayant créé l'événement
    """
    class Type(models.TextChoices):
        DEPARTURE = "departure", _("Départ")
        STOP = "stop", _("Arrêt")
        PASSENGER_DESCENT = "passenger_descent", _("Descente passager")
        PASSENGER_BOARDING = "passenger_boarding", _("Embarquement passager")
        INCIDENT = "incident", _("Incident")
        ACCIDENT = "accident", _("Accident")
        ARRIVAL = "arrival", _("Arrivée finale")

    trip = models.ForeignKey(
        Trip, 
        on_delete=models.CASCADE, 
        related_name="events",
        verbose_name=_("Voyage")
    )
    event_type = models.CharField(
        max_length=30, 
        choices=Type.choices,
        verbose_name=_("Type d'événement")
    )
    city = models.ForeignKey(
        "locations.City", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name=_("Ville")
    )
    note = models.TextField(
        blank=True,
        verbose_name=_("Notes")
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Date et heure")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name=_("Créé par")
    )

    class Meta:
        verbose_name = _("Événement voyage")
        verbose_name_plural = _("Événements voyage")

    def __str__(self):
        return f"{self.trip} - {self.get_event_type_display()} ({self.timestamp.strftime('%d/%m %H:%M')})"
    
    def to_json(self):
        """Serialise l'événement en format JSON pour l'API"""
        return {
            'id': self.id,
            'trip_id': self.trip_id,
            'event_type': self.event_type,
            'event_type_display': self.get_event_type_display(),
            'city': {
                'id': self.city.id,
                'name': self.city.name,
            } if self.city else None,
            'note': self.note,
            'timestamp': self.timestamp.isoformat(),
            'created_by': {
                'id': self.created_by.id,
                'name': self.created_by.get_full_name(),
            } if self.created_by else None,
            'created': self.created.isoformat() if self.created else None,
            'updated': self.updated.isoformat() if self.updated else None,
        }



# ==================================================
# APPLICATION: reservations
# FICHIER: models.py
# ==================================================

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
import uuid
import secrets
import string
from core.models import TimeStampedModel, QRCodeMixin
from parameter.models import CompanyConfig


class Reservation(TimeStampedModel):
    """Modèle pour les réservations de voyage"""
    
    class Status(models.TextChoices):
        PENDING = "pending", _("En attente")
        CONFIRMED = "confirmed", _("Confirmée")
        PAID = "paid", _("Payée")
        CANCELLED = "cancelled", _("Annulée")
        EXPIRED = "expired", _("Expirée")

    # Code unique généré automatiquement
    code = models.CharField(
        max_length=12, 
        unique=True, 
        editable=False,
        verbose_name=_("Code de réservation")
    )
    
    # Informations client
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name="reservations",
        verbose_name=_("Acheteur")
    )
    
    # Informations voyage
    schedule = models.ForeignKey(
        "transport.Schedule", 
        on_delete=models.PROTECT, 
        related_name="reservations",
        verbose_name=_("Horaire")
    )
    travel_date = models.DateField(verbose_name=_("Date de voyage"))
    
    # Détails réservation
    total_seats = models.PositiveIntegerField(default=1, verbose_name=_("Nombre de places"))
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Prix total"))
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING,
        verbose_name=_("Statut")
    )
    
    # Métadonnées
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Expire à"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Réservation")
        verbose_name_plural = _("Réservations")
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["buyer"]),
            models.Index(fields=["status"]),
            models.Index(fields=["travel_date"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.buyer.get_full_name()}"

    def save(self, *args, **kwargs):
        """Sauvegarde avec génération automatique du code"""
        if not self.code:
            self.code = self._generate_unique_reservation_code()
        
        # Définir la date d'expiration si c'est une nouvelle réservation en attente
        if not self.pk and self.status == self.Status.PENDING:
            config = CompanyConfig.get_cached_config()
            self.expires_at = timezone.now() + config.get_booking_expiry_timedelta()
        
        super().save(*args, **kwargs)

    def _generate_unique_reservation_code(self):
        """Génère un code de réservation unique"""
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            date_part = timezone.now().strftime('%y%m%d')
            random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
            code = f"RSV{date_part}{random_part}"
            
            if not Reservation.objects.filter(code=code).exists():
                return code
            attempt += 1
        
        fallback_code = f"RSV{timezone.now().strftime('%y%m%d')}{str(uuid.uuid4().int)[:6]}"
        return fallback_code[:12]

    def confirm_reservation(self):
        """Confirme la réservation"""
        self.status = self.Status.CONFIRMED
        self.expires_at = None
        self.save()
        
        # Créer les tickets associés
        self._create_tickets()

    def mark_paid(self):
        """Marque la réservation comme payée"""
        self.status = self.Status.PAID
        self.expires_at = None
        self.save()

    def cancel_reservation(self, reason=""):
        """Annule la réservation"""
        self.status = self.Status.CANCELLED
        self.notes = f"{self.notes}\nAnnulé: {reason}".strip()
        self.save()
        
        # Annuler les tickets associés
        self.tickets.update(status=Ticket.Status.CANCELLED)

    def mark_expired(self):
        """Marque la réservation comme expirée"""
        if self.status == self.Status.PENDING and self.expires_at and timezone.now() > self.expires_at:
            self.status = self.Status.EXPIRED
            self.save()
            return True
        return False

    def _create_tickets(self):
        """Crée les tickets pour cette réservation"""
        from transport.models import Trip
        
        # Trouver le voyage correspondant à la date
        trip = Trip.objects.filter(
            schedule=self.schedule,
            departure_dt__date=self.travel_date
        ).first()
        
        for i in range(self.total_seats):
            Ticket.objects.create(
                reservation=self,
                trip=trip,
                buyer=self.buyer,
                passenger_name=f"Passager {i+1}",
                passenger_phone=self.buyer.phone,
                status=Ticket.Status.CONFIRMED
            )

    def get_travel_details(self):
        """Retourne les détails du voyage"""
        return {
            'origin': self.schedule.leg.origin.name,
            'destination': self.schedule.leg.destination.name,
            'departure_time': self.schedule.departure_time,
            'travel_date': self.travel_date,
            'duration': self.schedule.leg.duration_minutes,
            'agency': self.schedule.agency.name
        }

    @property
    def is_active(self):
        return self.status in [self.Status.CONFIRMED, self.Status.PAID]


class Ticket(TimeStampedModel, QRCodeMixin):
    """Modèle pour les tickets de voyage avec gestion d'embarquement par scan"""
    
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", _("Confirmé")
        BOARDED = "boarded", _("Embarqué")
        MISSED = "missed", _("Non embarqué")
        CANCELLED = "cancelled", _("Annulé")
        REFUNDED = "refunded", _("Remboursé")

    # Code unique généré automatiquement
    ticket_code = models.CharField(
        max_length=15,
        unique=True,
        editable=False,
        verbose_name=_("Code du ticket")
    )
    
    # Références
    reservation = models.ForeignKey(
        Reservation, 
        on_delete=models.CASCADE, 
        related_name="tickets",
        verbose_name=_("Réservation")
    )
    trip = models.ForeignKey(
        "transport.Trip", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="tickets",
        verbose_name=_("Voyage")
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name="purchased_tickets",
        verbose_name=_("Acheteur")
    )
    
    # Informations passager
    passenger_name = models.CharField(max_length=255, verbose_name=_("Nom du passager"))
    passenger_phone = models.CharField(max_length=30, blank=True, verbose_name=_("Téléphone du passager"))
    passenger_email = models.EmailField(blank=True, verbose_name=_("Email du passager"))
    passenger_id = models.CharField(max_length=50, blank=True, verbose_name=_("Pièce d'identité"))
    
    # Siège et statut
    seat_number = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Numéro de siège"))
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.CONFIRMED,
        verbose_name=_("Statut")
    )
    
    # Métadonnées d'embarquement
    scanned_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Scanné à"))
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="scanned_tickets",
        verbose_name=_("Scanné par")
    )
    boarding_time = models.DateTimeField(null=True, blank=True, verbose_name=_("Heure d'embarquement"))
    scan_location = models.ForeignKey(
        "locations.City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Lieu de scan")
    )

    class Meta:
        verbose_name = _("Ticket")
        verbose_name_plural = _("Tickets")
        ordering = ["seat_number", "passenger_name"]
        indexes = [
            models.Index(fields=["ticket_code"]),
            models.Index(fields=["reservation"]),
            models.Index(fields=["status"]),
            models.Index(fields=["scanned_at"]),
            models.Index(fields=["trip"]),
        ]

    def __str__(self):
        return f"{self.ticket_code} - {self.passenger_name}"

    def save(self, *args, **kwargs):
        """Sauvegarde avec génération automatique des codes"""
        if not self.ticket_code:
            self.ticket_code = self._generate_unique_ticket_code()
        
        if not self.qr_token:
            self.qr_token = uuid.uuid4().hex
            
        super().save(*args, **kwargs)
        
        if not self.qr_image:
            self.generate_qr_code()

    def _generate_unique_ticket_code(self):
        """Génère un code de ticket unique"""
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            date_part = timezone.now().strftime('%y%m%d')
            random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            code = f"TCK{date_part}{random_part}"
            
            if not Ticket.objects.filter(ticket_code=code).exists():
                return code
            attempt += 1
        
        fallback_code = f"TCK{timezone.now().strftime('%y%m%d')}{str(uuid.uuid4().int)[:8]}"
        return fallback_code[:15]

    # =========================================================================
    # MÉTHODES DE SCAN ET EMBARQUEMENT
    # =========================================================================

    def scan_ticket(self, scanned_by, scan_location=None):
        """
        Scan un ticket pour l'embarquement
        Retourne un dict avec le résultat du scan
        """
        scan_result = {
            'success': False,
            'message': '',
            'ticket_status': self.status,
            'trip_status': self.trip.status if self.trip else None,
            'already_boarded': False,
            'trip_departed': False,
            'trip_completed': False,
            'current_location': None
        }

        # Vérifier si le ticket est déjà embarqué
        if self.status == self.Status.BOARDED:
            scan_result['already_boarded'] = True
            scan_result['message'] = _("Ticket déjà embarqué")
            
            # Vérifier l'état du voyage pour le passager déjà embarqué
            if self.trip:
                trip_info = self._get_trip_current_info()
                scan_result.update(trip_info)
                scan_result['message'] += f". {trip_info['message']}"
            
            return scan_result

        # Vérifier si le voyage est déjà parti
        if self.trip and self._is_trip_departed():
            scan_result['trip_departed'] = True
            scan_result['message'] = _("Le voyage est déjà parti")
            return scan_result

        # Vérifier si le voyage est terminé
        if self.trip and self._is_trip_completed():
            scan_result['trip_completed'] = True
            scan_result['message'] = _("Le voyage est terminé")
            return scan_result

        # Vérifier si l'embarquement est possible
        if not self._can_board():
            scan_result['message'] = _("Embarquement non autorisé à ce moment")
            return scan_result

        # Marquer comme embarqué
        self.status = self.Status.BOARDED
        self.scanned_at = timezone.now()
        self.scanned_by = scanned_by
        self.boarding_time = timezone.now()
        self.scan_location = scan_location
        self.save()

        scan_result['success'] = True
        scan_result['message'] = _("Ticket embarqué avec succès")
        scan_result['ticket_status'] = self.Status.BOARDED

        # Créer un événement d'embarquement
        self._create_boarding_event(scanned_by)

        return scan_result

    def _get_trip_current_info(self):
        """Retourne les informations actuelles du voyage"""
        if not self.trip:
            return {'message': _("Aucun voyage associé")}

        trip = self.trip
        current_info = {
            'trip_status': trip.status,
            'trip_departed': trip.status in ['in_progress', 'completed'],
            'trip_completed': trip.status == 'completed',
            'current_location': None,
            'message': _("Voyage: {}").format(trip.get_status_display())
        }

        # Obtenir la position actuelle du voyage
        if trip.status == 'in_progress':
            current_location = trip.get_current_location()
            if current_location:
                current_info['current_location'] = current_location
                current_info['message'] += _(" - Position: {}").format(current_location.get('city', 'En route'))

        return current_info

    def _is_trip_departed(self):
        """Vérifie si le voyage est déjà parti"""
        if not self.trip:
            return False
        return self.trip.status in ['boarding', 'in_progress', 'completed']

    def _is_trip_completed(self):
        """Vérifie si le voyage est terminé"""
        if not self.trip:
            return False
        return self.trip.status == 'completed'

    def _can_board(self):
        """Vérifie si l'embarquement est possible"""
        if not self.trip:
            return False
        
        # Vérifier le statut du ticket
        if self.status != self.Status.CONFIRMED:
            return False

        # Vérifier le statut du voyage
        if self.trip.status not in ['planned', 'boarding']:
            return False

        # Vérifier l'horaire d'embarquement (jusqu'à 30 minutes après le départ prévu)
        departure_time = self.trip.departure_dt
        current_time = timezone.now()
        
        return current_time <= departure_time + timezone.timedelta(minutes=30)

    def _create_boarding_event(self, scanned_by):
        """Crée un événement d'embarquement"""
        from transport.models import TripEvent
        
        if self.trip:
            TripEvent.objects.create(
                trip=self.trip,
                event_type='passenger_boarding',
                city=self.scan_location,
                note=f"Embarquement: {self.passenger_name} (Ticket: {self.ticket_code})",
                created_by=scanned_by
            )

    # =========================================================================
    # MÉTHODES DE GESTION AUTOMATIQUE DES TICKETS NON EMBARQUÉS
    # =========================================================================

    def auto_mark_missed(self):
        """
        Marque automatiquement le ticket comme non embarqué
        si le voyage a commencé et le ticket n'a pas été scanné
        """
        if (self.status == self.Status.CONFIRMED and 
            self.trip and 
            self.trip.status == 'in_progress' and
            not self.scanned_at):
            
            self.status = self.Status.MISSED
            self.save()
            return True
        return False

    @classmethod
    def process_missed_tickets_for_trip(cls, trip):
        """
        Traite tous les tickets non embarqués pour un voyage
        """
        missed_tickets = cls.objects.filter(
            trip=trip,
            status=cls.Status.CONFIRMED,
            scanned_at__isnull=True
        )
        
        count = 0
        for ticket in missed_tickets:
            if ticket.auto_mark_missed():
                count += 1
        
        return count

    # =========================================================================
    # MÉTHODES D'INFORMATION
    # =========================================================================

    def get_ticket_info_for_scan(self):
        """Retourne les informations du ticket pour l'affichage lors du scan"""
        return {
            'ticket_code': self.ticket_code,
            'passenger_name': self.passenger_name,
            'seat_number': self.seat_number,
            'status': self.status,
            'status_display': self.get_status_display(),
            'scanned_at': self.scanned_at.isoformat() if self.scanned_at else None,
            'trip_info': self.get_trip_info() if self.trip else None,
            'can_board': self._can_board(),
            'is_missed': self.status == self.Status.MISSED
        }

    def get_trip_info(self):
        """Retourne les informations du voyage associé"""
        if not self.trip:
            return None
            
        return {
            'trip_id': self.trip.id,
            'origin': self.trip.schedule.leg.origin.name,
            'destination': self.trip.schedule.leg.destination.name,
            'departure_time': self.trip.departure_dt,
            'current_status': self.trip.status,
            'current_status_display': self.trip.get_status_display(),
            'vehicle': self.trip.vehicle.plate,
            'driver': self.trip.driver.get_full_name(),
            'is_departed': self._is_trip_departed(),
            'is_completed': self._is_trip_completed()
        }

    # =========================================================================
    # MÉTHODES DE VALIDATION
    # =========================================================================

    def is_scanned(self):
        """Vérifie si le ticket a été scanné"""
        return self.scanned_at is not None

    def is_boarding_in_progress(self):
        """Vérifie si l'embarquement est en cours"""
        if not self.trip:
            return False
        
        boarding_start = self.trip.departure_dt - timezone.timedelta(minutes=30)
        boarding_end = self.trip.departure_dt + timezone.timedelta(minutes=15)
        current_time = timezone.now()
        
        return boarding_start <= current_time <= boarding_end

    # =========================================================================
    # PROPRIÉTÉS UTILES
    # =========================================================================

    @property
    def is_departed(self):
        """Vérifie si le voyage est parti"""
        return self._is_trip_departed()

    @property
    def boarding_status(self):
        """Statut d'embarquement"""
        if self.status == self.Status.BOARDED:
            return 'embarqué'
        elif self.status == self.Status.MISSED:
            return 'non_embarqué'
        elif self._can_board():
            return 'peut_embarquer'
        else:
            return 'embarquement_fermé'


class Payment(TimeStampedModel):
    """Modèle pour les paiements"""
    
    class Method(models.TextChoices):
        CASH = "cash", _("Espèces")
        CARD = "card", _("Carte bancaire")
        MOBILE_MONEY = "mobile_money", _("Mobile Money")
        BANK_TRANSFER = "bank_transfer", _("Virement bancaire")

    class Status(models.TextChoices):
        PENDING = "pending", _("En attente")
        COMPLETED = "completed", _("Complété")
        FAILED = "failed", _("Échoué")
        REFUNDED = "refunded", _("Remboursé")

    # Références
    reservation = models.OneToOneField(
        Reservation, 
        on_delete=models.PROTECT, 
        related_name="payment",
        verbose_name=_("Réservation")
    )
    
    # Informations paiement
    method = models.CharField(
        max_length=20, 
        choices=Method.choices,
        verbose_name=_("Méthode de paiement")
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name=_("Montant")
    )
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING,
        verbose_name=_("Statut")
    )
    
    # Références externes
    provider_ref = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name=_("Référence prestataire")
    )
    
    # Métadonnées
    paid_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name=_("Payé à")
    )
    agency = models.ForeignKey(
        "locations.Agency", 
        on_delete=models.PROTECT, 
        related_name="payments", 
        null=True, 
        blank=True,
        verbose_name=_("Agence")
    )

    class Meta:
        verbose_name = _("Paiement")
        verbose_name_plural = _("Paiements")
        ordering = ["-created"]

    def __str__(self):
        return f"Paiement {self.amount} - {self.get_status_display()}"

    def mark_completed(self, provider_ref=None):
        """Marque le paiement comme complété"""
        self.status = self.Status.COMPLETED
        self.paid_at = timezone.now()
        
        if provider_ref:
            self.provider_ref = provider_ref
            
        self.save()
        
        # Mettre à jour la réservation
        self.reservation.mark_paid()

    def mark_failed(self):
        """Marque le paiement comme échoué"""
        self.status = self.Status.FAILED
        self.save()

    def mark_refunded(self, amount=None):
        """Marque le paiement comme remboursé"""
        self.status = self.Status.REFUNDED
        self.refund_amount = amount or self.amount
        self.refunded_at = timezone.now()
        self.save()
        
        # Mettre à jour les tickets
        self.reservation.tickets.update(status=Ticket.Status.REFUNDED)



# ==================================================
# APPLICATION: parcel
# FICHIER: models.py
# ==================================================

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from core.models import TimeStampedModel, QRCodeMixin
from parameter.models import CompanyConfig


from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from django.urls import reverse
import uuid
from core.models import TimeStampedModel, QRCodeMixin


class Parcel(TimeStampedModel, QRCodeMixin):
    """Modèle pour la gestion complète des colis avec suivi en temps réel"""
    
    class Status(models.TextChoices):
        CREATED = "created", _("Enregistré")
        LOADED = "loaded", _("Chargé pour transport")
        AT_AGENCY = "at_agency", _("Arrivé à l'agence")
        OUT_FOR_DELIVERY = "out_for_delivery", _("En livraison")
        DELIVERED = "delivered", _("Livré")
        RETURNED = "returned", _("Retourné")
        LOST = "lost", _("Perdu")

    class Category(models.TextChoices):
        SMALL = "small", _("Petit colis (< 5kg)")
        MEDIUM = "medium", _("Colis moyen (5-20kg)")
        LARGE = "large", _("Gros colis (> 20kg)")
        DOCUMENT = "document", _("Document")
        FRAGILE = "fragile", _("Fragile")
        OTHER = "other", _("Autre")

    # Informations de base - tracking_code généré automatiquement
    tracking_code = models.CharField(
        max_length=20, 
        unique=True, 
        verbose_name=_("Code de suivi"),
        blank=True  # Permet de générer automatiquement
    )
    
    # Informations expéditeur
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sent_parcels", verbose_name=_("Expéditeur"))
    sender_name = models.CharField(max_length=120, verbose_name=_("Nom de l'expéditeur"))
    sender_phone = models.CharField(max_length=30, verbose_name=_("Téléphone expéditeur"))
    sender_address = models.TextField(blank=True, verbose_name=_("Adresse expéditeur"))
    
    # Informations destinataire
    receiver_name = models.CharField(max_length=120, verbose_name=_("Nom du destinataire"))
    receiver_phone = models.CharField(max_length=30, verbose_name=_("Téléphone du destinataire"))
    receiver_address = models.TextField(verbose_name=_("Adresse de livraison"))
    receiver_city = models.ForeignKey("locations.City", on_delete=models.PROTECT, related_name="parcels_destination_city", verbose_name=_("Ville de destination"))

    # Origine et destination
    origin_agency = models.ForeignKey("locations.Agency", on_delete=models.PROTECT, related_name="parcels_origin", verbose_name=_("Agence d'origine"))
    destination_agency = models.ForeignKey("locations.Agency", on_delete=models.PROTECT, related_name="parcels_destination", verbose_name=_("Agence de destination"))
    origin_city = models.ForeignKey("locations.City", on_delete=models.PROTECT, related_name="parcels_origin_city", verbose_name=_("Ville d'origine"))
    destination_city = models.ForeignKey("locations.City", on_delete=models.PROTECT, related_name="parcels_destination_city_final", verbose_name=_("Ville de destination finale"))

    # Caractéristiques du colis
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.MEDIUM, verbose_name=_("Catégorie"))
    description = models.TextField(blank=True, verbose_name=_("Description du contenu"))
    weight_kg = models.DecimalField(max_digits=7, decimal_places=3, validators=[MinValueValidator(0)], verbose_name=_("Poids (kg)"))
    dimensions = models.CharField(max_length=100, blank=True, verbose_name=_("Dimensions (L x l x H)"))
    declared_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_("Valeur déclarée"))

    # Tarification
    base_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Prix de base"))
    insurance_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_("Frais d'assurance"))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_("Frais de livraison"))
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Prix total"))

    # Statut et localisation
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED, verbose_name=_("Statut"))
    current_city = models.ForeignKey("locations.City", on_delete=models.PROTECT, related_name="parcels_current", verbose_name=_("Ville actuelle"))
    current_agency = models.ForeignKey("locations.Agency", on_delete=models.PROTECT, related_name="parcels_current", null=True, blank=True, verbose_name=_("Agence actuelle"))
    current_trip = models.ForeignKey("transport.Trip", on_delete=models.SET_NULL, null=True, blank=True, related_name="parcels", verbose_name=_("Voyage actuel"))

    # Options de livraison
    requires_signature = models.BooleanField(default=True, verbose_name=_("Signature requise"))
    requires_delivery_confirmation = models.BooleanField(default=True, verbose_name=_("Confirmation de livraison"))
    home_delivery = models.BooleanField(default=False, verbose_name=_("Livraison à domicile"))
    insurance_required = models.BooleanField(default=False, verbose_name=_("Assurance souscrite"))

    # Preuves et validation
    delivery_proof = models.ImageField(upload_to="parcels/delivery_proofs/", blank=True, null=True, verbose_name=_("Preuve de livraison"))
    recipient_signature = models.ImageField(upload_to="parcels/signatures/", blank=True, null=True, verbose_name=_("Signature du destinataire"))
    delivery_code = models.CharField(max_length=10, blank=True, verbose_name=_("Code de livraison"))

    # Métadonnées
    last_handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="handled_parcels", verbose_name=_("Dernier gestionnaire"))
    estimated_delivery = models.DateTimeField(null=True, blank=True, verbose_name=_("Livraison estimée"))
    actual_delivery = models.DateTimeField(null=True, blank=True, verbose_name=_("Livraison effective"))
    delivery_attempts = models.PositiveIntegerField(default=0, verbose_name=_("Tentatives de livraison"))

    class Meta:
        verbose_name = _("Colis")
        verbose_name_plural = _("Colis")
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["tracking_code"]),
            models.Index(fields=["receiver_phone"]),
            models.Index(fields=["status"]),
            models.Index(fields=["current_agency"]),
            models.Index(fields=["origin_agency"]),
            models.Index(fields=["destination_agency"]),
        ]

    def __str__(self):
        return f"{self.tracking_code} - {self.receiver_name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        """Sauvegarde avec génération automatique des codes et calcul des prix"""
        # Génération du tracking_code si vide
        if not self.tracking_code:
            self.tracking_code = self._generate_unique_tracking_code()
        
        # Génération du QR token si vide
        if not self.qr_token:
            self.qr_token = self._generate_qr_token()
        
        # Calcul du prix total
        self._calculate_total_price()
        
        # Définition des villes si non spécifiées
        if not self.origin_city and self.origin_agency:
            self.origin_city = self.origin_agency.city
        if not self.destination_city and self.destination_agency:
            self.destination_city = self.destination_agency.city
        if not self.current_city:
            self.current_city = self.origin_city
        
        super().save(*args, **kwargs)
        
        # Génération du QR code après sauvegarde
        if not self.qr_image:
            self.generate_qr_code()

    # =========================================================================
    # MÉTHODES DE GÉNÉRATION DE CODES UNIQUES
    # =========================================================================

    def _generate_unique_tracking_code(self):
        """
        Génère un code de suivi unique avec vérification d'unicité
        Format: PCL + YYMMDD + 6 caractères aléatoires
        """
        import secrets
        import string
        
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            # Format: PCL230101 + 6 caractères aléatoires
            date_part = timezone.now().strftime('%y%m%d')
            random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            tracking_code = f"PCL{date_part}{random_part}"
            
            # Vérifier l'unicité
            if not Parcel.objects.filter(tracking_code=tracking_code).exists():
                return tracking_code
            
            attempt += 1
        
        # Fallback avec UUID si échec après plusieurs tentatives
        fallback_code = f"PCL{timezone.now().strftime('%y%m%d')}{str(uuid.uuid4().int)[:8]}"
        return fallback_code[:20]  # Truncate to max_length

    def _generate_qr_token(self):
        """Génère un token unique pour le QR code"""
        return uuid.uuid4().hex

    def _calculate_total_price(self):
        """Calcule le prix total du colis"""
        self.total_price = self.base_price + self.insurance_fee + self.delivery_fee

    def generate_delivery_code(self):
        """Génère un code de livraison pour le destinataire"""
        import secrets
        import string
        alphabet = string.digits
        self.delivery_code = ''.join(secrets.choice(alphabet) for _ in range(6))
        self.save()
        return self.delivery_code

    # =========================================================================
    # MÉTHODES D'URLS DYNAMIQUES AVEC REQUEST
    # =========================================================================

    def get_tracking_url(self, request=None):
        """URL de suivi absolue basée sur la request"""
        if request:
            return request.build_absolute_uri(f"/tracking/{self.tracking_code}/")
        else:
            # Fallback si pas de request (emails, background tasks, etc.)
            base_url = getattr(settings, 'FRONTEND_BASE_URL', 'https://votre-site.com')
            return f"{base_url}/tracking/{self.tracking_code}/"

    def get_qr_code_url(self, request=None):
        """URL du QR code absolue"""
        if request:
            return request.build_absolute_uri(f"/qr/{self.qr_token}/")
        else:
            base_url = getattr(settings, 'FRONTEND_BASE_URL', 'https://votre-site.com')
            return f"{base_url}/qr/{self.qr_token}/"

    def get_admin_tracking_url(self, request=None):
        """URL de suivi pour l'administration"""
        if request:
            return request.build_absolute_uri(f"/admin/parcels/parcel/{self.id}/tracking/")
        else:
            base_url = getattr(settings, 'BACKEND_BASE_URL', 'https://admin.votre-site.com')
            return f"{base_url}/admin/parcels/parcel/{self.id}/tracking/"

    def get_api_tracking_url(self, request=None):
        """URL de l'API pour le suivi"""
        if request:
            return request.build_absolute_uri(f"/api/v1/parcels/{self.tracking_code}/tracking/")
        else:
            base_url = getattr(settings, 'API_BASE_URL', 'https://api.votre-site.com')
            return f"{base_url}/api/v1/parcels/{self.tracking_code}/tracking/"

    def get_customer_tracking_url(self, request=None):
        """URL publique de suivi pour les clients"""
        if request:
            return request.build_absolute_uri(f"/mes-colis/suivi/{self.tracking_code}/")
        else:
            base_url = getattr(settings, 'CUSTOMER_PORTAL_URL', 'https://client.votre-site.com')
            return f"{base_url}/mes-colis/suivi/{self.tracking_code}/"

    def get_driver_tracking_url(self, request=None):
        """URL de suivi pour les livreurs"""
        if request:
            return request.build_absolute_uri(f"/driver/parcels/{self.id}/track/")
        else:
            base_url = getattr(settings, 'DRIVER_APP_URL', 'https://livreur.votre-site.com')
            return f"{base_url}/driver/parcels/{self.id}/track/"

    def get_delivery_confirmation_url(self, request=None):
        """URL de confirmation de livraison"""
        if request:
            return request.build_absolute_uri(f"/delivery/confirm/{self.delivery_code}/")
        else:
            base_url = getattr(settings, 'FRONTEND_BASE_URL', 'https://votre-site.com')
            return f"{base_url}/delivery/confirm/{self.delivery_code}/"

    # =========================================================================
    # MÉTHODES DE GESTION DU STATUT
    # =========================================================================

    def update_status(self, new_status, actor, agency=None, trip=None, note="", proof=None):
        """
        Met à jour le statut du colis et crée un événement de suivi
        """
        old_status = self.status
        self.status = new_status
        self.current_agency = agency or self.current_agency
        self.current_trip = trip or self.current_trip
        self.last_handled_by = actor
        
        # Mise à jour de la localisation
        if agency:
            self.current_city = agency.city
        
        # Gestion des dates de livraison
        if new_status == self.Status.DELIVERED:
            self.actual_delivery = timezone.now()
            if proof:
                self.delivery_proof = proof
        
        self.save()

        # Création de l'événement de suivi
        TrackingEvent.objects.create(
            parcel=self,
            event=new_status,
            status=new_status,
            city=self.current_city,
            agency=self.current_agency,
            trip=self.current_trip,
            actor=actor,
            note=note,
        )

        # Notification si nécessaire
        self._notify_status_change(old_status, new_status)
        
        return self

    def mark_loaded(self, actor, trip, note=""):
        """Marque le colis comme chargé dans un véhicule"""
        return self.update_status(
            self.Status.LOADED, 
            actor, 
            trip=trip, 
            note=note or "Colis chargé dans le véhicule"
        )

    def mark_arrived(self, actor, agency, note=""):
        """Marque le colis comme arrivé à une agence"""
        return self.update_status(
            self.Status.AT_AGENCY, 
            actor, 
            agency=agency, 
            note=note or "Colis arrivé à l'agence"
        )

    def mark_out_for_delivery(self, actor, agency=None, note=""):
        """Marque le colis comme en cours de livraison"""
        self.delivery_attempts += 1
        return self.update_status(
            self.Status.OUT_FOR_DELIVERY,
            actor,
            agency=agency,
            note=note or f"Colis en cours de livraison - tentative {self.delivery_attempts}"
        )

    def mark_delivered(self, actor, proof=None, signature=None, note=""):
        """Marque le colis comme livré"""
        if signature:
            self.recipient_signature = signature
        return self.update_status(
            self.Status.DELIVERED,
            actor,
            note=note or "Colis livré avec succès",
            proof=proof
        )

    def mark_returned(self, actor, note=""):
        """Marque le colis comme retourné"""
        return self.update_status(
            self.Status.RETURNED,
            actor,
            note=note or "Colis retourné à l'expéditeur"
        )

    def mark_lost(self, actor, note=""):
        """Marque le colis comme perdu"""
        return self.update_status(
            self.Status.LOST,
            actor,
            note=note or "Colis déclaré perdu"
        )

    # =========================================================================
    # MÉTHODES DE SUIVI ET TRACABILITÉ
    # =========================================================================

    def get_tracking_history(self):
        """Retourne l'historique complet de suivi du colis"""
        return self.events.all().order_by('ts')

    def get_current_location(self):
        """Retourne la localisation actuelle du colis"""
        if self.current_agency:
            return {
                'type': 'agency',
                'agency': self.current_agency.name,
                'city': self.current_city.name,
                'address': self.current_agency.address
            }
        elif self.current_trip:
            return {
                'type': 'in_transit',
                'trip': str(self.current_trip),
                'vehicle': self.current_trip.vehicle.plate,
                'driver': self.current_trip.driver.get_full_name()
            }
        else:
            return {
                'type': 'unknown',
                'city': self.current_city.name
            }

    def get_estimated_delivery_time(self):
        """Calcule le temps de livraison estimé"""
        if self.actual_delivery:
            return self.actual_delivery
        
        if self.status == self.Status.DELIVERED:
            return self.actual_delivery
        
        # Logique d'estimation basée sur la distance et le statut
        base_estimation = self.created + timezone.timedelta(days=3)
        return base_estimation

    def is_deliverable(self):
        """Vérifie si le colis peut être livré"""
        return self.status in [
            self.Status.AT_AGENCY,
            self.Status.OUT_FOR_DELIVERY
        ] and not self._is_after_hours()

    def _is_after_hours(self):
        """Vérifie si c'est en dehors des heures de livraison"""
        from datetime import time
        now = timezone.now().time()
        return now < time(8, 0) or now > time(18, 0)

    # =========================================================================
    # MÉTHODES DE NOTIFICATION AVEC URLS DYNAMIQUES
    # =========================================================================

    def _notify_status_change(self, old_status, new_status, request=None):
        """Envoie des notifications lors du changement de statut"""
        if new_status == self.Status.DELIVERED:
            self._notify_delivery(request)
        elif new_status == self.Status.OUT_FOR_DELIVERY:
            self._notify_out_for_delivery(request)
        elif new_status in [self.Status.LOST, self.Status.RETURNED]:
            self._notify_problem(request)

    def _notify_delivery(self, request=None):
        """Notification de livraison réussie avec URL de confirmation"""
        tracking_url = self.get_tracking_url(request)
        message = (
            f"Votre colis {self.tracking_code} a été livré avec succès. "
            f"Suivez votre colis: {tracking_url}"
        )
        self._send_sms_notification(self.receiver_phone, message)

    def _notify_out_for_delivery(self, request=None):
        """Notification de mise en livraison avec code"""
        tracking_url = self.get_tracking_url(request)
        message = (
            f"Votre colis {self.tracking_code} est en cours de livraison. "
            f"Code: {self.delivery_code} - Suivi: {tracking_url}"
        )
        self._send_sms_notification(self.receiver_phone, message)

    def _notify_problem(self, request=None):
        """Notification de problème avec URL de contact"""
        contact_url = getattr(settings, 'CONTACT_URL', 'https://votre-site.com/contact')
        message = (
            f"Votre colis {self.tracking_code} rencontre un problème. "
            f"Statut: {self.get_status_display()}. "
            f"Contactez-nous: {contact_url}"
        )
        self._send_sms_notification(self.sender_phone, message)

    def _send_sms_notification(self, phone, message):
        """Envoie une notification SMS"""
        # Intégration avec service SMS (Twilio, etc.)
        try:
            # Code d'envoi SMS à implémenter
            print(f"SMS to {phone}: {message}")
            return True
        except Exception as e:
            print(f"Erreur envoi SMS: {str(e)}")
            return False

    # =========================================================================
    # MÉTHODES DE VALIDATION
    # =========================================================================

    def validate_weight(self):
        """Valide le poids du colis selon les limites de l'entreprise"""
        config = CompanyConfig.get_cached_config()
        return self.weight_kg <= config.max_parcel_weight

    def validate_dimensions(self):
        """Valide les dimensions du colis"""
        # Logique de validation des dimensions
        return True

    def can_be_updated(self):
        """Vérifie si le colis peut être modifié"""
        return self.status in [self.Status.CREATED, self.Status.AT_AGENCY]

    # =========================================================================
    # MÉTHODES DE RAPPORT ET ANALYSE
    # =========================================================================

    def get_delivery_timeline(self):
        """Retourne la timeline de livraison"""
        events = self.get_tracking_history()
        timeline = []
        
        for event in events:
            timeline.append({
                'timestamp': event.ts,
                'event': event.get_event_display(),
                'location': event.city.name,
                'note': event.note
            })
        
        return timeline

    def calculate_delivery_duration(self):
        """Calcule la durée totale de livraison"""
        if self.actual_delivery:
            return self.actual_delivery - self.created
        return None

    @classmethod
    def get_agency_statistics(cls, agency, start_date=None, end_date=None):
        """Statistiques des colis pour une agence"""
        if not start_date:
            start_date = timezone.now().date() - timezone.timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()

        parcels = cls.objects.filter(
            models.Q(origin_agency=agency) | models.Q(destination_agency=agency),
            created__date__range=[start_date, end_date]
        )

        return {
            'total_parcels': parcels.count(),
            'delivered': parcels.filter(status=cls.Status.DELIVERED).count(),
            'in_transit': parcels.filter(status__in=[cls.Status.LOADED, cls.Status.AT_AGENCY]).count(),
            'pending': parcels.filter(status=cls.Status.CREATED).count(),
            'problems': parcels.filter(status__in=[cls.Status.LOST, cls.Status.RETURNED]).count(),
            'total_revenue': parcels.aggregate(total=models.Sum('total_price'))['total'] or 0,
        }

    # =========================================================================
    # PROPRIÉTÉS UTILES
    # =========================================================================

    @property
    def is_delivered(self):
        return self.status == self.Status.DELIVERED

    @property
    def is_in_transit(self):
        return self.status in [self.Status.LOADED, self.Status.OUT_FOR_DELIVERY]

    @property
    def has_insurance(self):
        return self.insurance_required and self.insurance_fee > 0

    @property
    def requires_home_delivery(self):
        return self.home_delivery


class TrackingEvent(TimeStampedModel):
    """Modèle pour le suivi détaillé des événements de colis"""
    
    class Event(models.TextChoices):
        CREATED = "created", _("Colis enregistré")
        LOADED = "loaded", _("Chargé pour transport")
        AT_AGENCY = "at_agency", _("Arrivé à l'agence")
        OUT_FOR_DELIVERY = "out_for_delivery", _("En livraison")
        DELIVERED = "delivered", _("Livré")
        RETURNED = "returned", _("Retourné")
        LOST = "lost", _("Perdu")
        EXCEPTION = "exception", _("Incident / Anomalie")
        DELIVERY_ATTEMPT = "delivery_attempt", _("Tentative de livraison")
        HOLD = "hold", _("Mis en attente")
        CUSTOMS = "customs", _("Passage en douane")

    parcel = models.ForeignKey(Parcel, on_delete=models.CASCADE, related_name="events", verbose_name=_("Colis"))
    event = models.CharField(max_length=20, choices=Event.choices, verbose_name=_("Événement"))
    status = models.CharField(max_length=20, choices=Parcel.Status.choices, verbose_name=_("Statut"))
    
    # Localisation
    city = models.ForeignKey("locations.City", on_delete=models.PROTECT, verbose_name=_("Ville"))
    agency = models.ForeignKey("locations.Agency", on_delete=models.PROTECT, related_name="tracking_events", null=True, blank=True, verbose_name=_("Agence"))
    trip = models.ForeignKey("transport.Trip", on_delete=models.SET_NULL, null=True, blank=True, related_name="parcel_events", verbose_name=_("Voyage"))

    # Détails
    note = models.CharField(max_length=255, blank=True, verbose_name=_("Note"))
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="parcel_events", verbose_name=_("Acteur"))
    ts = models.DateTimeField(default=timezone.now, db_index=True, verbose_name=_("Horodatage"))

    # Données supplémentaires
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name=_("Latitude"))
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name=_("Longitude"))
    photos = models.JSONField(default=list, blank=True, verbose_name=_("Photos"))

    class Meta:
        ordering = ["-ts"]
        verbose_name = _("Événement de suivi")
        verbose_name_plural = _("Événements de suivi")
        indexes = [
            models.Index(fields=["parcel", "ts"]),
            models.Index(fields=["event"]),
            models.Index(fields=["agency"]),
        ]

    def __str__(self):
        return f"{self.parcel.tracking_code} - {self.get_event_display()} @ {self.city.name}"

    def save(self, *args, **kwargs):
        """Sauvegarde avec validation"""
        if not self.ts:
            self.ts = timezone.now()
        
        # Synchronisation du statut avec le colis
        if self.parcel:
            self.status = self.parcel.status
        
        super().save(*args, **kwargs)

    def get_location_display(self):
        """Retourne l'affichage de la localisation"""
        if self.agency:
            return f"{self.agency.name}, {self.city.name}"
        elif self.trip:
            return f"En transit - {self.trip.vehicle.plate}, {self.city.name}"
        else:
            return self.city.name

    def add_photo(self, photo_url):
        """Ajoute une photo à l'événement"""
        if not self.photos:
            self.photos = []
        self.photos.append(photo_url)
        self.save()

    @classmethod
    def create_delivery_attempt(cls, parcel, actor, note="", photos=None):
        """Crée un événement de tentative de livraison"""
        return cls.objects.create(
            parcel=parcel,
            event=cls.Event.DELIVERY_ATTEMPT,
            status=parcel.status,
            city=parcel.current_city,
            agency=parcel.current_agency,
            actor=actor,
            note=note,
            photos=photos or []
        )



# ==================================================
# APPLICATION: publications
# FICHIER: models.py
# ==================================================

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import uuid
import secrets
import string
from core.models import TimeStampedModel
from parameter.models import CompanyConfig


class Publication(TimeStampedModel):
    """Modèle pour les publications et annonces du système"""
    
    class Type(models.TextChoices):
        PROMOTION = "promotion", _("Promotion")
        NEWS = "news", _("Nouvelle")
        MAINTENANCE = "maintenance", _("Maintenance")
        SECURITY = "security", _("Sécurité")
        EVENT = "event", _("Événement")
        ALERT = "alert", _("Alerte")
        UPDATE = "update", _("Mise à jour")
        OTHER = "other", _("Autre")
    
    class Audience(models.TextChoices):
        ALL = "all", _("Tous les utilisateurs")
        CLIENTS = "clients", _("Clients uniquement")
        STAFF = "staff", _("Personnel uniquement")
        AGENCY = "agency", _("Par agence")
        SPECIFIC = "specific", _("Utilisateurs spécifiques")
        DRIVERS = "drivers", _("Chauffeurs uniquement")
        CASHIERS = "cashiers", _("Caissiers uniquement")
    
    class Status(models.TextChoices):
        DRAFT = "draft", _("Brouillon")
        PUBLISHED = "published", _("Publié")
        ARCHIVED = "archived", _("Archivé")
        EXPIRED = "expired", _("Expiré")
    
    # Contenu
    title = models.CharField(max_length=200, verbose_name=_("Titre"))
    content = models.TextField(verbose_name=_("Contenu"))
    excerpt = models.TextField(max_length=500, blank=True, verbose_name=_("Extrait"))
    publication_type = models.CharField(
        max_length=20, 
        choices=Type.choices, 
        default=Type.NEWS,
        verbose_name=_("Type de publication")
    )
    audience = models.CharField(
        max_length=20, 
        choices=Audience.choices, 
        default=Audience.ALL,
        verbose_name=_("Public cible")
    )
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.DRAFT,
        verbose_name=_("Statut")
    )
    
    # Ciblage
    target_agencies = models.ManyToManyField(
        "locations.Agency", 
        blank=True, 
        related_name="publications",
        verbose_name=_("Agences cibles")
    )
    target_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        blank=True, 
        related_name="targeted_publications",
        verbose_name=_("Utilisateurs cibles")
    )
    
    # Configuration
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    is_featured = models.BooleanField(default=False, verbose_name=_("En vedette"))
    is_pinned = models.BooleanField(default=False, verbose_name=_("Épinglé"))
    start_date = models.DateTimeField(default=timezone.now, verbose_name=_("Date de début"))
    end_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Date de fin"))
    priority = models.PositiveIntegerField(
        default=1, 
        choices=[(1, 'Normal'), (2, 'Important'), (3, 'Urgent')],
        verbose_name=_("Priorité")
    )
    
    # Médias
    image = models.ImageField(upload_to="publications/%Y/%m/", blank=True, null=True, verbose_name=_("Image"))
    attachment = models.FileField(upload_to="publications/attachments/%Y/%m/", blank=True, null=True, verbose_name=_("Pièce jointe"))
    
    # Actions
    action_url = models.URLField(blank=True, verbose_name=_("Lien d'action"))
    action_text = models.CharField(max_length=100, blank=True, verbose_name=_("Texte de l'action"))
    
    # Métriques
    view_count = models.PositiveIntegerField(default=0, verbose_name=_("Nombre de vues"))
    click_count = models.PositiveIntegerField(default=0, verbose_name=_("Nombre de clics"))
    share_count = models.PositiveIntegerField(default=0, verbose_name=_("Nombre de partages"))
    
    # Auteur
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT, 
        related_name="publications",
        verbose_name=_("Auteur")
    )
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True, verbose_name=_("Meta titre"))
    meta_description = models.TextField(max_length=300, blank=True, verbose_name=_("Meta description"))
    slug = models.SlugField(max_length=200, unique=True, blank=True, verbose_name=_("Slug"))
    
    # Données techniques
    notification_sent = models.BooleanField(default=False, verbose_name=_("Notification envoyée"))
    last_notified = models.DateTimeField(null=True, blank=True, verbose_name=_("Dernière notification"))

    class Meta:
        verbose_name = _("Publication")
        verbose_name_plural = _("Publications")
        ordering = ["-is_pinned", "-priority", "-created"]
        indexes = [
            models.Index(fields=['status', 'is_active', 'start_date', 'end_date']),
            models.Index(fields=['publication_type']),
            models.Index(fields=['audience']),
            models.Index(fields=['slug']),
            models.Index(fields=['is_featured']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_publication_type_display()})"
    
    def save(self, *args, **kwargs):
        """Sauvegarde avec génération automatique du slug et gestion du statut"""
        # Génération du slug
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Publication.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Gestion automatique du statut EXPIRED
        if self.status == self.Status.PUBLISHED and self.end_date and self.end_date < timezone.now():
            self.status = self.Status.EXPIRED
        
        super().save(*args, **kwargs)
        
        # Envoi de notification si publication nouvellement publiée
        if (self.status == self.Status.PUBLISHED and 
            not self.notification_sent and 
            self.is_current):
            self.send_publication_notification()

    # =========================================================================
    # MÉTHODES DE GESTION DU STATUT
    # =========================================================================

    def publish(self):
        """Publie la publication"""
        self.status = self.Status.PUBLISHED
        self.start_date = timezone.now()
        self.save()
        self.send_publication_notification()

    def unpublish(self):
        """Dépublie la publication"""
        self.status = self.Status.DRAFT
        self.save()

    def archive(self):
        """Archive la publication"""
        self.status = self.Status.ARCHIVED
        self.save()

    def expire(self):
        """Expire la publication"""
        self.status = self.Status.EXPIRED
        self.save()

    # =========================================================================
    # MÉTHODES DE VÉRIFICATION
    # =========================================================================

    @property
    def is_current(self):
        """Vérifie si la publication est actuellement active"""
        now = timezone.now()
        if not self.is_active or self.status != self.Status.PUBLISHED:
            return False
        if self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True

    @property
    def is_urgent(self):
        """Vérifie si la publication est urgente"""
        return self.priority == 3

    @property
    def days_remaining(self):
        """Nombre de jours restants avant expiration"""
        if not self.end_date:
            return None
        remaining = self.end_date - timezone.now()
        return max(0, remaining.days)

    def is_visible_to_user(self, user):
        """Vérifie si la publication est visible par un utilisateur donné"""
        if not self.is_current:
            return False
        
        # Vérification par audience
        if self.audience == self.Audience.ALL:
            return True
        elif self.audience == self.Audience.CLIENTS and user.is_client():
            return True
        elif self.audience == self.Audience.STAFF and user.is_employee():
            return True
        elif self.audience == self.Audience.DRIVERS and user.is_chauffeur():
            return True
        elif self.audience == self.Audience.CASHIERS and user.is_caissier():
            return True
        elif self.audience == self.Audience.AGENCY and user.agency in self.target_agencies.all():
            return True
        elif self.audience == self.Audience.SPECIFIC and user in self.target_users.all():
            return True
        
        return False

    # =========================================================================
    # MÉTHODES DE MÉTRIQUES
    # =========================================================================

    def increment_view_count(self):
        """Incrémente le compteur de vues"""
        self.view_count += 1
        self.save(update_fields=['view_count'])

    def increment_click_count(self):
        """Incrémente le compteur de clics"""
        self.click_count += 1
        self.save(update_fields=['click_count'])

    def increment_share_count(self):
        """Incrémente le compteur de partages"""
        self.share_count += 1
        self.save(update_fields=['share_count'])

    def get_engagement_rate(self):
        """Calcule le taux d'engagement"""
        if self.view_count == 0:
            return 0
        return (self.click_count / self.view_count) * 100

    # =========================================================================
    # MÉTHODES DE NOTIFICATION
    # =========================================================================

    def send_publication_notification(self):
        """Envoie des notifications pour cette publication"""
        if self.notification_sent:
            return
        
        # Déterminer les utilisateurs cibles
        users = self._get_target_users()
        
        for user in users:
            Notification.objects.create(
                user=user,
                title=f"Nouvelle publication: {self.title}",
                message=self.excerpt or self.content[:200] + "...",
                notification_type=Notification.Type.INFO,
                related_publication=self,
                action_url=self.get_absolute_url(),
                should_send_email=True,
                should_send_sms=False
            )
        
        self.notification_sent = True
        self.last_notified = timezone.now()
        self.save(update_fields=['notification_sent', 'last_notified'])

    def _get_target_users(self):
        """Retourne la liste des utilisateurs cibles"""
        from users.models import User
        
        if self.audience == self.Audience.ALL:
            return User.objects.filter(is_active=True)
        elif self.audience == self.Audience.CLIENTS:
            return User.objects.filter(role=User.Role.CLIENT, is_active=True)
        elif self.audience == self.Audience.STAFF:
            return User.objects.filter(is_employee=True, is_active=True)
        elif self.audience == self.Audience.DRIVERS:
            return User.objects.filter(role=User.Role.CHAUFFEUR, is_active=True)
        elif self.audience == self.Audience.CASHIERS:
            return User.objects.filter(role=User.Role.CAISSIER, is_active=True)
        elif self.audience == self.Audience.AGENCY:
            return User.objects.filter(agency__in=self.target_agencies.all(), is_active=True)
        elif self.audience == self.Audience.SPECIFIC:
            return self.target_users.filter(is_active=True)
        
        return User.objects.none()

    # =========================================================================
    # MÉTHODES D'URL
    # =========================================================================

    def get_absolute_url(self, request=None):
        """URL absolue de la publication"""
        if request:
            return request.build_absolute_uri(f"/publications/{self.slug}/")
        else:
            base_url = getattr(settings, 'FRONTEND_BASE_URL', 'https://votre-site.com')
            return f"{base_url}/publications/{self.slug}/"

    def get_admin_url(self, request=None):
        """URL d'administration de la publication"""
        if request:
            return request.build_absolute_uri(f"/admin/publications/publication/{self.id}/change/")
        else:
            base_url = getattr(settings, 'BACKEND_BASE_URL', 'https://admin.votre-site.com')
            return f"{base_url}/admin/publications/publication/{self.id}/change/"

    # =========================================================================
    # MÉTHODES DE RAPPORT
    # =========================================================================

    @classmethod
    def get_publication_statistics(cls, start_date=None, end_date=None):
        """Statistiques des publications"""
        if not start_date:
            start_date = timezone.now().date() - timezone.timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()

        publications = cls.objects.filter(created__date__range=[start_date, end_date])

        return {
            'total_publications': publications.count(),
            'published': publications.filter(status=cls.Status.PUBLISHED).count(),
            'drafts': publications.filter(status=cls.Status.DRAFT).count(),
            'expired': publications.filter(status=cls.Status.EXPIRED).count(),
            'total_views': publications.aggregate(total=models.Sum('view_count'))['total'] or 0,
            'total_clicks': publications.aggregate(total=models.Sum('click_count'))['total'] or 0,
            'most_viewed': publications.order_by('-view_count').first(),
            'engagement_rate': cls._calculate_overall_engagement(publications),
        }

    @classmethod
    def _calculate_overall_engagement(cls, publications):
        """Calcule le taux d'engagement global"""
        total_views = publications.aggregate(total=models.Sum('view_count'))['total'] or 0
        total_clicks = publications.aggregate(total=models.Sum('click_count'))['total'] or 0
        
        if total_views == 0:
            return 0
        return (total_clicks / total_views) * 100


class Notification(TimeStampedModel):
    """Modèle pour les notifications utilisateur"""
    
    class Type(models.TextChoices):
        INFO = "info", _("Information")
        SUCCESS = "success", _("Succès")
        WARNING = "warning", _("Avertissement")
        ERROR = "error", _("Erreur")
        REMINDER = "reminder", _("Rappel")
        ALERT = "alert", _("Alerte")
        PROMOTION = "promotion", _("Promotion")

    class Status(models.TextChoices):
        UNREAD = "unread", _("Non lu")
        READ = "read", _("Lu")
        DISMISSED = "dismissed", _("Rejeté")
        ARCHIVED = "archived", _("Archivé")

    class Channel(models.TextChoices):
        IN_APP = "in_app", _("Dans l'application")
        EMAIL = "email", _("Email")
        SMS = "sms", _("SMS")
        PUSH = "push", _("Notification push")
        ALL = "all", _("Tous les canaux")

    # Destinataire
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="notifications",
        verbose_name=_("Utilisateur")
    )
    
    # Contenu
    title = models.CharField(max_length=200, verbose_name=_("Titre"))
    message = models.TextField(verbose_name=_("Message"))
    notification_type = models.CharField(
        max_length=20, 
        choices=Type.choices, 
        default=Type.INFO,
        verbose_name=_("Type de notification")
    )
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.UNREAD,
        verbose_name=_("Statut")
    )
    channel = models.CharField(
        max_length=20, 
        choices=Channel.choices, 
        default=Channel.IN_APP,
        verbose_name=_("Canal")
    )
    
    # Références
    related_publication = models.ForeignKey(
        Publication, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="notifications",
        verbose_name=_("Publication liée")
    )
    related_reservation = models.ForeignKey(
        "reservations.Reservation", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="notifications",
        verbose_name=_("Réservation liée")
    )
    related_parcel = models.ForeignKey(
        "parcel.Parcel", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="notifications",
        verbose_name=_("Colis lié")
    )
    related_trip = models.ForeignKey(
        "transport.Trip", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="notifications",
        verbose_name=_("Voyage lié")
    )
    related_support = models.ForeignKey(
        "SupportTicket", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="notifications",
        verbose_name=_("Ticket support lié")
    )
    
    # Actions
    action_url = models.URLField(blank=True, verbose_name=_("Lien d'action"))
    action_label = models.CharField(max_length=100, blank=True, verbose_name=_("Label de l'action"))
    
    # Présentation
    icon = models.CharField(max_length=50, blank=True, verbose_name=_("Icône"))
    image = models.ImageField(upload_to="notifications/%Y/%m/", blank=True, null=True, verbose_name=_("Image"))
    
    # Horodatage
    sent_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Envoyé à"))
    read_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Lu à"))
    dismissed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Rejeté à"))
    
    # Configuration d'envoi
    should_send_email = models.BooleanField(default=False, verbose_name=_("Envoyer par email"))
    should_send_sms = models.BooleanField(default=False, verbose_name=_("Envoyer par SMS"))
    should_send_push = models.BooleanField(default=False, verbose_name=_("Envoyer par push"))
    
    # Statut d'envoi
    email_sent = models.BooleanField(default=False, verbose_name=_("Email envoyé"))
    sms_sent = models.BooleanField(default=False, verbose_name=_("SMS envoyé"))
    push_sent = models.BooleanField(default=False, verbose_name=_("Push envoyé"))
    
    # Données techniques
    notification_id = models.CharField(
        max_length=20, 
        unique=True, 
        editable=False,
        verbose_name=_("ID de notification")
    )

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ["-created"],  
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created']),  
            models.Index(fields=['notification_type']),
            models.Index(fields=['channel']),
            models.Index(fields=['notification_id']),
        ]
    
    def __str__(self):
        return f"{self.user}: {self.title}"

    def save(self, *args, **kwargs):
        """Sauvegarde avec génération automatique de l'ID"""
        if not self.notification_id:
            self.notification_id = self._generate_notification_id()
        super().save(*args, **kwargs)

    def _generate_notification_id(self):
        """Génère un ID de notification unique"""
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            date_part = timezone.now().strftime('%y%m%d')
            random_part = ''.join(secrets.choice(string.digits) for _ in range(6))
            notification_id = f"NOT{date_part}{random_part}"
            
            if not Notification.objects.filter(notification_id=notification_id).exists():
                return notification_id
            attempt += 1
        
        return f"NOT{timezone.now().strftime('%y%m%d')}{str(uuid.uuid4().int)[:8]}"

    # =========================================================================
    # MÉTHODES DE GESTION DU STATUT
    # =========================================================================

    def mark_as_read(self):
        """Marque la notification comme lue"""
        if self.status != self.Status.READ:
            self.status = self.Status.READ
            self.read_at = timezone.now()
            self.save(update_fields=['status', 'read_at'])

    def mark_as_unread(self):
        """Marque la notification comme non lue"""
        self.status = self.Status.UNREAD
        self.read_at = None
        self.save(update_fields=['status', 'read_at'])

    def mark_as_dismissed(self):
        """Marque la notification comme rejetée"""
        self.status = self.Status.DISMISSED
        self.dismissed_at = timezone.now()
        self.save(update_fields=['status', 'dismissed_at'])

    def mark_as_archived(self):
        """Marque la notification comme archivée"""
        self.status = self.Status.ARCHIVED
        self.save(update_fields=['status'])

    # =========================================================================
    # MÉTHODES D'ENVOI
    # =========================================================================

    def send(self):
        """Envoie la notification sur tous les canaux configurés"""
        self.sent_at = timezone.now()
        
        # Envoi email
        if self.should_send_email and not self.email_sent:
            try:
                self._send_email()
                self.email_sent = True
            except Exception as e:
                print(f"Erreur envoi email: {e}")
        
        # Envoi SMS
        if self.should_send_sms and not self.sms_sent:
            try:
                self._send_sms()
                self.sms_sent = True
            except Exception as e:
                print(f"Erreur envoi SMS: {e}")
        
        # Envoi push
        if self.should_send_push and not self.push_sent:
            try:
                self._send_push()
                self.push_sent = True
            except Exception as e:
                print(f"Erreur envoi push: {e}")
        
        self.save()

    def _send_email(self):
        """Envoie la notification par email"""
        
        company_config = CompanyConfig.get_cached_config()
        
        context = {
            'user': self.user,
            'notification': self,
            'company': company_config,
            'action_url': self.action_url or self.get_absolute_url(),
        }
        
        html_message = render_to_string('emails/notification.html', context)
        plain_message = strip_tags(html_message)
        
        subject = f"{company_config.name} - {self.title}"
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=company_config.email,
            recipient_list=[self.user.email],
            html_message=html_message,
            fail_silently=False,
        )

    def _send_sms(self):
        """Envoie la notification par SMS"""
        # Intégration avec service SMS
        message = f"{self.title}: {self.message}"
        if self.action_url:
            message += f" {self.action_url}"
        
        try:
            # Code d'envoi SMS à implémenter
            print(f"SMS to {self.user.phone}: {message}")
            return True
        except Exception as e:
            print(f"Erreur envoi SMS: {e}")
            return False

    def _send_push(self):
        """Envoie la notification push"""
        # Intégration avec service push (Firebase, etc.)
        try:
            # Code d'envoi push à implémenter
            print(f"Push to {self.user}: {self.title}")
            return True
        except Exception as e:
            print(f"Erreur envoi push: {e}")
            return False

    # =========================================================================
    # MÉTHODES UTILITAIRES
    # =========================================================================

    def get_absolute_url(self, request=None):
        """URL absolue de la notification"""
        if request:
            return request.build_absolute_uri(f"/notifications/{self.notification_id}/")
        else:
            base_url = getattr(settings, 'FRONTEND_BASE_URL', 'https://votre-site.com')
            return f"{base_url}/notifications/{self.notification_id}/"

    @property
    def is_sent(self):
        """Vérifie si la notification a été envoyée"""
        return self.sent_at is not None

    @property
    def is_actionable(self):
        """Vérifie si la notification a une action"""
        return bool(self.action_url and self.action_label)

    @classmethod
    def create_reservation_notification(cls, reservation, notification_type=Type.INFO):
        """Crée une notification pour une réservation"""
        if notification_type == cls.Type.SUCCESS:
            title = _("Réservation confirmée")
            message = _("Votre réservation {} a été confirmée").format(reservation.code)
        elif notification_type == cls.Type.REMINDER:
            title = _("Rappel de voyage")
            message = _("N'oubliez pas votre voyage demain à {}").format(
                reservation.schedule.departure_time
            )
        else:
            title = _("Mise à jour réservation")
            message = _("Votre réservation {} a été mise à jour").format(reservation.code)
        
        return cls.objects.create(
            user=reservation.buyer,
            title=title,
            message=message,
            notification_type=notification_type,
            related_reservation=reservation,
            action_url=reservation.get_reservation_url(),
            should_send_email=True
        )


class SupportTicket(TimeStampedModel):
    """Modèle pour les tickets de support"""
    
    class Category(models.TextChoices):
        RESERVATION = "reservation", _("Réservation")
        PAYMENT = "payment", _("Paiement")
        PARCEL = "parcel", _("Colis")
        TRIP = "trip", _("Voyage")
        ACCOUNT = "account", _("Compte utilisateur")
        TECHNICAL = "technical", _("Problème technique")
        COMPLAINT = "complaint", _("Réclamation")
        SUGGESTION = "suggestion", _("Suggestion")
        OTHER = "other", _("Autre")

    class Status(models.TextChoices):
        OPEN = "open", _("Ouvert")
        IN_PROGRESS = "in_progress", _("En cours")
        WAITING_CUSTOMER = "waiting_customer", _("En attente client")
        RESOLVED = "resolved", _("Résolu")
        CLOSED = "closed", _("Fermé")
        CANCELLED = "cancelled", _("Annulé")

    class Priority(models.TextChoices):
        LOW = "low", _("Basse")
        MEDIUM = "medium", _("Moyenne")
        HIGH = "high", _("Haute")
        URGENT = "urgent", _("Urgente")

    # Identifiant
    ticket_id = models.CharField(
        max_length=20, 
        unique=True, 
        verbose_name=_("Numéro de ticket")
    )
    
    # Informations de base
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="support_tickets",
        verbose_name=_("Utilisateur")
    )
    category = models.CharField(
        max_length=20, 
        choices=Category.choices, 
        default=Category.OTHER,
        verbose_name=_("Catégorie")
    )
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.OPEN,
        verbose_name=_("Statut")
    )
    priority = models.CharField(
        max_length=20, 
        choices=Priority.choices, 
        default=Priority.MEDIUM,
        verbose_name=_("Priorité")
    )
    
    # Contenu
    subject = models.CharField(max_length=200, verbose_name=_("Sujet"))
    description = models.TextField(verbose_name=_("Description"))
    attachment = models.FileField(
        upload_to="support/attachments/%Y/%m/", 
        blank=True, 
        null=True,
        verbose_name=_("Pièce jointe")
    )
    
    # Assignation
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="assigned_tickets", 
        limit_choices_to={'role__in': ['admin', 'caissier', 'agency_manager']},
        verbose_name=_("Assigné à")
    )
    agency = models.ForeignKey(
        "locations.Agency", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="support_tickets",
        verbose_name=_("Agence")
    )
    
    # Métriques
    response_time = models.DurationField(null=True, blank=True, verbose_name=_("Temps de réponse"))
    resolution_time = models.DurationField(null=True, blank=True, verbose_name=_("Temps de résolution"))
    satisfaction_rating = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Note de satisfaction")
    )
    satisfaction_comment = models.TextField(blank=True, verbose_name=_("Commentaire satisfaction"))
    
    # Horodatage
    first_response_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Première réponse à"))
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Résolu à"))
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Fermé à"))
    
    # Références
    related_reservation = models.ForeignKey(
        "reservations.Reservation", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="support_tickets",
        verbose_name=_("Réservation liée")
    )
    related_parcel = models.ForeignKey(
        "parcel.Parcel", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="support_tickets",
        verbose_name=_("Colis lié")
    )
    related_trip = models.ForeignKey(
        "transport.Trip", 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="support_tickets",
        verbose_name=_("Voyage lié")
    )

    class Meta:
        verbose_name = _("Ticket de support")
        verbose_name_plural = _("Tickets de support")
        ordering = ["-created"]
        indexes = [
            models.Index(fields=['ticket_id']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['category']),
            models.Index(fields=['priority']),
            models.Index(fields=['assigned_to']),
        ]
    
    def __str__(self):
        return f"{self.ticket_id} - {self.subject}"

    def save(self, *args, **kwargs):
        """Sauvegarde avec génération automatique du ticket_id"""
        if not self.ticket_id:
            self.ticket_id = self._generate_ticket_id()
        super().save(*args, **kwargs)

    def _generate_ticket_id(self):
        """Génère un ID de ticket unique"""
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            date_part = timezone.now().strftime('%y%m%d')
            random_part = ''.join(secrets.choice(string.digits) for _ in range(6))
            ticket_id = f"TKT{date_part}{random_part}"
            
            if not SupportTicket.objects.filter(ticket_id=ticket_id).exists():
                return ticket_id
            attempt += 1
        
        return f"TKT{timezone.now().strftime('%y%m%d')}{str(uuid.uuid4().int)[:8]}"

    # =========================================================================
    # MÉTHODES DE GESTION DU STATUT
    # =========================================================================

    def update_status(self, new_status, user=None, note=""):
        """Met à jour le statut du ticket"""
        old_status = self.status
        self.status = new_status
        
        # Gestion des horodatages
        if new_status == self.Status.IN_PROGRESS and not self.assigned_to:
            self.assigned_to = user
        
        elif new_status == self.Status.RESOLVED and not self.resolved_at:
            self.resolved_at = timezone.now()
            if self.created:
                self.resolution_time = self.resolved_at - self.created
        
        elif new_status == self.Status.CLOSED and not self.closed_at:
            self.closed_at = timezone.now()
        
        self.save()
        
        # Créer un message système
        if user:
            SupportMessage.objects.create(
                ticket=self,
                user=user,
                message=f"Statut changé: {self._get_status_display(old_status)} → {self.get_status_display()} {note}",
                message_type=SupportMessage.MessageType.SYSTEM,
                is_system=True
            )
        
        # Envoyer une notification
        self._send_status_notification(user)

    def assign_to_agent(self, agent, user=None):
        """Assign le ticket à un agent"""
        self.assigned_to = agent
        self.status = self.Status.IN_PROGRESS
        self.save()
        
        if user:
            SupportMessage.objects.create(
                ticket=self,
                user=user,
                message=f"Ticket assigné à {agent.get_full_name()}",
                message_type=SupportMessage.MessageType.SYSTEM,
                is_system=True
            )

    def add_customer_response(self, message, attachment=None):
        """Ajoute une réponse du client"""
        return SupportMessage.objects.create(
            ticket=self,
            user=self.user,
            message=message,
            message_type=SupportMessage.MessageType.CUSTOMER,
            attachment=attachment
        )

    def add_agent_response(self, user, message, attachment=None, is_internal=False):
        """Ajoute une réponse de l'agent"""
        message_obj = SupportMessage.objects.create(
            ticket=self,
            user=user,
            message=message,
            message_type=SupportMessage.MessageType.AGENT,
            attachment=attachment,
            is_internal=is_internal
        )
        
        # Mettre à jour le statut si c'est la première réponse
        if not self.first_response_at:
            self.first_response_at = timezone.now()
            self.response_time = self.first_response_at - self.created
            self.save()
        
        return message_obj

    # =========================================================================
    # MÉTHODES DE NOTIFICATION
    # =========================================================================

    def _send_status_notification(self, changed_by=None):
        """Envoie une notification de changement de statut"""
        title = f"Ticket {self.ticket_id} - {self.get_status_display()}"
        message = f"Votre ticket '{self.subject}' est maintenant {self.get_status_display().lower()}"
        
        Notification.objects.create(
            user=self.user,
            title=title,
            message=message,
            notification_type=Notification.Type.INFO,
            related_support=self,
            action_url=self.get_absolute_url(),
            should_send_email=True
        )

    # =========================================================================
    # MÉTHODES D'URL
    # =========================================================================

    def get_absolute_url(self, request=None):
        """URL absolue du ticket"""
        if request:
            return request.build_absolute_uri(f"/support/tickets/{self.ticket_id}/")
        else:
            base_url = getattr(settings, 'FRONTEND_BASE_URL', 'https://votre-site.com')
            return f"{base_url}/support/tickets/{self.ticket_id}/"

    def get_admin_url(self, request=None):
        """URL d'administration du ticket"""
        if request:
            return request.build_absolute_uri(f"/admin/support/supportticket/{self.id}/change/")
        else:
            base_url = getattr(settings, 'BACKEND_BASE_URL', 'https://admin.votre-site.com')
            return f"{base_url}/admin/support/supportticket/{self.id}/change/"

    # =========================================================================
    # MÉTHODES DE STATISTIQUES
    # =========================================================================

    @property
    def is_overdue(self):
        """Vérifie si le ticket est en retard"""
        if self.status in [self.Status.RESOLVED, self.Status.CLOSED, self.Status.CANCELLED]:
            return False
        
        # Considérer comme en retard après 48 heures sans réponse
        if self.status == self.Status.OPEN and (timezone.now() - self.created).days >= 2:
            return True
        
        # Considérer comme en retard après 24 heures sans activité
        last_message = self.messages.last()
        if last_message and (timezone.now() - last_message.created).days >= 1:
            return True
        
        return False

    @property
    def response_time_display(self):
        """Temps de réponse formaté"""
        if self.response_time:
            total_seconds = int(self.response_time.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}min"
        return "N/A"

    @classmethod
    def get_support_statistics(cls, start_date=None, end_date=None):
        """Statistiques du support"""
        if not start_date:
            start_date = timezone.now().date() - timezone.timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()

        tickets = cls.objects.filter(created__date__range=[start_date, end_date])

        return {
            'total_tickets': tickets.count(),
            'open_tickets': tickets.filter(status=cls.Status.OPEN).count(),
            'in_progress_tickets': tickets.filter(status=cls.Status.IN_PROGRESS).count(),
            'resolved_tickets': tickets.filter(status=cls.Status.RESOLVED).count(),
            'closed_tickets': tickets.filter(status=cls.Status.CLOSED).count(),
            'average_response_time': tickets.exclude(response_time__isnull=True).aggregate(
                avg=models.Avg('response_time')
            )['avg'],
            'satisfaction_rate': tickets.exclude(satisfaction_rating__isnull=True).aggregate(
                avg=models.Avg('satisfaction_rating')
            )['avg'] or 0,
            'most_common_category': tickets.values('category').annotate(
                count=models.Count('id')
            ).order_by('-count').first(),
        }


class SupportMessage(TimeStampedModel):
    """Modèle pour les messages des tickets de support"""
    
    class MessageType(models.TextChoices):
        CUSTOMER = "customer", _("Message client")
        AGENT = "agent", _("Message agent")
        SYSTEM = "system", _("Message système")

    ticket = models.ForeignKey(
        SupportTicket, 
        on_delete=models.CASCADE, 
        related_name="messages",
        verbose_name=_("Ticket")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="support_messages",
        verbose_name=_("Utilisateur")
    )
    message = models.TextField(verbose_name=_("Message"))
    message_type = models.CharField(
        max_length=20, 
        choices=MessageType.choices, 
        default=MessageType.CUSTOMER,
        verbose_name=_("Type de message")
    )
    is_system = models.BooleanField(default=False, verbose_name=_("Message système"))
    is_internal = models.BooleanField(default=False, verbose_name=_("Message interne"))
    
    is_first_response = models.BooleanField(default=False, verbose_name=_("Première réponse"))
    
    attachment = models.FileField(
        upload_to="support/messages/%Y/%m/", 
        blank=True, 
        null=True,
        verbose_name=_("Pièce jointe")
    )
    
    read_by_customer = models.BooleanField(default=False, verbose_name=_("Lu par le client"))
    read_by_agent = models.BooleanField(default=False, verbose_name=_("Lu par l'agent"))

    class Meta:
        verbose_name = _("Message de support")
        verbose_name_plural = _("Messages de support")
        ordering = ["created"]
        indexes = [
            models.Index(fields=['ticket', 'created']),
            models.Index(fields=['message_type']),
        ]
    
    def __str__(self):
        return f"Message #{self.id} - {self.ticket.ticket_id}"

    def save(self, *args, **kwargs):
        """Sauvegarde avec gestion de la première réponse"""
        if not self.pk and self.message_type == self.MessageType.AGENT and not self.is_system:
            existing_agent_messages = SupportMessage.objects.filter(
                ticket=self.ticket,
                message_type=self.MessageType.AGENT,
                is_system=False
            ).exists()
            
            if not existing_agent_messages and not self.ticket.first_response_at:
                self.is_first_response = True
                self.ticket.first_response_at = timezone.now()
                self.ticket.response_time = self.ticket.first_response_at - self.ticket.created
                self.ticket.save()
        
        super().save(*args, **kwargs)
        
        # Marquer comme lu par l'expéditeur
        if self.message_type == self.MessageType.CUSTOMER:
            self.read_by_agent = False
            self.read_by_customer = True
        elif self.message_type == self.MessageType.AGENT:
            self.read_by_agent = True
            self.read_by_customer = False
        
        # Envoyer une notification pour les nouveaux messages
        if not self.is_system and not self.is_internal:
            self._send_message_notification()

    def _send_message_notification(self):
        """Envoie une notification pour un nouveau message"""
        if self.message_type == self.MessageType.CUSTOMER:
            # Notifier les agents
            title = f"Nouveau message - Ticket {self.ticket.ticket_id}"
            message = f"Nouveau message de {self.user.get_full_name()}: {self.message[:100]}..."
            
            # Notifier l'agent assigné ou tous les agents
            if self.ticket.assigned_to:
                users_to_notify = [self.ticket.assigned_to]
            else:
                from users.models import User
                users_to_notify = User.objects.filter(
                    role__in=['admin', 'caissier', 'agency_manager'],
                    is_active=True
                )
            
            for user in users_to_notify:
                Notification.objects.create(
                    user=user,
                    title=title,
                    message=message,
                    notification_type=Notification.Type.INFO,
                    related_support=self.ticket,
                    action_url=self.ticket.get_absolute_url(),
                    should_send_email=True
                )
        
        elif self.message_type == self.MessageType.AGENT:
            # Notifier le client
            title = f"Réponse à votre ticket {self.ticket.ticket_id}"
            message = f"{self.user.get_full_name()} a répondu: {self.message[:100]}..."
            
            Notification.objects.create(
                user=self.ticket.user,
                title=title,
                message=message,
                notification_type=Notification.Type.INFO,
                related_support=self.ticket,
                action_url=self.ticket.get_absolute_url(),
                should_send_email=True
            )

    def mark_as_read_by_customer(self):
        """Marque le message comme lu par le client"""
        self.read_by_customer = True
        self.save(update_fields=['read_by_customer'])

    def mark_as_read_by_agent(self):
        """Marque le message comme lu par l'agent"""
        self.read_by_agent = True
        self.save(update_fields=['read_by_agent'])

    @property
    def is_read(self):
        """Vérifie si le message a été lu par le destinataire"""
        if self.message_type == self.MessageType.CUSTOMER:
            return self.read_by_agent
        elif self.message_type == self.MessageType.AGENT:
            return self.read_by_customer
        return True



# ==================================================
# APPLICATION: parameter
# FICHIER: models.py
# ==================================================

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from django.conf import settings
from core.models import TimeStampedModel


class CompanyConfig(TimeStampedModel):
    """Configuration de la société/entreprise"""
    
    name = models.CharField(max_length=200, verbose_name=_("Nom de l'entreprise"))
    legal_name = models.CharField(max_length=200, blank=True, verbose_name=_("Nom légal"))
    slogan = models.CharField(max_length=300, blank=True, verbose_name=_("Slogan"))
    
    # Logo et branding
    logo = models.ImageField(upload_to="company/", blank=True, null=True, verbose_name=_("Logo principal"))
    logo_light = models.ImageField(upload_to="company/", blank=True, null=True, verbose_name=_("Logo clair"))
    logo_dark = models.ImageField(upload_to="company/", blank=True, null=True, verbose_name=_("Logo sombre"))
    favicon = models.ImageField(upload_to="company/", blank=True, null=True, verbose_name=_("Favicon"))
    
    # Contacts principaux
    phone = models.CharField(max_length=30, verbose_name=_("Téléphone principal"))
    phone_secondary = models.CharField(max_length=30, blank=True, verbose_name=_("Téléphone secondaire"))
    email = models.EmailField(verbose_name=_("Email principal"))
    email_support = models.EmailField(blank=True, verbose_name=_("Email support"))
    email_sales = models.EmailField(blank=True, verbose_name=_("Email commercial"))
    
    # Adresse
    address = models.TextField(verbose_name=_("Adresse principale"))
    city = models.CharField(max_length=100, verbose_name=_("Ville"))
    country = models.CharField(max_length=100, verbose_name=_("Pays"))
    postal_code = models.CharField(max_length=20, blank=True, verbose_name=_("Code postal"))
    
    # Réseaux sociaux
    website = models.URLField(blank=True, verbose_name=_("Site web"))
    facebook = models.URLField(blank=True, verbose_name=_("Facebook"))
    twitter = models.URLField(blank=True, verbose_name=_("Twitter"))
    linkedin = models.URLField(blank=True, verbose_name=_("LinkedIn"))
    instagram = models.URLField(blank=True, verbose_name=_("Instagram"))
    whatsapp = models.CharField(max_length=30, blank=True, verbose_name=_("WhatsApp"))
    
    # Informations légales
    rc_number = models.CharField(max_length=50, blank=True, verbose_name=_("Numéro RC"))
    nif = models.CharField(max_length=50, blank=True, verbose_name=_("Numéro NIF"))
    nis = models.CharField(max_length=50, blank=True, verbose_name=_("Numéro NIS"))
    ai_number = models.CharField(max_length=50, blank=True, verbose_name=_("Numéro AI"))
    
    # Configuration métier
    currency = models.CharField(max_length=10, default="FCFA", verbose_name=_("Devise"))
    timezone = models.CharField(max_length=50, default="Africa/Douala", verbose_name=_("Fuseau horaire"))
    language = models.CharField(max_length=10, default="fr", verbose_name=_("Langue par défaut"))
    
    # Paramètres réservations
    max_seats_per_booking = models.PositiveIntegerField(default=10, verbose_name=_("Nombre maximum de sièges par réservation"))
    booking_expiry_minutes = models.PositiveIntegerField(default=30, verbose_name=_("Délai d'expiration des réservations (minutes)"))
    allow_online_payment = models.BooleanField(default=True, verbose_name=_("Paiement en ligne activé"))
    
    # Paramètres colis
    max_parcel_weight = models.DecimalField(max_digits=6, decimal_places=2, default=50.0, verbose_name=_("Poids maximum des colis (kg)"))
    parcel_insurance_required = models.BooleanField(default=False, verbose_name=_("Assurance colis obligatoire"))
    
    # Paramètres système
    maintenance_mode = models.BooleanField(default=False, verbose_name=_("Mode maintenance"))
    enable_sms_notifications = models.BooleanField(default=True, verbose_name=_("Notifications SMS activées"))
    enable_email_notifications = models.BooleanField(default=True, verbose_name=_("Notifications email activées"))
    
    # Métadonnées SEO
    meta_title = models.CharField(max_length=200, blank=True, verbose_name=_("Meta titre"))
    meta_description = models.TextField(blank=True, verbose_name=_("Meta description"))
    keywords = models.TextField(blank=True, verbose_name=_("Mots-clés"))
    
    class Meta:
        verbose_name = _("Configuration entreprise")
        verbose_name_plural = _("Configurations entreprise")
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # S'assurer qu'il n'y a qu'une seule configuration
        if not self.pk and CompanyConfig.objects.exists():
            # Garder la configuration existante
            existing = CompanyConfig.objects.first()
            self.pk = existing.pk
        
        # Invalider le cache à chaque sauvegarde
        self.clear_cache()
        super().save(*args, **kwargs)
    
    # =========================================================================
    # MÉTHODES DE CACHE - Performances
    # =========================================================================
    
    @classmethod
    def get_cached_config(cls):
        """Récupère la configuration depuis le cache ou la base de données"""
        cache_key = 'company_config'
        config = cache.get(cache_key)
        
        if config is None:
            config = cls.objects.first()
            if not config:
                # Créer une configuration par défaut si elle n'existe pas
                config = cls.create_default_config()
            # Mettre en cache pour 1 heure
            cache.set(cache_key, config, 3600)
        
        return config
    
    def clear_cache(self):
        """Vide le cache de la configuration"""
        cache.delete('company_config')
    
    # =========================================================================
    # MÉTHODES FACTORY - Création facile
    # =========================================================================
    
    @classmethod
    def create_default_config(cls):
        """Crée une configuration par défaut"""
        return cls.objects.create(
            name="G-Travel",
            legal_name="G-Travel SARL",
            slogan="Voyagez en toute sérénité",
            phone="+226 66 60 55 72",
            phone_secondary="+226 60 95 58 60",
            email="contact@gtravel.com",
            email_support="support@gtravel.com",
            email_sales="commercial@gtravel.com",
            address="Rue du Commerce, Ouagadougou",
            city="Ouagadougou",
            country="Burkina Faso",
            postal_code="01 BP 1234",
            website="https://gtravel.com",
            facebook="https://facebook.com/gtravel",
            whatsapp="+22666995588",
            rc_number="RC123456789",
            nif="NIF123456789",
            currency="FCFA",
            timezone="Africa/Ouagadougou",
            language="fr"
        )
    
    @classmethod
    def get_or_create_config(cls):
        """Récupère ou crée la configuration"""
        config = cls.objects.first()
        if not config:
            config = cls.create_default_config()
        return config
    
    # =========================================================================
    # MÉTHODES MÉTIER - Logique commerciale
    # =========================================================================
    
    def can_make_booking(self, number_of_seats=1):
        """Vérifie si une réservation est possible avec le nombre de sièges demandé"""
        return number_of_seats <= self.max_seats_per_booking
    
    def get_booking_expiry_timedelta(self):
        """Retourne le délai d'expiration des réservations sous forme de timedelta"""
        from datetime import timedelta
        return timedelta(minutes=self.booking_expiry_minutes)
    
    def is_parcel_weight_allowed(self, weight):
        """Vérifie si le poids d'un colis est autorisé"""
        return weight <= self.max_parcel_weight
    
    def get_parcel_insurance_info(self):
        """Retourne les informations sur l'assurance colis"""
        return {
            'required': self.parcel_insurance_required,
            'message': "Assurance obligatoire" if self.parcel_insurance_required else "Assurance optionnelle"
        }
    
    # =========================================================================
    # MÉTHODES DE COMMUNICATION - Contacts et support
    # =========================================================================
    
    def get_contact_info(self):
        """Retourne toutes les informations de contact"""
        return {
            'company_name': self.name,
            'phone': self.phone,
            'phone_secondary': self.phone_secondary,
            'email': self.email,
            'email_support': self.email_support or self.email,
            'email_sales': self.email_sales or self.email,
            'address': self.address,
            'city': self.city,
            'country': self.country,
            'postal_code': self.postal_code,
            'whatsapp': self.whatsapp
        }
    
    def get_social_links(self):
        """Retourne tous les liens des réseaux sociaux"""
        social_links = {}
        if self.website:
            social_links['website'] = self.website
        if self.facebook:
            social_links['facebook'] = self.facebook
        if self.twitter:
            social_links['twitter'] = self.twitter
        if self.linkedin:
            social_links['linkedin'] = self.linkedin
        if self.instagram:
            social_links['instagram'] = self.instagram
        if self.whatsapp:
            social_links['whatsapp'] = f"https://wa.me/{self.whatsapp.replace('+', '')}"
        
        return social_links
    
    def get_support_contacts(self):
        """Retourne les contacts de support"""
        return {
            'phone': self.phone_secondary or self.phone,
            'email': self.email_support or self.email,
            'whatsapp': self.whatsapp
        }
    
    # =========================================================================
    # MÉTHODES SYSTÈME - Configuration technique
    # =========================================================================
    
    def is_maintenance_mode(self):
        """Vérifie si le mode maintenance est activé"""
        return self.maintenance_mode
    
    def get_notification_settings(self):
        """Retourne les paramètres de notification"""
        return {
            'sms_enabled': self.enable_sms_notifications,
            'email_enabled': self.enable_email_notifications
        }
    
    def can_send_sms(self):
        """Vérifie si l'envoi de SMS est activé"""
        return self.enable_sms_notifications
    
    def can_send_email(self):
        """Vérifie si l'envoi d'emails est activé"""
        return self.enable_email_notifications
    
    # =========================================================================
    # MÉTHODES DE VALIDATION - Règles métier
    # =========================================================================
    
    def validate_booking_seats(self, number_of_seats):
        """Valide le nombre de sièges pour une réservation"""
        if number_of_seats > self.max_seats_per_booking:
            raise ValueError(
                f"Nombre de sièges ({number_of_seats}) dépasse la limite autorisée ({self.max_seats_per_booking})"
            )
        return True
    
    def validate_parcel_weight(self, weight):
        """Valide le poids d'un colis"""
        if weight > self.max_parcel_weight:
            raise ValueError(
                f"Poids du colis ({weight}kg) dépasse la limite autorisée ({self.max_parcel_weight}kg)"
            )
        return True
    
    # =========================================================================
    # MÉTHODES D'AFFICHAGE - Templates et API
    # =========================================================================
    
    def to_dict(self):
        """Convertit la configuration en dictionnaire pour l'API"""
        return {
            'name': self.name,
            'legal_name': self.legal_name,
            'slogan': self.slogan,
            'contact': self.get_contact_info(),
            'social': self.get_social_links(),
            'business_rules': {
                'max_seats_per_booking': self.max_seats_per_booking,
                'booking_expiry_minutes': self.booking_expiry_minutes,
                'allow_online_payment': self.allow_online_payment,
                'max_parcel_weight': float(self.max_parcel_weight),
                'parcel_insurance_required': self.parcel_insurance_required,
            },
            'system': {
                'maintenance_mode': self.maintenance_mode,
                'enable_sms_notifications': self.enable_sms_notifications,
                'enable_email_notifications': self.enable_email_notifications,
                'currency': self.currency,
                'timezone': self.timezone,
                'language': self.language,
            },
            'seo': {
                'meta_title': self.meta_title,
                'meta_description': self.meta_description,
                'keywords': self.keywords,
            }
        }
    
    def get_context_data(self):
        """Retourne les données pour les templates"""
        return {
            'company': self,
            'contact_info': self.get_contact_info(),
            'social_links': self.get_social_links(),
            'support_contacts': self.get_support_contacts(),
        }
    
    # =========================================================================
    # PROPRIÉTÉS UTILES - Accès rapide
    # =========================================================================
    
    @property
    def full_address(self):
        """Adresse complète formatée"""
        parts = [self.address]
        if self.postal_code:
            parts.append(self.postal_code)
        parts.append(self.city)
        parts.append(self.country)
        return ", ".join(filter(None, parts))
    
    @property
    def primary_contact(self):
        """Contact principal formaté"""
        return f"{self.phone} | {self.email}"
    
    @property
    def business_hours(self):
        """Heures d'ouverture par défaut (à personnaliser)"""
        return "Lundi - Vendredi: 7h00 - 19h00, Samedi: 8h00 - 16h00, Dimanche: Fermé"
    
    @property
    def is_online_payment_available(self):
        """Vérifie si le paiement en ligne est disponible"""
        return self.allow_online_payment and not self.maintenance_mode


class SystemParameter(TimeStampedModel):
    """Paramètres système configurables"""
    
    class Category(models.TextChoices):
        GENERAL = "general", _("Général")
        RESERVATION = "reservation", _("Réservation")
        PAYMENT = "payment", _("Paiement")
        PARCEL = "parcel", _("Colis")
        NOTIFICATION = "notification", _("Notification")
        SECURITY = "security", _("Sécurité")
    
    key = models.CharField(max_length=100, unique=True, verbose_name=_("Clé"))
    value = models.TextField(verbose_name=_("Valeur"))
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL, verbose_name=_("Catégorie"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    data_type = models.CharField(
        max_length=20,
        choices=[
            ('string', 'String'),
            ('integer', 'Entier'),
            ('float', 'Décimal'),
            ('boolean', 'Booléen'),
            ('json', 'JSON'),
        ],
        default='string',
        verbose_name=_("Type de données")
    )
    is_public = models.BooleanField(default=False, verbose_name=_("Public"))
    
    class Meta:
        verbose_name = _("Paramètre système")
        verbose_name_plural = _("Paramètres système")
        ordering = ['category', 'key']
    
    def __str__(self):
        return f"{self.key} = {self.value}"
    
    # =========================================================================
    # MÉTHODES UTILES POUR SystemParameter
    # =========================================================================
    
    def get_typed_value(self):
        """Retourne la valeur convertie dans le bon type"""
        if self.data_type == 'integer':
            return int(self.value)
        elif self.data_type == 'float':
            return float(self.value)
        elif self.data_type == 'boolean':
            return self.value.lower() in ('true', '1', 'yes', 'oui')
        elif self.data_type == 'json':
            import json
            return json.loads(self.value)
        else:  # string
            return self.value
    
    @classmethod
    def get_parameter(cls, key, default=None):
        """Récupère un paramètre par sa clé"""
        try:
            param = cls.objects.get(key=key)
            return param.get_typed_value()
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_parameter(cls, key, value, category='general', description='', data_type='string', is_public=False):
        """Crée ou met à jour un paramètre"""
        param, created = cls.objects.get_or_create(
            key=key,
            defaults={
                'value': str(value),
                'category': category,
                'description': description,
                'data_type': data_type,
                'is_public': is_public
            }
        )
        if not created:
            param.value = str(value)
            param.category = category
            param.description = description
            param.data_type = data_type
            param.is_public = is_public
            param.save()
        
        return param



# ==================================================
# APPLICATION: core
# FICHIER: models.py
# ==================================================

from django.db import models

# Create your models here.
import uuid
import qrcode
import io
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        return super().update(is_deleted=True, deleted=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)

    def all_with_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db)

    def only_deleted(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=True)


class ActiveManager(models.Manager):
    """Manager pour filtrer uniquement les objets actifs (is_active=True)."""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class TimeStampedModel(models.Model):
    """Base : UUID + horodatage + suppression logique."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteManager().all_with_deleted()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, soft=True):
        if soft:
            self.is_deleted = True
            self.deleted = timezone.now()
            self.save(update_fields=["is_deleted", "deleted"])
        else:
            super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.is_deleted = False
        self.deleted = None
        self.save(update_fields=["is_deleted", "deleted"])

    def hard_delete(self):
        super().delete()


class QRCodeMixin(models.Model):
    """Mixin pour générer des QR codes"""
    qr_token = models.CharField(max_length=64, unique=True, blank=True, verbose_name="QR Token")
    qr_image = models.ImageField(upload_to="qrcodes/", blank=True, null=True, verbose_name="QR Code")

    class Meta:
        abstract = True

    def generate_qr_code(self, data=None):
        """Génère un QR code pour l'objet"""
        if not data:
            data = self.qr_token
            
        if not data:
            return
            
        qr_img = qrcode.make(data)
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        filename = f"{self.__class__.__name__.lower()}_{self.id}.png"
        
        self.qr_image.save(filename, ContentFile(buffer.getvalue()), save=False)


