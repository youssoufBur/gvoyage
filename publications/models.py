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