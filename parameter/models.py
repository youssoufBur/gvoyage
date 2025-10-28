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