from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.apps import apps  # ← IMPORT AJOUTÉ
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
from datetime import datetime, time, timedelta
from django.db.models import Count, Sum, Avg


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
        
        # Générer un mot de passe temporaire uniquement pour les employés
        temporary_password = None
        if user.is_employee() and not password:
            temporary_password = self.generate_temporary_password()
            password = temporary_password
            
        user.set_password(password)
        user.temporary_password = temporary_password
        
        # ✅ ACTIVATION AUTOMATIQUE POUR LES CLIENTS
        if user.is_client():
            user.is_verified = True
            user.is_active = True
            user.activation_token = None  # Pas de token d'activation pour les clients
            user.activation_token_expires = None
        
        user.save(using=self._db)

        
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)
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
        AGENT = "agent", _("Agent d'Agence")
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

    # Champ temporaire pour stocker le mot de passe temporaire (non persisté en base)
    temporary_password = None

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

    def is_agent(self):
        return self.role == self.Role.AGENT

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
        """Retourne True si l'utilisateur est un employé (pas un client)"""
        return self.role in [
            self.Role.CHAUFFEUR, self.Role.CAISSIER, self.Role.LIVREUR, self.Role.AGENT,
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
            self.Role.AGENT: 1,
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
        elif self.is_manager() or self.is_agent():
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
        elif self.is_agency_manager() or self.is_agent():
            return {'agency': self.agency}
        else:
            return {'agency': self.agency} if self.agency else {}

    def _get_client_stats(self, date_filter):
        """Statistiques pour les clients"""
        try:
            Ticket = apps.get_model('reservations', 'Ticket')
            Parcel = apps.get_model('parcel', 'Parcel')
            
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
        except (LookupError, ImportError):
            return {
                'total_tickets': 0,
                'active_tickets': 0,
                'total_spent': 0,
                'total_parcels': 0,
                'pending_parcels': 0,
                'delivered_parcels': 0,
            }

    def _get_chauffeur_stats(self, date_filter):
        """Statistiques pour les chauffeurs"""
        try:
            Trip = apps.get_model('transport', 'Trip')
            
            trips = Trip.objects.filter(driver=self, **date_filter)
            
            return {
                'total_trips': trips.count(),
                'completed_trips': trips.filter(status='completed').count(),
                'in_progress_trips': trips.filter(status__in=['boarding', 'in_progress']).count(),
                'total_passengers': trips.aggregate(total=Count('passengers'))['total'] or 0,
                'on_time_rate': self._calculate_on_time_rate(trips),
            }
        except (LookupError, ImportError):
            return {
                'total_trips': 0,
                'completed_trips': 0,
                'in_progress_trips': 0,
                'total_passengers': 0,
                'on_time_rate': 0,
            }

    def _get_caissier_stats(self, date_filter):
        """Statistiques pour les caissiers"""
        try:
            Payment = apps.get_model('reservations', 'Payment')
            
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
        except (LookupError, ImportError):
            return {
                'total_payments': 0,
                'successful_payments': 0,
                'today_payments': 0,
                'total_revenue': 0,
                'today_revenue': 0,
                'cash_revenue': 0,
                'mobile_revenue': 0,
            }

    def _get_livreur_stats(self, date_filter):
        """Statistiques pour les livreurs"""
        try:
            Parcel = apps.get_model('parcel', 'Parcel')
            
            parcels = Parcel.objects.filter(
                last_handled_by=self,
                **date_filter
            )
            
            deliveries = parcels.filter(
                status__in=['out_for_delivery', 'delivered']
            )
            
            return {
                'total_deliveries': deliveries.count(),
                'completed_deliveries': deliveries.filter(status='delivered').count(),
                'pending_deliveries': deliveries.filter(status='out_for_delivery').count(),
                'average_delivery_time': self._calculate_avg_delivery_time(deliveries),
                'customer_rating': self._calculate_avg_rating(deliveries),
            }
        except (LookupError, ImportError):
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
            completed_deliveries = deliveries.filter(status='delivered')
            
            if not completed_deliveries:
                return 0
            
            total_seconds = 0
            count = 0
            
            for parcel in completed_deliveries:
                if hasattr(parcel, 'actual_delivery') and parcel.actual_delivery and parcel.created:
                    delivery_time = parcel.actual_delivery - parcel.created
                    total_seconds += delivery_time.total_seconds()
                    count += 1
            
            return total_seconds / count / 3600 if count > 0 else 0
        except (AttributeError, TypeError):
            return 0

    def _calculate_avg_rating(self, deliveries):
        """Calcule la note moyenne des clients"""
        # À implémenter selon votre logique métier
        # Pour l'instant, retourner une valeur par défaut
        return 4.5

    def _get_manager_stats(self, date_filter, agency_filter):
        """Statistiques pour les managers et agents"""
        try:
            Payment = apps.get_model('reservations', 'Payment')
            Trip = apps.get_model('transport', 'Trip')
            TripEvent = apps.get_model('transport', 'TripEvent')
            Ticket = apps.get_model('reservations', 'Ticket')
            Parcel = apps.get_model('parcel', 'Parcel')
            
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
        except (LookupError, ImportError):
            return {
                'financial': {},
                'operations': {},
                'incidents': {},
                'parcels': {}
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
        try:
            Payment = apps.get_model('reservations', 'Payment')
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
        except (LookupError, ImportError):
            return {
                'period': {'start': start_date, 'end': end_date},
                'report_type': report_type,
                'summary': {'total_revenue': 0, 'total_transactions': 0, 'average_transaction': 0},
                'breakdown': {'by_payment_method': {}, 'by_agency': {}}
            }

    def get_incident_analytics(self, start_date, end_date):
        """Retourne l'analytique des incidents"""
        try:
            TripEvent = apps.get_model('transport', 'TripEvent')
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
        except (LookupError, ImportError):
            return {
                'total_incidents': 0,
                'by_type': {},
                'by_severity': {},
                'trends': {'weekly_trend': 'stable', 'comparison_previous_period': 0}
            }

    def _categorize_incidents(self, incidents):
        """Catégorise les incidents par sévérité"""
        return {
            'minor': incidents.filter(event_type='incident').count(),
            'major': incidents.filter(event_type='accident').count()
        }

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
        """Retourne True si l'utilisateur a besoin d'activation"""
        return bool(self.activation_token) and not self.is_verified

    @property
    def can_login(self):
        """Retourne True si l'utilisateur peut se connecter"""
        return self.is_active and self.is_verified and not self.needs_activation

    @property
    def activation_status(self):
        """Retourne le statut d'activation"""
        if self.is_client():
            return "auto_activated"
        elif self.is_verified:
            return "activated"
        elif self.activation_token:
            return "pending_activation"
        else:
            return "not_activated"

    def clean(self):
        super().clean()
        
        # ✅ CORRECTION : Seuls les employés ont besoin d'agence et d'email
        if self.is_employee() and not self.agency:
            raise ValidationError(_("Les {}s doivent être associés à une agence.").format(self.get_role_display()))
        
        if self.is_employee() and not self.email:
            raise ValidationError(_("Les {}s doivent avoir une adresse email.").format(self.get_role_display()))

    def save(self, *args, **kwargs):
        is_new_user = not self.pk
        
        # ✅ LOGIQUE D'ACTIVATION CORRIGÉE
        if is_new_user:
            if self.is_client():
                # Clients : activation automatique
                self.is_verified = True
                self.is_active = True
                self.activation_token = None
                self.activation_token_expires = None
            elif self.is_employee():
                # Employés : besoin d'activation
                if not self.activation_token:
                    self.activation_token = str(uuid.uuid4())
                    self.activation_token_expires = timezone.now() + timezone.timedelta(hours=24)
                
                if not self.employee_id:
                    self.employee_id = self._generate_employee_id()

        super().save(*args, **kwargs)
        
        # ✅ ENVOI D'EMAIL UNIQUEMENT POUR LES EMPLOYÉS
        if (is_new_user and self.is_employee() and self.activation_token and
            not getattr(self, '_activation_email_sent', False)):
            
            temporary_password = getattr(self, 'temporary_password', None)
            self._send_activation_email(temporary_password)
            self._activation_email_sent = True

    def _generate_employee_id(self):
        prefix = {
            self.Role.CHAUFFEUR: 'CH', self.Role.CAISSIER: 'CA', 
            self.Role.LIVREUR: 'LV', self.Role.AGENT: 'AG',
            self.Role.AGENCY_MANAGER: 'AM', self.Role.CENTRAL_MANAGER: 'CM', 
            self.Role.NATIONAL_MANAGER: 'NM', self.Role.DG: 'DG', 
            self.Role.ADMIN: 'AD'
        }.get(self.role, 'EM')
        
        timestamp = timezone.now().strftime('%y%m%d')
        random_part = str(uuid.uuid4().int)[:6]
        return f"{prefix}{timestamp}{random_part}"
    
    def _send_activation_email(self, temporary_password=None):
        """Envoie un email d'activation aux employés"""
        if not self.email:
            return
            
        subject = _("Activation de votre compte employé")
        context = {
            'user': self,
            'activation_link': f"{settings.FRONTEND_URL}/activate/{self.activation_token}/",
            'temporary_password': temporary_password,
        }
        html_message = render_to_string('emails/employee_activation.html', context)
        plain_message = strip_tags(html_message)
        
        try:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [self.email],
                html_message=html_message,
                fail_silently=False,
            )
        except Exception as e:
            print(f"❌ Erreur envoi email: {e}")