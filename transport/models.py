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