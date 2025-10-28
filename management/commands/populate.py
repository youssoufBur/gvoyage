# management/commands/populate.py
import os
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db import transaction

from location.models import Country, City, Agency
from user.models import User
from transport.models import Route, Leg, Schedule, Vehicle, Trip
from reservation.models import Reservation, Ticket, Payment
from parcel.models import Parcel, TrackingEvent
from notification.models import Announcement, Notification

class Command(BaseCommand):
    help = 'Peuple la base de données avec des données de démonstration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Supprimer les données existantes avant de peupler',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Début du peuplement de la base de données...'))
        
        if options['clear']:
            self.clear_data()
        
        with transaction.atomic():
            self.create_countries_cities()
            self.create_agencies()
            self.create_users()
            self.create_routes_legs()
            self.create_schedules()
            self.create_vehicles()
            self.create_trips()
            self.create_reservations_tickets()
            self.create_parcels()
            self.create_announcements_notifications()
        
        self.stdout.write(self.style.SUCCESS('Peuplement terminé avec succès!'))

    def clear_data(self):
        """Supprime toutes les données existantes"""
        self.stdout.write('Nettoyage des données existantes...')
        models = [
            Notification, Announcement, TrackingEvent, Parcel,
            Payment, Ticket, Reservation, TripPassenger, TripEvent, Trip,
            Vehicle, Schedule, Leg, Route, User, Agency, City, Country
        ]
        
        for model in models:
            try:
                model.objects.all().delete()
                self.stdout.write(f'  - {model.__name__} effacé')
            except:
                pass

    def create_countries_cities(self):
        """Crée les pays et villes"""
        self.stdout.write('Création des pays et villes...')
        
        # Pays
        countries_data = [
            {'name': 'Côte d\'Ivoire', 'code': 'CI'},
            {'name': 'Burkina Faso', 'code': 'BF'},
            {'name': 'Mali', 'code': 'ML'},
            {'name': 'Ghana', 'code': 'GH'},
            {'name': 'Guinée', 'code': 'GN'},
        ]
        
        countries = {}
        for data in countries_data:
            country, created = Country.objects.get_or_create(**data)
            countries[data['code']] = country
        
        # Villes par pays
        cities_data = {
            'CI': [
                'Abidjan', 'Bouaké', 'Daloa', 'Korhogo', 'San-Pédro', 
                'Yamoussoukro', 'Divo', 'Gagnoa', 'Man', 'Abengourou'
            ],
            'BF': [
                'Ouagadougou', 'Bobo-Dioulasso', 'Koudougou', 'Banfora', 
                'Ouahigouya', 'Dédougou', 'Kaya', 'Tenkodogo', 'Fada N\'Gourma'
            ],
            'ML': [
                'Bamako', 'Sikasso', 'Mopti', 'Koutiala', 'Ségou', 
                'Gao', 'Kayes', 'Kati', 'Kita', 'Niono'
            ],
            'GH': [
                'Accra', 'Kumasi', 'Tamale', 'Takoradi', 'Ashaiman',
                'Cape Coast', 'Tema', 'Madina', 'Koforidua', 'Wa'
            ],
            'GN': [
                'Conakry', 'Nzérékoré', 'Kankan', 'Kindia', 'Labé',
                'Mamou', 'Boké', 'Faranah', 'Kissidougou', 'Macenta'
            ]
        }
        
        self.cities = {}
        for country_code, city_names in cities_data.items():
            country = countries[country_code]
            for city_name in city_names:
                city, created = City.objects.get_or_create(
                    name=city_name,
                    country=country
                )
                self.cities[city_name] = city
                self.stdout.write(f'  - {city_name} ({country_code}) créée')

    def create_agencies(self):
        """Crée les agences"""
        self.stdout.write('Création des agences...')
        
        agencies_data = [
            # Abidjan - Agence nationale
            {
                'name': 'Siège National Abidjan',
                'code': 'ABJ_NAT',
                'city': self.cities['Abidjan'],
                'level': Agency.Level.NATIONAL,
                'type': Agency.Type.SERVICE,
                'address': 'Plateau, Avenue Chardy, Immeuble CCIA',
                'phone': '+225 27 20 21 22 23',
                'email': 'direction@stm-transport.ci'
            },
            # Agences centrales
            {
                'name': 'Gare Routière d\'Abidjan',
                'code': 'ABJ_CENT',
                'city': self.cities['Abidjan'],
                'level': Agency.Level.CENTRAL,
                'type': Agency.Type.DEPARTURE,
                'address': 'Adjamé, Gare Routière BP 1234',
                'phone': '+225 27 20 21 24 25',
                'email': 'abidjan@stm-transport.ci'
            },
            {
                'name': 'Gare de Ouagadougou',
                'code': 'OUA_CENT',
                'city': self.cities['Ouagadougou'],
                'level': Agency.Level.CENTRAL,
                'type': Agency.Type.DEPARTURE,
                'address': 'Centre-ville, Avenue de la Nation',
                'phone': '+226 25 30 31 32',
                'email': 'ouaga@stm-transport.bf'
            },
            {
                'name': 'Gare de Bamako',
                'code': 'BAM_CENT',
                'city': self.cities['Bamako'],
                'level': Agency.Level.CENTRAL,
                'type': Agency.Type.DEPARTURE,
                'address': 'Badalabougou, Route de Koulouba',
                'phone': '+223 20 21 22 23',
                'email': 'bamako@stm-transport.ml'
            },
            # Agences locales
            {
                'name': 'Agence Yopougon',
                'code': 'ABJ_YOP',
                'city': self.cities['Abidjan'],
                'level': Agency.Level.LOCAL,
                'type': Agency.Type.SALES,
                'address': 'Yopougon, Rue du Commerce',
                'phone': '+225 27 20 21 26 27',
                'email': 'yopougon@stm-transport.ci'
            },
            {
                'name': 'Agence Cocody',
                'code': 'ABJ_COC',
                'city': self.cities['Abidjan'],
                'level': Agency.Level.LOCAL,
                'type': Agency.Type.SALES,
                'address': 'Cocody, 2 Plateaux',
                'phone': '+225 27 20 21 28 29',
                'email': 'cocody@stm-transport.ci'
            },
            {
                'name': 'Agence Bobo-Dioulasso',
                'code': 'BOB_LOC',
                'city': self.cities['Bobo-Dioulasso'],
                'level': Agency.Level.LOCAL,
                'type': Agency.Type.ARRIVAL,
                'address': 'Centre-ville, Avenue de la Révolution',
                'phone': '+226 20 97 00 00',
                'email': 'bobo@stm-transport.bf'
            },
        ]
        
        self.agencies = {}
        for data in agencies_data:
            parent = None
            if data['level'] == Agency.Level.LOCAL:
                # Associer les agences locales à leur agence centrale
                if 'ABJ' in data['code']:
                    parent = Agency.objects.get(code='ABJ_CENT')
                elif 'BOB' in data['code']:
                    parent = Agency.objects.get(code='OUA_CENT')
            
            agency = Agency.objects.create(
                parent_agency=parent,
                **{k: v for k, v in data.items() if k != 'parent'}
            )
            self.agencies[data['code']] = agency
            self.stdout.write(f'  - {agency.name} créée')

    def create_users(self):
        """Crée les utilisateurs"""
        self.stdout.write('Création des utilisateurs...')
        
        # Administrateur
        admin = User.objects.create_user(
            phone='+2250700000000',
            password='admin123',
            full_name='Admin System',
            email='admin@stm-transport.ci',
            role='admin',
            is_verified=True
        )
        
        # Chauffeurs
        drivers_data = [
            {
                'phone': '+2250701010101',
                'full_name': 'Kouame Yao',
                'agency': self.agencies['ABJ_CENT'],
                'role': 'chauffeur'
            },
            {
                'phone': '+2250702020202',
                'full_name': 'Jean Traoré',
                'agency': self.agencies['ABJ_CENT'],
                'role': 'chauffeur'
            },
            {
                'phone': '+2267601010101',
                'full_name': 'Moussa Sawadogo',
                'agency': self.agencies['OUA_CENT'],
                'role': 'chauffeur'
            },
        ]
        
        self.drivers = []
        for data in drivers_data:
            driver = User.objects.create_user(
                password='driver123',
                is_verified=True,
                **data
            )
            self.drivers.append(driver)
            self.stdout.write(f'  - Chauffeur {driver.full_name} créé')
        
        # Caissiers
        cashiers_data = [
            {
                'phone': '+2250703030303',
                'full_name': 'Aïcha Diarra',
                'agency': self.agencies['ABJ_CENT'],
                'role': 'caissier'
            },
            {
                'phone': '+2250704040404',
                'full_name': 'Paul Aké',
                'agency': self.agencies['ABJ_YOP'],
                'role': 'caissier'
            },
        ]
        
        self.cashiers = []
        for data in cashiers_data:
            cashier = User.objects.create_user(
                password='cashier123',
                is_verified=True,
                **data
            )
            self.cashiers.append(cashier)
            self.stdout.write(f'  - Caissier {cashier.full_name} créé')
        
        # Clients
        clients_data = [
            {
                'phone': '+2250505050505',
                'full_name': 'Marie Koné',
                'email': 'marie.kone@email.ci',
                'gender': 'female',
                'role': 'client'
            },
            {
                'phone': '+2250506060606',
                'full_name': 'Mohamed Sylla',
                'email': 'mohamed.sylla@email.ci',
                'gender': 'male',
                'role': 'client'
            },
            {
                'phone': '+2250507070707',
                'full_name': 'Fatou Bamba',
                'email': 'fatou.bamba@email.ci',
                'gender': 'female',
                'role': 'client'
            },
            {
                'phone': '+2267605050505',
                'full_name': 'Ibrahim Ouedraogo',
                'email': 'ibrahim.ouedraogo@email.bf',
                'gender': 'male',
                'role': 'client'
            },
        ]
        
        self.clients = []
        for data in clients_data:
            client = User.objects.create_user(
                password='client123',
                is_verified=True,
                **data
            )
            self.clients.append(client)
            self.stdout.write(f'  - Client {client.full_name} créé')
        
        self.admin_user = admin

    def create_routes_legs(self):
        """Crée les routes et les trajets"""
        self.stdout.write('Création des routes et trajets...')
        
        routes_data = [
            {
                'code': 'ABJ_OUA',
                'origin': self.cities['Abidjan'],
                'destination': self.cities['Ouagadougou'],
                'distance_km': 1100,
                'agency': self.agencies['ABJ_CENT']
            },
            {
                'code': 'ABJ_BAM',
                'origin': self.cities['Abidjan'],
                'destination': self.cities['Bamako'],
                'distance_km': 1200,
                'agency': self.agencies['ABJ_CENT']
            },
            {
                'code': 'OUA_BAM',
                'origin': self.cities['Ouagadougou'],
                'destination': self.cities['Bamako'],
                'distance_km': 900,
                'agency': self.agencies['OUA_CENT']
            },
            {
                'code': 'ABJ_BOU',
                'origin': self.cities['Abidjan'],
                'destination': self.cities['Bouaké'],
                'distance_km': 350,
                'agency': self.agencies['ABJ_CENT']
            },
        ]
        
        self.routes = {}
        for data in routes_data:
            route = Route.objects.create(**data)
            self.routes[data['code']] = route
            self.stdout.write(f'  - Route {route.code} créée')
        
        # Création des legs (segments de route)
        legs_data = [
            # Abidjan -> Ouagadougou avec escales
            {
                'route': self.routes['ABJ_OUA'],
                'origin': self.cities['Abidjan'],
                'destination': self.cities['Bouaké'],
                'order': 1,
                'price': 5000,
                'duration_minutes': 240
            },
            {
                'route': self.routes['ABJ_OUA'],
                'origin': self.cities['Bouaké'],
                'destination': self.cities['Korhogo'],
                'order': 2,
                'price': 4000,
                'duration_minutes': 180
            },
            {
                'route': self.routes['ABJ_OUA'],
                'origin': self.cities['Korhogo'],
                'destination': self.cities['Ouagadougou'],
                'order': 3,
                'price': 6000,
                'duration_minutes': 300
            },
            # Abidjan -> Bouaké (direct)
            {
                'route': self.routes['ABJ_BOU'],
                'origin': self.cities['Abidjan'],
                'destination': self.cities['Bouaké'],
                'order': 1,
                'price': 5000,
                'duration_minutes': 240
            },
        ]
        
        self.legs = []
        for data in legs_data:
            leg = Leg.objects.create(**data)
            self.legs.append(leg)
            self.stdout.write(f'  - Leg {leg.origin} -> {leg.destination} créé')

    def create_schedules(self):
        """Crée les horaires"""
        self.stdout.write('Création des horaires...')
        
        schedules_data = [
            {
                'leg': self.legs[0],  # ABJ -> Bouaké
                'agency': self.agencies['ABJ_CENT'],
                'departure_time': '06:00',
                'days_of_week': 'daily'
            },
            {
                'leg': self.legs[0],
                'agency': self.agencies['ABJ_CENT'],
                'departure_time': '14:00',
                'days_of_week': 'daily'
            },
            {
                'leg': self.legs[1],  # Bouaké -> Korhogo
                'agency': self.agencies['ABJ_CENT'],
                'departure_time': '12:00',
                'days_of_week': 'mon,wed,fri,sun'
            },
            {
                'leg': self.legs[3],  # ABJ -> Bouaké direct
                'agency': self.agencies['ABJ_CENT'],
                'departure_time': '08:00',
                'days_of_week': 'daily'
            },
        ]
        
        self.schedules = []
        for data in schedules_data:
            schedule = Schedule.objects.create(**data)
            self.schedules.append(schedule)
            self.stdout.write(f'  - Schedule {schedule.departure_time} créé')

    def create_vehicles(self):
        """Crée les véhicules"""
        self.stdout.write('Création des véhicules...')
        
        vehicles_data = [
            {
                'plate': 'CI-1234-AB',
                'capacity': 50,
                'type': 'bus',
                'agency': self.agencies['ABJ_CENT']
            },
            {
                'plate': 'CI-5678-CD',
                'capacity': 35,
                'type': 'minibus',
                'agency': self.agencies['ABJ_CENT']
            },
            {
                'plate': 'BF-9012-EF',
                'capacity': 50,
                'type': 'bus',
                'agency': self.agencies['OUA_CENT']
            },
            {
                'plate': 'CI-3456-GH',
                'capacity': 28,
                'type': 'minibus',
                'agency': self.agencies['ABJ_YOP']
            },
        ]
        
        self.vehicles = []
        for data in vehicles_data:
            vehicle = Vehicle.objects.create(**data)
            self.vehicles.append(vehicle)
            self.stdout.write(f'  - Véhicule {vehicle.plate} créé')

    def create_trips(self):
        """Crée les voyages"""
        self.stdout.write('Création des voyages...')
        
        # Dates pour les voyages
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        trips_data = [
            {
                'schedule': self.schedules[0],  # ABJ -> Bouaké 06:00
                'agency': self.agencies['ABJ_CENT'],
                'vehicle': self.vehicles[0],
                'driver': self.drivers[0],
                'departure_dt': timezone.make_aware(datetime.combine(today, datetime.strptime('06:00', '%H:%M').time())),
                'status': 'completed'
            },
            {
                'schedule': self.schedules[0],  # ABJ -> Bouaké 06:00 (demain)
                'agency': self.agencies['ABJ_CENT'],
                'vehicle': self.vehicles[1],
                'driver': self.drivers[1],
                'departure_dt': timezone.make_aware(datetime.combine(tomorrow, datetime.strptime('06:00', '%H:%M').time())),
                'status': 'boarding'
            },
            {
                'schedule': self.schedules[1],  # ABJ -> Bouaké 14:00
                'agency': self.agencies['ABJ_CENT'],
                'vehicle': self.vehicles[0],
                'driver': self.drivers[0],
                'departure_dt': timezone.make_aware(datetime.combine(today, datetime.strptime('14:00', '%H:%M').time())),
                'status': 'in_progress'
            },
            {
                'schedule': self.schedules[3],  # ABJ -> Bouaké direct 08:00
                'agency': self.agencies['ABJ_CENT'],
                'vehicle': self.vehicles[2],
                'driver': self.drivers[0],
                'departure_dt': timezone.make_aware(datetime.combine(tomorrow, datetime.strptime('08:00', '%H:%M').time())),
                'status': 'planned'
            },
        ]
        
        self.trips = []
        for data in trips_data:
            trip = Trip.objects.create(**data)
            self.trips.append(trip)
            self.stdout.write(f'  - Trip {trip} créé')

    def create_reservations_tickets(self):
        """Crée les réservations et tickets"""
        self.stdout.write('Création des réservations et tickets...')
        
        reservations_data = [
            {
                'buyer': self.clients[0],
                'schedule': self.schedules[0],
                'travel_date': timezone.now().date() - timedelta(days=1),
                'total_seats': 2,
                'total_price': 10000,
                'status': 'paid'
            },
            {
                'buyer': self.clients[1],
                'schedule': self.schedules[0],
                'travel_date': timezone.now().date(),
                'total_seats': 1,
                'total_price': 5000,
                'status': 'paid'
            },
            {
                'buyer': self.clients[2],
                'schedule': self.schedules[3],
                'travel_date': timezone.now().date() + timedelta(days=1),
                'total_seats': 3,
                'total_price': 15000,
                'status': 'pending'
            },
        ]
        
        self.reservations = []
        for data in reservations_data:
            reservation = Reservation.objects.create(**data)
            self.reservations.append(reservation)
            self.stdout.write(f'  - Réservation {reservation.code} créée')
            
            # Créer les tickets pour cette réservation
            for i in range(data['total_seats']):
                ticket = Ticket.objects.create(
                    reservation=reservation,
                    trip=self.trips[0] if reservation.travel_date == timezone.now().date() - timedelta(days=1) else None,
                    buyer=reservation.buyer,
                    passenger_name=f"{reservation.buyer.full_name} {i+1}",
                    passenger_phone=reservation.buyer.phone,
                    seat_number=i + 1,
                    status='confirmed' if reservation.status == 'paid' else 'confirmed'
                )
                self.stdout.write(f'    - Ticket {ticket.passenger_name} créé')
            
            # Créer le paiement pour les réservations payées
            if reservation.status == 'paid':
                payment = Payment.objects.create(
                    reservation=reservation,
                    method='cash',
                    amount=reservation.total_price,
                    status='completed',
                    agency=self.agencies['ABJ_CENT'],
                    paid_at=reservation.created_at + timedelta(hours=1)
                )
                self.stdout.write(f'    - Paiement {payment.amount} FCFA créé')

    def create_parcels(self):
        """Crée les colis"""
        self.stdout.write('Création des colis...')
        
        parcels_data = [
            {
                'sender': self.clients[0],
                'receiver_name': 'Koffi N\'Guessan',
                'receiver_phone': '+2250801010101',
                'origin': self.cities['Abidjan'],
                'destination': self.cities['Bouaké'],
                'category': 'medium',
                'weight_kg': 5.5,
                'price': 7500,
                'status': 'delivered',
                'current_city': self.cities['Bouaké'],
                'current_agency': self.agencies['ABJ_CENT'],
                'requires_signature': True,
                'delivery_proof': 'Signature: Koffi N',
                'last_handled_by': self.cashiers[0]
            },
            {
                'sender': self.clients[1],
                'receiver_name': 'Aminata Bamba',
                'receiver_phone': '+2267002020202',
                'origin': self.cities['Abidjan'],
                'destination': self.cities['Ouagadougou'],
                'category': 'small',
                'weight_kg': 1.2,
                'price': 12000,
                'status': 'at_agency',
                'current_city': self.cities['Ouagadougou'],
                'current_agency': self.agencies['OUA_CENT'],
                'requires_signature': False,
                'last_handled_by': self.cashiers[0]
            },
            {
                'sender': self.clients[2],
                'receiver_name': 'Sékou Traoré',
                'receiver_phone': '+2250703030303',
                'origin': self.cities['Abidjan'],
                'destination': self.cities['Bamako'],
                'category': 'large',
                'weight_kg': 25.0,
                'price': 35000,
                'status': 'loaded',
                'current_city': self.cities['Bouaké'],
                'current_agency': self.agencies['ABJ_CENT'],
                'current_trip': self.trips[2],
                'requires_signature': True,
                'last_handled_by': self.drivers[0]
            },
        ]
        
        self.parcels = []
        for data in parcels_data:
            parcel = Parcel.objects.create(**data)
            self.parcels.append(parcel)
            self.stdout.write(f'  - Colis {parcel.tracking_code} créé')
            
            # Créer l'historique de tracking
            status_events = {
                'created': (Parcel.Status.CREATED, "Colis enregistré"),
                'loaded': (Parcel.Status.LOADED, "Colis chargé dans le véhicule"),
                'at_agency': (Parcel.Status.AT_AGENCY, "Colis arrivé à l'agence"),
                'delivered': (Parcel.Status.DELIVERED, "Colis livré au destinataire"),
            }
            
            current_status = data['status']
            for event_name, (status, note) in status_events.items():
                if (current_status == 'delivered' and event_name in ['created', 'loaded', 'at_agency', 'delivered']) or \
                   (current_status == 'at_agency' and event_name in ['created', 'loaded', 'at_agency']) or \
                   (current_status == 'loaded' and event_name in ['created', 'loaded']) or \
                   (current_status == 'created' and event_name in ['created']):
                    
                    TrackingEvent.objects.create(
                        parcel=parcel,
                        event=status,
                        status=status,
                        city=parcel.current_city,
                        agency=parcel.current_agency,
                        trip=parcel.current_trip,
                        actor=parcel.last_handled_by,
                        note=note,
                        ts=parcel.created_at + timedelta(hours=1) if event_name != 'created' else parcel.created_at
                    )

    def create_announcements_notifications(self):
        """Crée les annonces et notifications"""
        self.stdout.write('Création des annonces et notifications...')
        
        announcements_data = [
            {
                'title': 'Promotion Spéciale Été 2024',
                'content': 'Bénéficiez de 20% de réduction sur tous vos voyages jusqu\'au 31 août 2024. Code promo: ETE2024',
                'announcement_type': 'promotion',
                'audience': 'all',
                'is_active': True,
                'start_date': timezone.now() - timedelta(days=2),
                'end_date': timezone.now() + timedelta(days=30),
                'priority': 2,
                'action_url': '/promotions',
                'action_text': 'Voir les promotions',
                'created_by': self.admin_user
            },
            {
                'title': 'Maintenance Système',
                'content': 'Le système sera en maintenance le samedi 15 juin de 02h00 à 06h00. Désolé pour la gêne occasionnée.',
                'announcement_type': 'maintenance',
                'audience': 'all',
                'is_active': True,
                'start_date': timezone.now() - timedelta(days=1),
                'end_date': timezone.now() + timedelta(days=5),
                'priority': 3,
                'created_by': self.admin_user
            },
            {
                'title': 'Nouvelle Ligne Abidjan - Accra',
                'content': 'Nous sommes heureux de vous annoncer l\'ouverture de notre nouvelle ligne Abidjan-Accra à partir du 1er juillet.',
                'announcement_type': 'news',
                'audience': 'clients',
                'is_active': True,
                'start_date': timezone.now(),
                'priority': 2,
                'created_by': self.admin_user
            },
        ]
        
        self.announcements = []
        for data in announcements_data:
            announcement = Announcement.objects.create(**data)
            self.announcements.append(announcement)
            self.stdout.write(f'  - Annonce "{announcement.title}" créée')
            
            # Créer des notifications pour certains utilisateurs
            if announcement.announcement_type == 'promotion':
                for client in self.clients[:2]:  # 2 premiers clients
                    Notification.objects.create(
                        user=client,
                        title="Nouvelle Promotion Disponible!",
                        message=announcement.content,
                        notification_type='info',
                        related_announcement=announcement,
                        action_url=announcement.action_url,
                        icon="megaphone"
                    )
        
        # Créer quelques notifications supplémentaires
        notifications_data = [
            {
                'user': self.clients[0],
                'title': 'Voyage Confirmé',
                'message': 'Votre voyage pour Bouaké a été confirmé. Présentez-vous 1h avant le départ.',
                'notification_type': 'success',
                'related_reservation': self.reservations[0],
                'icon': 'check-circle'
            },
            {
                'user': self.clients[1],
                'title': 'Colis en Transit',
                'message': f'Votre colis {self.parcels[1].tracking_code} est arrivé à Ouagadougou.',
                'notification_type': 'info',
                'related_parcel': self.parcels[1],
                'icon': 'package'
            },
            {
                'user': self.clients[2],
                'title': 'Rappel de Voyage',
                'message': 'Votre voyage pour Bouaké est prévu demain à 08:00.',
                'notification_type': 'reminder',
                'related_reservation': self.reservations[2],
                'icon': 'clock'
            },
        ]
        
        for data in notifications_data:
            Notification.objects.create(**data)
            self.stdout.write(f'  - Notification pour {data["user"].full_name} créée')