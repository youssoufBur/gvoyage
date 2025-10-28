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