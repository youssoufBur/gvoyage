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