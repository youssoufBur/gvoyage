# management/commands/populate.py
import os
import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.apps import apps

from locations.models import Country, City, Agency
from users.models import User
from transport.models import Route, Leg, Schedule, Vehicle, Trip, TripPassenger, TripEvent
from reservations.models import Reservation, Ticket, Payment
from parcel.models import Parcel, TrackingEvent
from publications.models import Notification, SupportTicket, SupportMessage
from parameter.models import CompanyConfig, SystemParameter

class Command(BaseCommand):
    help = 'Peuple la base de données avec des données de démonstration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Supprimer les données existantes avant de peupler',
        )
        parser.add_argument(
            '--create-config',
            action='store_true',
            help='Créer la configuration de base de l\'entreprise',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Début du peuplement de la base de données...'))
        
        if options['clear']:
            self.clear_data()
        
        if options['create_config']:
            self.create_company_config()
        
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
            self.create_support_tickets()
            self.create_system_parameters()
        
        self.stdout.write(self.style.SUCCESS('Peuplement terminé avec succès!'))

    def clear_data(self):
        """Supprime toutes les données existantes"""
        self.stdout.write('Nettoyage des données existantes...')
        models = [
            SupportMessage, SupportTicket, Notification, 
            TrackingEvent, Parcel, Payment, Ticket, Reservation, 
            TripPassenger, TripEvent, Trip, Vehicle, Schedule, Leg, Route, 
            User, Agency, City, Country, SystemParameter, CompanyConfig
        ]
        
        for model in models:
            try:
                model.objects.all().delete()
                self.stdout.write(f'  - {model.__name__} effacé')
            except Exception as e:
                self.stdout.write(f'  - Erreur avec {model.__name__}: {e}')

    def create_company_config(self):
        """Crée la configuration de base de l'entreprise"""
        self.stdout.write('Création de la configuration entreprise...')
        
        config, created = CompanyConfig.objects.get_or_create(
            name="STM Transport",
            defaults={
                'legal_name': "STM Transport SARL",
                'slogan': "Voyagez en toute sécurité et confort",
                'phone': "+225 27 20 21 22 23",
                'phone_secondary': "+225 27 20 21 24 25",
                'email': "contact@stm-transport.ci",
                'email_support': "support@stm-transport.ci",
                'email_sales': "commercial@stm-transport.ci",
                'address': "Plateau, Avenue Chardy, Immeuble CCIA",
                'city': "Abidjan",
                'country': "Côte d'Ivoire",
                'postal_code': "01 BP 1234",
                'website': "https://stm-transport.ci",
                'facebook': "https://facebook.com/stmtransport",
                'whatsapp': "+2250700000000",
                'rc_number': "RC CI-ABJ-2023-001",
                'nif': "NIF123456789CI",
                'currency': "FCFA",
                'timezone': "Africa/Abidjan",
                'language': "fr",
                'max_seats_per_booking': 10,
                'booking_expiry_minutes': 30,
                'allow_online_payment': True,
                'max_parcel_weight': 50.0,
                'parcel_insurance_required': False,
                'maintenance_mode': False,
                'enable_sms_notifications': True,
                'enable_email_notifications': True,
            }
        )
        
        if created:
            self.stdout.write(f'  - Configuration STM Transport créée')
        else:
            self.stdout.write(f'  - Configuration existante mise à jour')

    def create_system_parameters(self):
        """Crée les paramètres système"""
        self.stdout.write('Création des paramètres système...')
        
        parameters = [
            {
                'key': 'SITE_MAINTENANCE',
                'value': 'false',
                'category': SystemParameter.Category.GENERAL,
                'description': 'Mode maintenance du site',
                'data_type': 'boolean',
                'is_public': True
            },
            {
                'key': 'MAX_BOOKING_DAYS_ADVANCE',
                'value': '30',
                'category': SystemParameter.Category.RESERVATION,
                'description': 'Nombre maximum de jours pour réserver à l\'avance',
                'data_type': 'integer',
                'is_public': True
            },
            {
                'key': 'AUTO_CANCEL_PENDING_MINUTES',
                'value': '30',
                'category': SystemParameter.Category.RESERVATION,
                'description': 'Délai avant annulation automatique des réservations en attente',
                'data_type': 'integer',
                'is_public': False
            },
            {
                'key': 'PARCEL_BASE_PRICE_PER_KG',
                'value': '500',
                'category': SystemParameter.Category.PARCEL,
                'description': 'Prix de base par kg pour les colis',
                'data_type': 'float',
                'is_public': True
            },
            {
                'key': 'ENABLE_SMS_NOTIFICATIONS',
                'value': 'true',
                'category': SystemParameter.Category.NOTIFICATION,
                'description': 'Activer les notifications SMS',
                'data_type': 'boolean',
                'is_public': False
            },
        ]
        
        for param_data in parameters:
            param, created = SystemParameter.objects.get_or_create(
                key=param_data['key'],
                defaults=param_data
            )
            if created:
                self.stdout.write(f'  - Paramètre {param.key} créé')

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
        """Crée les utilisateurs avec les nouveaux rôles"""
        self.stdout.write('Création des utilisateurs...')
        
        # Administrateur
        admin = User.objects.create_user(
            phone='+2250700000000',
            password='admin123',
            full_name='Admin System',
            email='admin@stm-transport.ci',
            role=User.Role.ADMIN,
            is_verified=True,
            is_staff=True,
            is_superuser=True
        )
        
        # Directeur Général
        dg = User.objects.create_user(
            phone='+2250700000001',
            password='dg123',
            full_name='Directeur Général',
            email='dg@stm-transport.ci',
            role=User.Role.DG,
            is_verified=True,
            agency=self.agencies['ABJ_NAT']
        )
        
        # Chef d'Agence Nationale
        national_manager = User.objects.create_user(
            phone='+2250700000002',
            password='manager123',
            full_name='Chef Agence Nationale',
            email='national.manager@stm-transport.ci',
            role=User.Role.NATIONAL_MANAGER,
            is_verified=True,
            agency=self.agencies['ABJ_NAT']
        )
        
        # Chefs d'Agence Centrale
        central_managers = [
            {
                'phone': '+2250700000003',
                'full_name': 'Chef Agence Abidjan',
                'email': 'abidjan.manager@stm-transport.ci',
                'agency': self.agencies['ABJ_CENT'],
                'role': User.Role.CENTRAL_MANAGER
            },
            {
                'phone': '+2267600000001',
                'full_name': 'Chef Agence Ouagadougou',
                'email': 'ouaga.manager@stm-transport.bf',
                'agency': self.agencies['OUA_CENT'],
                'role': User.Role.CENTRAL_MANAGER
            },
        ]
        
        self.managers = []
        for data in central_managers:
            manager = User.objects.create_user(
                password='manager123',
                is_verified=True,
                **data
            )
            self.managers.append(manager)
            self.stdout.write(f'  - Manager {manager.full_name} créé')
        
        # Chefs d'Agence Locale
        agency_managers = [
            {
                'phone': '+2250700000004',
                'full_name': 'Chef Agence Yopougon',
                'email': 'yopougon.manager@stm-transport.ci',
                'agency': self.agencies['ABJ_YOP'],
                'role': User.Role.AGENCY_MANAGER
            },
            {
                'phone': '+2250700000005',
                'full_name': 'Chef Agence Cocody',
                'email': 'cocody.manager@stm-transport.ci',
                'agency': self.agencies['ABJ_COC'],
                'role': User.Role.AGENCY_MANAGER
            },
        ]
        
        for data in agency_managers:
            manager = User.objects.create_user(
                password='manager123',
                is_verified=True,
                **data
            )
            self.managers.append(manager)
            self.stdout.write(f'  - Manager {manager.full_name} créé')
        
        # Agents
        agents = [
            {
                'phone': '+2250700000006',
                'full_name': 'Agent Service Client',
                'email': 'agent@stm-transport.ci',
                'agency': self.agencies['ABJ_CENT'],
                'role': User.Role.AGENT
            },
        ]
        
        self.agents = []
        for data in agents:
            agent = User.objects.create_user(
                password='agent123',
                is_verified=True,
                **data
            )
            self.agents.append(agent)
            self.stdout.write(f'  - Agent {agent.full_name} créé')
        
        # Chauffeurs
        drivers_data = [
            {
                'phone': '+2250701010101',
                'full_name': 'Kouame Yao',
                'agency': self.agencies['ABJ_CENT'],
                'role': User.Role.CHAUFFEUR
            },
            {
                'phone': '+2250702020202',
                'full_name': 'Jean Traoré',
                'agency': self.agencies['ABJ_CENT'],
                'role': User.Role.CHAUFFEUR
            },
            {
                'phone': '+2267601010101',
                'full_name': 'Moussa Sawadogo',
                'agency': self.agencies['OUA_CENT'],
                'role': User.Role.CHAUFFEUR
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
                'role': User.Role.CAISSIER
            },
            {
                'phone': '+2250704040404',
                'full_name': 'Paul Aké',
                'agency': self.agencies['ABJ_YOP'],
                'role': User.Role.CAISSIER
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
        
        # Livreurs
        livreurs_data = [
            {
                'phone': '+2250705050505',
                'full_name': 'Livreur Express',
                'agency': self.agencies['ABJ_CENT'],
                'role': User.Role.LIVREUR
            },
        ]
        
        self.livreurs = []
        for data in livreurs_data:
            livreur = User.objects.create_user(
                password='livreur123',
                is_verified=True,
                **data
            )
            self.livreurs.append(livreur)
            self.stdout.write(f'  - Livreur {livreur.full_name} créé')
        
        # Clients
        clients_data = [
            {
                'phone': '+2250505050505',
                'full_name': 'Marie Koné',
                'email': 'marie.kone@email.ci',
                'gender': User.Gender.FEMALE,
                'role': User.Role.CLIENT
            },
            {
                'phone': '+2250506060606',
                'full_name': 'Mohamed Sylla',
                'email': 'mohamed.sylla@email.ci',
                'gender': User.Gender.MALE,
                'role': User.Role.CLIENT
            },
            {
                'phone': '+2250507070707',
                'full_name': 'Fatou Bamba',
                'email': 'fatou.bamba@email.ci',
                'gender': User.Gender.FEMALE,
                'role': User.Role.CLIENT
            },
            {
                'phone': '+2267605050505',
                'full_name': 'Ibrahim Ouedraogo',
                'email': 'ibrahim.ouedraogo@email.bf',
                'gender': User.Gender.MALE,
                'role': User.Role.CLIENT
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
        self.dg_user = dg

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
                'days_of_week': 'daily',
                'is_active': True
            },
            {
                'leg': self.legs[0],
                'agency': self.agencies['ABJ_CENT'],
                'departure_time': '14:00',
                'days_of_week': 'daily',
                'is_active': True
            },
            {
                'leg': self.legs[1],  # Bouaké -> Korhogo
                'agency': self.agencies['ABJ_CENT'],
                'departure_time': '12:00',
                'days_of_week': 'mon,wed,fri,sun',
                'is_active': True
            },
            {
                'leg': self.legs[3],  # ABJ -> Bouaké direct
                'agency': self.agencies['ABJ_CENT'],
                'departure_time': '08:00',
                'days_of_week': 'daily',
                'is_active': True
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
                'agency': self.agencies['ABJ_CENT'],
                'is_active': True
            },
            {
                'plate': 'CI-5678-CD',
                'capacity': 35,
                'type': 'minibus',
                'agency': self.agencies['ABJ_CENT'],
                'is_active': True
            },
            {
                'plate': 'BF-9012-EF',
                'capacity': 50,
                'type': 'bus',
                'agency': self.agencies['OUA_CENT'],
                'is_active': True
            },
            {
                'plate': 'CI-3456-GH',
                'capacity': 28,
                'type': 'minibus',
                'agency': self.agencies['ABJ_YOP'],
                'is_active': True
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
        yesterday = today - timedelta(days=1)
        
        trips_data = [
            {
                'schedule': self.schedules[0],  # ABJ -> Bouaké 06:00
                'agency': self.agencies['ABJ_CENT'],
                'vehicle': self.vehicles[0],
                'driver': self.drivers[0],
                'departure_dt': timezone.make_aware(datetime.combine(yesterday, datetime.strptime('06:00', '%H:%M').time())),
                'status': Trip.Status.COMPLETED
            },
            {
                'schedule': self.schedules[0],  # ABJ -> Bouaké 06:00 (aujourd'hui)
                'agency': self.agencies['ABJ_CENT'],
                'vehicle': self.vehicles[1],
                'driver': self.drivers[1],
                'departure_dt': timezone.make_aware(datetime.combine(today, datetime.strptime('06:00', '%H:%M').time())),
                'status': Trip.Status.IN_PROGRESS
            },
            {
                'schedule': self.schedules[1],  # ABJ -> Bouaké 14:00 (aujourd'hui)
                'agency': self.agencies['ABJ_CENT'],
                'vehicle': self.vehicles[0],
                'driver': self.drivers[0],
                'departure_dt': timezone.make_aware(datetime.combine(today, datetime.strptime('14:00', '%H:%M').time())),
                'status': Trip.Status.BOARDING
            },
            {
                'schedule': self.schedules[3],  # ABJ -> Bouaké direct 08:00 (demain)
                'agency': self.agencies['ABJ_CENT'],
                'vehicle': self.vehicles[2],
                'driver': self.drivers[0],
                'departure_dt': timezone.make_aware(datetime.combine(tomorrow, datetime.strptime('08:00', '%H:%M').time())),
                'status': Trip.Status.PLANNED
            },
        ]
        
        self.trips = []
        for data in trips_data:
            trip = Trip.objects.create(**data)
            self.trips.append(trip)
            self.stdout.write(f'  - Trip {trip} créé')
            
            # Créer des événements pour les voyages en cours et terminés
            if trip.status == Trip.Status.COMPLETED:
                # Événements pour voyage terminé
                TripEvent.objects.create(
                    trip=trip,
                    event_type=TripEvent.Type.DEPARTURE,
                    city=trip.schedule.leg.origin,
                    timestamp=trip.departure_dt,
                    created_by=trip.driver
                )
                TripEvent.objects.create(
                    trip=trip,
                    event_type=TripEvent.Type.ARRIVAL,
                    city=trip.schedule.leg.destination,
                    timestamp=trip.departure_dt + timedelta(minutes=trip.schedule.leg.duration_minutes),
                    created_by=trip.driver
                )
            elif trip.status == Trip.Status.IN_PROGRESS:
                # Événements pour voyage en cours
                TripEvent.objects.create(
                    trip=trip,
                    event_type=TripEvent.Type.DEPARTURE,
                    city=trip.schedule.leg.origin,
                    timestamp=trip.departure_dt,
                    created_by=trip.driver
                )
                TripEvent.objects.create(
                    trip=trip,
                    event_type=TripEvent.Type.STOP,
                    city=self.cities['Bouaké'],
                    timestamp=trip.departure_dt + timedelta(minutes=120),
                    created_by=trip.driver,
                    note="Arrêt technique à Bouaké"
                )

    def create_reservations_tickets(self):
        """Crée les réservations et tickets"""
        self.stdout.write('Création des réservations et tickets...')
        
        reservations_data = [
            {
                'buyer': self.clients[0],
                'schedule': self.schedules[0],
                'travel_date': timezone.now().date() - timedelta(days=1),  # Hier
                'total_seats': 2,
                'total_price': 10000,
                'status': Reservation.Status.PAID
            },
            {
                'buyer': self.clients[1],
                'schedule': self.schedules[0],
                'travel_date': timezone.now().date(),  # Aujourd'hui
                'total_seats': 1,
                'total_price': 5000,
                'status': Reservation.Status.PAID
            },
            {
                'buyer': self.clients[2],
                'schedule': self.schedules[3],
                'travel_date': timezone.now().date() + timedelta(days=1),  # Demain
                'total_seats': 3,
                'total_price': 15000,
                'status': Reservation.Status.PENDING
            },
        ]
        
        self.reservations = []
        for data in reservations_data:
            reservation = Reservation.objects.create(**data)
            self.reservations.append(reservation)
            self.stdout.write(f'  - Réservation {reservation.code} créée')
            
            # Créer les tickets pour cette réservation
            for i in range(data['total_seats']):
                # Associer le bon voyage selon la date
                trip = None
                if reservation.travel_date == timezone.now().date() - timedelta(days=1):
                    trip = self.trips[0]  # Voyage d'hier
                elif reservation.travel_date == timezone.now().date():
                    trip = self.trips[1]  # Voyage d'aujourd'hui
                elif reservation.travel_date == timezone.now().date() + timedelta(days=1):
                    trip = self.trips[3]  # Voyage de demain
                
                ticket = Ticket.objects.create(
                    reservation=reservation,
                    trip=trip,
                    buyer=reservation.buyer,
                    passenger_name=f"{reservation.buyer.full_name} {i+1}",
                    passenger_phone=reservation.buyer.phone,
                    seat_number=i + 1,
                    status=Ticket.Status.CONFIRMED if reservation.status == Reservation.Status.PAID else Ticket.Status.CONFIRMED
                )
                self.stdout.write(f'    - Ticket {ticket.passenger_name} créé')
                
                # Créer un passager pour les tickets associés à un voyage
                if trip:
                    trip_passenger = TripPassenger.objects.create(
                        trip=trip,
                        ticket=ticket,
                        client=reservation.buyer,
                        passenger_name=ticket.passenger_name,
                        seat_number=ticket.seat_number,
                        is_onboard=(trip.status == Trip.Status.IN_PROGRESS)
                    )
                    if trip.status == Trip.Status.COMPLETED:
                        trip_passenger.mark_disembarked(trip.schedule.leg.destination)
                    elif trip.status == Trip.Status.IN_PROGRESS:
                        trip_passenger.mark_boarded()
            
            # Créer le paiement pour les réservations payées
            if reservation.status == Reservation.Status.PAID:
                payment = Payment.objects.create(
                    reservation=reservation,
                    method=Payment.Method.CASH,
                    amount=reservation.total_price,
                    status=Payment.Status.COMPLETED,
                    agency=self.agencies['ABJ_CENT'],
                    paid_at=reservation.created + timedelta(hours=1)
                )
                self.stdout.write(f'    - Paiement {payment.amount} FCFA créé')

    def create_parcels(self):
        """Crée les colis"""
        self.stdout.write('Création des colis...')
        
        parcels_data = [
            {
                'sender': self.clients[0],
                'sender_name': 'Marie Koné',
                'sender_phone': '+2250505050505',
                'receiver_name': 'Koffi N\'Guessan',
                'receiver_phone': '+2250801010101',
                'receiver_address': 'Rue du Commerce, Bouaké',
                'origin_agency': self.agencies['ABJ_CENT'],
                'destination_agency': self.agencies['ABJ_CENT'],  # Même agence pour la démo
                'origin_city': self.cities['Abidjan'],
                'destination_city': self.cities['Bouaké'],
                'receiver_city': self.cities['Bouaké'],
                'category': Parcel.Category.MEDIUM,
                'weight_kg': 5.5,
                'base_price': 5000,
                'insurance_fee': 500,
                'delivery_fee': 2000,
                'status': Parcel.Status.DELIVERED,
                'current_city': self.cities['Bouaké'],
                'current_agency': self.agencies['ABJ_CENT'],
                'requires_signature': True,
                'delivery_proof': 'Signature: Koffi N',
                'last_handled_by': self.cashiers[0],
                'actual_delivery': timezone.now() - timedelta(days=1)
            },
            {
                'sender': self.clients[1],
                'sender_name': 'Mohamed Sylla',
                'sender_phone': '+2250506060606',
                'receiver_name': 'Aminata Bamba',
                'receiver_phone': '+2267002020202',
                'receiver_address': 'Avenue de la Nation, Ouagadougou',
                'origin_agency': self.agencies['ABJ_CENT'],
                'destination_agency': self.agencies['OUA_CENT'],
                'origin_city': self.cities['Abidjan'],
                'destination_city': self.cities['Ouagadougou'],
                'receiver_city': self.cities['Ouagadougou'],
                'category': Parcel.Category.SMALL,
                'weight_kg': 1.2,
                'base_price': 8000,
                'insurance_fee': 0,
                'delivery_fee': 4000,
                'status': Parcel.Status.AT_AGENCY,
                'current_city': self.cities['Ouagadougou'],
                'current_agency': self.agencies['OUA_CENT'],
                'requires_signature': False,
                'last_handled_by': self.cashiers[0]
            },
            {
                'sender': self.clients[2],
                'sender_name': 'Fatou Bamba',
                'sender_phone': '+2250507070707',
                'receiver_name': 'Sékou Traoré',
                'receiver_phone': '+2250703030303',
                'receiver_address': 'Badalabougou, Bamako',
                'origin_agency': self.agencies['ABJ_CENT'],
                'destination_agency': self.agencies['BAM_CENT'],
                'origin_city': self.cities['Abidjan'],
                'destination_city': self.cities['Bamako'],
                'receiver_city': self.cities['Bamako'],
                'category': Parcel.Category.LARGE,
                'weight_kg': 25.0,
                'base_price': 25000,
                'insurance_fee': 2500,
                'delivery_fee': 7500,
                'status': Parcel.Status.LOADED,
                'current_city': self.cities['Bouaké'],
                'current_agency': self.agencies['ABJ_CENT'],
                'current_trip': self.trips[1],
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
            status_events = []
            
            if parcel.status == Parcel.Status.DELIVERED:
                status_events = [
                    (Parcel.Status.CREATED, "Colis enregistré", parcel.created),
                    (Parcel.Status.LOADED, "Colis chargé dans le véhicule", parcel.created + timedelta(hours=2)),
                    (Parcel.Status.AT_AGENCY, "Colis arrivé à l'agence", parcel.created + timedelta(hours=6)),
                    (Parcel.Status.DELIVERED, "Colis livré au destinataire", parcel.actual_delivery),
                ]
            elif parcel.status == Parcel.Status.AT_AGENCY:
                status_events = [
                    (Parcel.Status.CREATED, "Colis enregistré", parcel.created),
                    (Parcel.Status.LOADED, "Colis chargé dans le véhicule", parcel.created + timedelta(hours=2)),
                    (Parcel.Status.AT_AGENCY, "Colis arrivé à l'agence", parcel.created + timedelta(hours=6)),
                ]
            elif parcel.status == Parcel.Status.LOADED:
                status_events = [
                    (Parcel.Status.CREATED, "Colis enregistré", parcel.created),
                    (Parcel.Status.LOADED, "Colis chargé dans le véhicule", parcel.created + timedelta(hours=2)),
                ]
            
            for status, note, event_time in status_events:
                TrackingEvent.objects.create(
                    parcel=parcel,
                    event=status,
                    status=status,
                    city=parcel.current_city,
                    agency=parcel.current_agency,
                    trip=parcel.current_trip,
                    actor=parcel.last_handled_by,
                    note=note,
                    ts=event_time
                )

    def create_announcements_notifications(self):
        """Crée les annonces et notifications"""
        self.stdout.write('Création des annonces et notifications...')
        
             # Créer quelques notifications supplémentaires
        notifications_data = [
            {
                'user': self.clients[0],
                'title': 'Voyage Confirmé',
                'message': 'Votre voyage pour Bouaké a été confirmé. Présentez-vous 1h avant le départ.',
                'notification_type': Notification.Type.SUCCESS,
                'related_reservation': self.reservations[0],
                'icon': 'check-circle',
                'channel': Notification.Channel.ALL,
                'should_send_email': True
            },
            {
                'user': self.clients[1],
                'title': 'Colis en Transit',
                'message': f'Votre colis {self.parcels[1].tracking_code} est arrivé à Ouagadougou.',
                'notification_type': Notification.Type.INFO,
                'related_parcel': self.parcels[1],
                'icon': 'package',
                'channel': Notification.Channel.IN_APP,
                'should_send_sms': True
            },
            {
                'user': self.clients[2],
                'title': 'Rappel de Voyage',
                'message': 'Votre voyage pour Bouaké est prévu demain à 08:00.',
                'notification_type': Notification.Type.REMINDER,
                'related_reservation': self.reservations[2],
                'icon': 'clock',
                'channel': Notification.Channel.ALL,
                'should_send_email': True,
                'should_send_sms': True
            },
        ]
        
        for data in notifications_data:
            notification = Notification.objects.create(**data)
            self.stdout.write(f'  - Notification pour {data["user"].full_name} créée')

    def create_support_tickets(self):
        """Crée des tickets de support de démonstration"""
        self.stdout.write('Création des tickets de support...')
        
        support_tickets_data = [
            {
                'user': self.clients[0],
                'category': SupportTicket.Category.RESERVATION,
                'subject': 'Problème avec ma réservation',
                'description': 'Je n\'arrive pas à modifier les dates de mon voyage. Pouvez-vous m\'aider?',
                'priority': SupportTicket.Priority.MEDIUM,
                'status': SupportTicket.Status.IN_PROGRESS,
                'assigned_to': self.agents[0],
                'agency': self.agencies['ABJ_CENT']
            },
            {
                'user': self.clients[1],
                'category': SupportTicket.Category.PARCEL,
                'subject': 'Retard dans la livraison de mon colis',
                'description': 'Mon colis devait être livré hier mais il n\'est toujours pas arrivé.',
                'priority': SupportTicket.Priority.HIGH,
                'status': SupportTicket.Status.OPEN,
                'agency': self.agencies['OUA_CENT']
            },
            {
                'user': self.clients[2],
                'category': SupportTicket.Category.PAYMENT,
                'subject': 'Remboursement demandé',
                'description': 'Mon voyage a été annulé, je souhaite être remboursé.',
                'priority': SupportTicket.Priority.MEDIUM,
                'status': SupportTicket.Status.WAITING_CUSTOMER,
                'assigned_to': self.agents[0],
                'agency': self.agencies['ABJ_CENT']
            },
        ]
        
        self.support_tickets = []
        for data in support_tickets_data:
            ticket = SupportTicket.objects.create(**data)
            self.support_tickets.append(ticket)
            self.stdout.write(f'  - Ticket support {ticket.ticket_id} créé')
            
            # Créer des messages pour certains tickets
            if ticket.status == SupportTicket.Status.IN_PROGRESS:
                SupportMessage.objects.create(
                    ticket=ticket,
                    user=ticket.assigned_to,
                    message="Bonjour, je vais vous aider avec votre problème de réservation. Pouvez-vous me donner le numéro de votre réservation?",
                    message_type=SupportMessage.MessageType.AGENT
                )
            elif ticket.status == SupportTicket.Status.WAITING_CUSTOMER:
                SupportMessage.objects.create(
                    ticket=ticket,
                    user=ticket.assigned_to,
                    message="Votre demande de remboursement a été prise en compte. Nous avons besoin de votre RIB pour procéder au virement.",
                    message_type=SupportMessage.MessageType.AGENT
                )